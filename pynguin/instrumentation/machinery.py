#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""
Provides classes for runtime instrumentation.
Inspired by https://github.com/agronholm/typeguard/blob/master/typeguard/importhook.py
"""
from __future__ import annotations

import logging
import sys
from importlib.abc import FileLoader, MetaPathFinder
from importlib.machinery import ModuleSpec, SourceFileLoader
from inspect import isclass
from types import CodeType
from typing import TYPE_CHECKING, cast

import pynguin.configuration as config
from pynguin.analyses.constants import (
    ConstantPool,
    DynamicConstantProvider,
    EmptyConstantProvider,
)
from pynguin.instrumentation.instrumentation import (
    BranchCoverageInstrumentation,
    DynamicSeedingInstrumentation,
    InstrumentationTransformer,
    LineCoverageInstrumentation,
)

if TYPE_CHECKING:
    from pynguin.instrumentation.instrumentation import InstrumentationAdapter
    from pynguin.testcase.execution import ExecutionTracer


class InstrumentationLoader(SourceFileLoader):
    """A loader that instruments the module after execution."""

    def __init__(
        self,
        fullname,
        path,
        tracer: ExecutionTracer,
        dynamic_constant_provider: DynamicConstantProvider | None,
    ):
        super().__init__(fullname, path)
        self._tracer = tracer
        self._dynamic_constant_provider = dynamic_constant_provider

    def exec_module(self, module):
        self._tracer.reset()
        super().exec_module(module)
        self._tracer.store_import_trace()

    def get_code(self, fullname) -> CodeType:
        """Add instrumentation instructions to the code of the module
        before it is executed.

        Args:
            fullname: The name of the module

        Returns:
            The modules code blocks
        """
        to_instrument = cast(CodeType, super().get_code(fullname))
        assert to_instrument, "Failed to get code object of module."
        adapters: list[InstrumentationAdapter] = []
        coverage_metrics = config.configuration.statistics_output.coverage_metrics
        if config.CoverageMetric.BRANCH in coverage_metrics:
            adapters.append(BranchCoverageInstrumentation(self._tracer))
        if config.CoverageMetric.LINE in coverage_metrics:
            adapters.append(LineCoverageInstrumentation(self._tracer))

        if config.configuration.seeding.dynamic_constant_seeding:
            assert self._dynamic_constant_provider is not None
            adapters.append(
                DynamicSeedingInstrumentation(self._dynamic_constant_provider)
            )

        transformer = InstrumentationTransformer(self._tracer, adapters)
        return transformer.instrument_module(to_instrument)


class InstrumentationFinder(MetaPathFinder):
    """
    A meta path finder which wraps another pathfinder.
    It receives all import requests and intercepts the ones for the modules that
    should be instrumented.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        original_pathfinder,
        module_to_instrument: str,
        tracer: ExecutionTracer,
        dynamic_constant_provider: DynamicConstantProvider | None = None,
    ) -> None:
        """Wraps the given path finder.

        Args:
            original_pathfinder: the original pathfinder that is wrapped.
            module_to_instrument: the name of the module, that should be instrumented.
            tracer: the execution tracer
            dynamic_constant_provider: Used for dynamic constant seeding
        """
        self._module_to_instrument = module_to_instrument
        self._original_pathfinder = original_pathfinder
        self._tracer = tracer
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
            spec: ModuleSpec = self._original_pathfinder.find_spec(
                fullname, path, target
            )
            if spec is not None:
                if isinstance(spec.loader, FileLoader):
                    spec.loader = InstrumentationLoader(
                        spec.loader.name,
                        spec.loader.path,
                        self._tracer,
                        self._dynamic_constant_provider,
                    )
                    return spec
                self._logger.error(
                    "Loader for module under test is not a FileLoader,"
                    " cannot instrument."
                )

        return None


class ImportHookContextManager:
    """A simple context manager for using the import hook."""

    def __init__(self, hook: MetaPathFinder):
        self.hook = hook

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.uninstall()

    def uninstall(self):
        """Remove the installed hook."""
        try:
            sys.meta_path.remove(self.hook)
        except ValueError:
            pass  # already removed


def install_import_hook(
    module_to_instrument: str,
    tracer: ExecutionTracer,
    dynamic_constant_provider: DynamicConstantProvider | None = None,
) -> ImportHookContextManager:
    """Install the InstrumentationFinder in the meta path.

    Args:
        module_to_instrument: The module that shall be instrumented.
        tracer: The tracer where the instrumentation should report its data.
        dynamic_constant_provider: Used for dynamic constant seeding

    Returns:
        a context manager which can be used to uninstall the hook.

    Raises:
        RuntimeError: In case a PathFinder could not be found
    """
    if dynamic_constant_provider is None:
        dynamic_constant_provider = DynamicConstantProvider(
            ConstantPool(), EmptyConstantProvider(), 0
        )

    to_wrap = None
    for finder in sys.meta_path:
        if (
            isclass(finder)
            and finder.__name__ == "PathFinder"
            and hasattr(finder, "find_spec")
        ):
            to_wrap = finder
            break

    if not to_wrap:
        raise RuntimeError("Cannot find a PathFinder in sys.meta_path")

    hook = InstrumentationFinder(
        to_wrap,
        module_to_instrument,
        tracer,
        dynamic_constant_provider=dynamic_constant_provider,
    )
    sys.meta_path.insert(0, hook)
    return ImportHookContextManager(hook)
