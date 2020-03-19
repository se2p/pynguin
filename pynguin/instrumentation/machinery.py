# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""
Provides classes for runtime instrumentation.
Inspired by https://github.com/agronholm/typeguard/blob/master/typeguard/importhook.py
"""
import logging
import sys
from importlib.machinery import ModuleSpec, SourceFileLoader
from importlib.abc import MetaPathFinder, FileLoader
from inspect import isclass
from typing import Optional

from pynguin.instrumentation.branch_distance import BranchDistanceInstrumentation
from pynguin.instrumentation.basis import set_tracer
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class InstrumentationLoader(SourceFileLoader):
    """A loader that instruments the module after execution."""

    def exec_module(self, module):
        """
        Instruments the module after it was executed.
        Installs a tracer into the loaded module.
        """
        super().exec_module(module)
        tracer = ExecutionTracer()
        instrumentation = BranchDistanceInstrumentation(tracer)
        instrumentation.instrument(module)
        set_tracer(module, tracer)


class InstrumentationFinder(MetaPathFinder):
    """
    A meta path finder which wraps another pathfinder.
    It receives all import requests and intercepts the ones for the modules that
    should be instrumented.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self, original_pathfinder, module_to_instrument: str):
        """
        Wraps the given path finder.
        :param original_pathfinder: the original pathfinder that is wrapped.
        :param module_to_instrument: the name of the module, that should be instrumented.
        """
        self._module_to_instrument = module_to_instrument
        self._original_pathfinder = original_pathfinder

    def _should_instrument(self, module_name: str):
        return module_name == self._module_to_instrument

    def find_spec(self, fullname, path=None, target=None):
        """
        Try to find a spec for the given module.
        If the original path finder accepts the request, we take the spec and replace the loader.
        """
        if self._should_instrument(fullname):
            spec: ModuleSpec = self._original_pathfinder.find_spec(
                fullname, path, target
            )
            if spec is not None:
                if isinstance(spec.loader, FileLoader):
                    spec.loader = InstrumentationLoader(
                        spec.loader.name, spec.loader.path
                    )
                    return spec
                self._logger.error(
                    "Loader for module under test is not a FileLoader, cannot instrument."
                )

        return None


class ImportHookContextManager:
    """A simple context manager for using the import hook."""

    def __init__(self, hook: Optional[MetaPathFinder]):
        self.hook = hook

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.uninstall()

    def uninstall(self):
        """Remove the installed hook."""
        if self.hook is None:
            return

        try:
            sys.meta_path.remove(self.hook)
        except ValueError:
            pass  # already removed


def install_import_hook(
    use: bool, module_to_instrument: str
) -> ImportHookContextManager:
    """
    Install the InstrumentationFinder in the meta path.
    :param use: Do we actually install the hook?
    :param module_to_instrument: The module that shall be instrumented.
    :return a context manager which can be used to uninstall the hook.
    """
    if not use:
        return ImportHookContextManager(None)

    to_wrap = None
    for finder in sys.meta_path:
        if (
            isclass(finder)
            and finder.__name__ == "PathFinder"  # type: ignore
            and hasattr(finder, "find_spec")
        ):
            to_wrap = finder
            break

    if not to_wrap:
        raise RuntimeError("Cannot find a PathFinder in sys.meta_path")

    hook = InstrumentationFinder(to_wrap, module_to_instrument)
    sys.meta_path.insert(0, hook)
    return ImportHookContextManager(hook)
