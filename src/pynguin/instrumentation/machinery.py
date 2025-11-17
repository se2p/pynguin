#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for runtime instrumentation.

Inspired by https://github.com/agronholm/typeguard/blob/master/typeguard/importhook.py.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from importlib.abc import FileLoader, MetaPathFinder
from importlib.machinery import ModuleSpec, SourceFileLoader
from inspect import isclass
from typing import TYPE_CHECKING, cast

import pynguin.configuration as config
from pynguin.analyses.constants import ConstantPool, DynamicConstantProvider, EmptyConstantProvider
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import (
    BranchCoverageInstrumentation,
    CheckedCoverageInstrumentation,
    DynamicSeedingInstrumentation,
    LineCoverageInstrumentation,
)

if TYPE_CHECKING:
    from types import CodeType

    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.instrumentation.transformer import InstrumentationAdapter


class InstrumentationLoader(SourceFileLoader):
    """A loader that instruments the module after execution."""

    def __init__(  # noqa: D107
        self,
        fullname,
        path,
        transformer: InstrumentationTransformer,
    ):
        super().__init__(fullname, path)
        self._transformer = transformer

    def exec_module(self, module):  # noqa: D102
        self._transformer.subject_properties.reset()
        super().exec_module(module)
        self._transformer.subject_properties.instrumentation_tracer.store_import_trace()

    def get_code(self, fullname: str) -> CodeType:
        """Add instrumentation instructions to the code of the module.

        This happens before the module is executed.

        Args:
            fullname: The name of the module

        Returns:
            The modules code blocks
        """
        to_instrument = cast("CodeType", super().get_code(fullname))
        assert to_instrument is not None, "Failed to get code object of module."
        return self._transformer.instrument_code(to_instrument, fullname)


def build_transformer(
    subject_properties: SubjectProperties,
    coverage_metrics: set[config.CoverageMetric],
    to_cover_config: config.ToCoverConfiguration,
    dynamic_constant_provider: DynamicConstantProvider | None = None,
) -> InstrumentationTransformer:
    """Build a transformer that applies the configured instrumentation.

    Args:
        subject_properties: The properties of the subject under test.
        coverage_metrics: The coverage metrics to use.
        to_cover_config: the configuration of which code elements are used as coverage goals.
        dynamic_constant_provider: The dynamic constant provider to use.
            When such a provider is passed, we apply the instrumentation for dynamic
            constant seeding.

    Returns:
        An instrumentation transformer.
    """
    adapters: list[InstrumentationAdapter] = []
    if config.CoverageMetric.BRANCH in coverage_metrics:
        adapters.append(BranchCoverageInstrumentation(subject_properties))
    if config.CoverageMetric.LINE in coverage_metrics:
        adapters.append(LineCoverageInstrumentation(subject_properties))
    if config.CoverageMetric.CHECKED in coverage_metrics:
        adapters.append(CheckedCoverageInstrumentation(subject_properties))

    if dynamic_constant_provider is not None:
        adapters.append(DynamicSeedingInstrumentation(dynamic_constant_provider))

    return InstrumentationTransformer(
        subject_properties,
        adapters,
        to_cover_config=to_cover_config,
    )


