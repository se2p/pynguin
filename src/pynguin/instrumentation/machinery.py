#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
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

from importlib.abc import FileLoader
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.machinery import SourceFileLoader
from inspect import isclass
from types import CodeType
from typing import TYPE_CHECKING
from typing import cast

import pynguin.configuration as config

from pynguin.analyses.constants import ConstantPool
from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.instrumentation.instrumentation import BranchCoverageInstrumentation
from pynguin.instrumentation.instrumentation import CheckedCoverageInstrumentation
from pynguin.instrumentation.instrumentation import DynamicSeedingInstrumentation
from pynguin.instrumentation.instrumentation import InstrumentationTransformer
from pynguin.instrumentation.instrumentation import LineCoverageInstrumentation


if TYPE_CHECKING:
    from pynguin.instrumentation.instrumentation import InstrumentationAdapter
    from pynguin.testcase.execution import ExecutionTracer


class InstrumentationLoader(SourceFileLoader):
    """A loader that instruments the module after execution."""

    def __init__(  # noqa: D107
        self,
        fullname,
        path,
        tracer: ExecutionTracer,
        transformer: InstrumentationTransformer,
    ):
        super().__init__(fullname, path)
        self._tracer = tracer
        self._transformer = transformer

    def exec_module(self, module):  # noqa: D102
        self._tracer.reset()
        super().exec_module(module)
        self._tracer.store_import_trace()

    def get_code(self, fullname) -> CodeType:
        """Add instrumentation instructions to the code of the module.

        This happens before the module is executed.

        Args:
            fullname: The name of the module

        Returns:
            The modules code blocks
        """
        to_instrument = cast(CodeType, super().get_code(fullname))
        assert to_instrument is not None, "Failed to get code object of module."
        return self._transformer.instrument_module(to_instrument)


def build_transformer(
    tracer: ExecutionTracer,
    coverage_metrics: set[config.CoverageMetric],
    dynamic_constant_provider: DynamicConstantProvider | None = None,
) -> InstrumentationTransformer:
    """Build a transformer that applies the configured instrumentation.

    Args:
        tracer: The tracer to use.
        coverage_metrics: The coverage metrics to use.
        dynamic_constant_provider: The dynamic constant provider to use.
            When such a provider is passed, we apply the instrumentation for dynamic
            constant seeding.

    Returns:
        An instrumentation transformer.
    """
    adapters: list[InstrumentationAdapter] = []
    if config.CoverageMetric.BRANCH in coverage_metrics:
        adapters.append(BranchCoverageInstrumentation(tracer))
    if config.CoverageMetric.LINE in coverage_metrics:
        adapters.append(LineCoverageInstrumentation(tracer))
    if config.CoverageMetric.CHECKED in coverage_metrics:
        adapters.append(CheckedCoverageInstrumentation(tracer))

    if dynamic_constant_provider is not None:
        adapters.append(DynamicSeedingInstrumentation(dynamic_constant_provider))

    return InstrumentationTransformer(tracer, adapters)


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
        tracer: ExecutionTracer,
        coverage_metrics: set[config.CoverageMetric],
        dynamic_constant_provider: DynamicConstantProvider | None = None,
    ) -> None:
        """Wraps the given pathfinder.

        Args:
            original_pathfinder: the original pathfinder that is wrapped.
            module_to_instrument: the name of the module, that should be instrumented.
            tracer: the execution tracer
            coverage_metrics: the coverage metrics to be used for instrumentation.
            dynamic_constant_provider: Used for dynamic constant seeding
        """
        self._module_to_instrument = module_to_instrument
        self._original_pathfinder = original_pathfinder
        self._tracer = tracer
        self._coverage_metrics = coverage_metrics
        self._dynamic_constant_provider = dynamic_constant_provider

    def update_instrumentation_metrics(
        self,
        tracer: ExecutionTracer,
        coverage_metrics: set[config.CoverageMetric],
        dynamic_constant_provider: DynamicConstantProvider | None,
    ) -> None:
        """Update the coverage instrumentation.

        Useful for re-applying a different instrumentation.

        Args:
            tracer: The new execution tracer
            coverage_metrics: The new coverage metrics
            dynamic_constant_provider: The dynamic constant provider, if any.
        """
        self._tracer = tracer
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
                        self._tracer,
                        build_transformer(
                            self._tracer,
                            self._coverage_metrics,
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
    tracer: ExecutionTracer,
    coverage_metrics: set[config.CoverageMetric] | None = None,
    dynamic_constant_provider: DynamicConstantProvider | None = None,
) -> ImportHookContextManager:
    """Install the InstrumentationFinder in the meta path.

    Args:
        module_to_instrument: The module that shall be instrumented.
        tracer: The tracer where the instrumentation should report its data.
        coverage_metrics: the coverage metrics to be used for instrumentation, falls
            back to the configured metrics in the configuration, if not specified.
        dynamic_constant_provider: Used for dynamic constant seeding

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

    to_wrap = None
    for finder in sys.meta_path:
        if isclass(finder) and finder.__name__ == "PathFinder" and hasattr(finder, "find_spec"):
            to_wrap = finder
            break

    if not to_wrap:
        raise RuntimeError("Cannot find a PathFinder in sys.meta_path")

    hook = InstrumentationFinder(
        original_pathfinder=to_wrap,
        module_to_instrument=module_to_instrument,
        tracer=tracer,
        coverage_metrics=coverage_metrics,
        dynamic_constant_provider=dynamic_constant_provider,
    )
    sys.meta_path.insert(0, hook)
    return ImportHookContextManager(hook)