class InstrumentationFinder(MetaPathFinder):
    """A meta pathfinder which wraps another pathfinder.

    It receives all import requests and intercepts the ones for the modules that
    should be instrumented.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        *,
        original_pathfinder,
        module_to_instrument: str,
        subject_properties: SubjectProperties,
        coverage_metrics: set[config.CoverageMetric],
        to_cover_config: config.ToCoverConfiguration,
        dynamic_constant_provider: DynamicConstantProvider | None = None,
    ) -> None:
        """Wraps the given pathfinder.

        Args:
            original_pathfinder: the original pathfinder that is wrapped.
            module_to_instrument: the name of the module, that should be instrumented.
            subject_properties: the properties of the subject under test.
            coverage_metrics: the coverage metrics to be used for instrumentation.
            to_cover_config: the configuration of which code elements are used as coverage goals.
            dynamic_constant_provider: Used for dynamic constant seeding.
        """
        self._module_to_instrument = module_to_instrument
        self._original_pathfinder = original_pathfinder
        self._subject_properties = subject_properties
        self._coverage_metrics = coverage_metrics
        self._to_cover_config = to_cover_config
        self._dynamic_constant_provider = dynamic_constant_provider

    @property
    def subject_properties(self) -> SubjectProperties:
        """Get the properties of the subject under test.

        Returns:
            The subject properties
        """
        return self._subject_properties

    def update_instrumentation_metrics(
        self,
        subject_properties: SubjectProperties,
        coverage_metrics: set[config.CoverageMetric],
        dynamic_constant_provider: DynamicConstantProvider | None,
    ) -> None:
        """Update the coverage instrumentation.

        Useful for re-applying a different instrumentation.

        Args:
            subject_properties: The new subject properties
            coverage_metrics: The new coverage metrics
            dynamic_constant_provider: The dynamic constant provider, if any.
        """
        self._subject_properties = subject_properties
        self._coverage_metrics = coverage_metrics
        self._dynamic_constant_provider = dynamic_constant_provider

    def _should_instrument(self, module_name: str):
        return module_name == self._module_to_instrument

    def find_spec(self, fullname: str, path=None, target=None):
        """Try to find a spec for the given module.

        If the original path finder accepts the request, we take the spec and replace
        the loader.

        Args:
            fullname: The full name of the module
            path: The path
            target: The target

        Returns:
            An optional ModuleSpec
        """
        if self._should_instrument(fullname):
            spec: ModuleSpec = self._original_pathfinder.find_spec(fullname, path, target)
            if spec is not None:
                if isinstance(spec.loader, FileLoader):
                    spec.loader = InstrumentationLoader(
                        spec.loader.name,
                        spec.loader.path,
                        build_transformer(
                            self._subject_properties,
                            self._coverage_metrics,
                            self._to_cover_config,
                            self._dynamic_constant_provider,
                        ),
                    )
                    return spec
                self._logger.error(
                    "Loader for module under test is not a FileLoader, can not instrument."
                )

        return None


class ImportHookContextManager:
    """A simple context manager for using the import hook."""

    def __init__(self, hook: MetaPathFinder):  # noqa: D107
        self.hook = hook

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.uninstall()

    def uninstall(self):
        """Remove the installed hook."""
        with contextlib.suppress(ValueError):  # suppress error if already removed
            sys.meta_path.remove(self.hook)


def install_import_hook(
    module_to_instrument: str,
    subject_properties: SubjectProperties,
    coverage_metrics: set[config.CoverageMetric] | None = None,
    to_cover_config: config.ToCoverConfiguration | None = None,
    dynamic_constant_provider: DynamicConstantProvider | None = None,
) -> ImportHookContextManager:
    """Install the InstrumentationFinder in the meta path.

    Args:
        module_to_instrument: The module that shall be instrumented.
        subject_properties: The properties of the subject under test.
        coverage_metrics: the coverage metrics to be used for instrumentation, falls
            back to the configured metrics in the configuration, if not specified.
        to_cover_config: the configuration of which code elements are used as coverage goals,
            falls back to the global configuration, if not specified.
        dynamic_constant_provider: Used for dynamic constant seeding.

    Returns:
        a context manager which can be used to uninstall the hook.

    Raises:
        RuntimeError: In case a PathFinder could not be found
    """
    if dynamic_constant_provider is None:
        # Create a dummy constant provider here. If you want to actually use this
        # feature, you should pass in your own instance.
        dynamic_constant_provider = DynamicConstantProvider(
            ConstantPool(),
            EmptyConstantProvider(),
            probability=0,
            max_constant_length=1,
        )
    if coverage_metrics is None:
        coverage_metrics = set(config.configuration.statistics_output.coverage_metrics)
    if to_cover_config is None:
        to_cover_config = config.configuration.to_cover

    if config.configuration.ignore_methods:
        module_prefix = f"{module_to_instrument}."
        to_cover_config.no_cover.extend(
            method.removeprefix(module_prefix)
            for method in config.configuration.ignore_methods
            if method.startswith(module_prefix)
        )

    to_wrap = None
    for finder in sys.meta_path:
        if isclass(finder) and finder.__name__ == "PathFinder" and hasattr(finder, "find_spec"):
            to_wrap = finder
            break

    if to_wrap is None:
        raise RuntimeError("Cannot find a PathFinder in sys.meta_path")

    hook = InstrumentationFinder(
        original_pathfinder=to_wrap,
        module_to_instrument=module_to_instrument,
        subject_properties=subject_properties,
        coverage_metrics=coverage_metrics,
        to_cover_config=to_cover_config,
        dynamic_constant_provider=dynamic_constant_provider,
    )
    sys.meta_path.insert(0, hook)
    return ImportHookContextManager(hook)
