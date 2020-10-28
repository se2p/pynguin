#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an analysis that collects all methods provided by classes."""
import dataclasses
import importlib
import inspect
import logging
from typing import Any, Dict, Set

from pynguin.setup.testcluster import TestCluster


@dataclasses.dataclass(eq=True, frozen=True)
class DefiningClass:
    """A wrapper for a class definition."""

    class_name: str = dataclasses.field(hash=True, compare=True)
    class_obj: Any = dataclasses.field(hash=False, compare=False)


@dataclasses.dataclass
class MethodBinding:
    """A wrapper for a method definition."""

    method_name: str
    method_obj: Any
    defining_classes: Set[DefiningClass]
    signature: inspect.Signature


class SourceCodeAnalyser:
    """Analyses source code for defined types."""

    def __init__(self, module_name: str, module_only_analysis: bool = False) -> None:
        """Instantiates the analysis.

        Args:
            module_name: The name of the module to analyse
            module_only_analysis: Whether or not the analysis should only be done on
                                  this particular module or also on all included (via
                                  import) modules.
        """
        self._module_name = module_name
        self._module_only_analysis = module_only_analysis
        self._method_bindings: Dict[str, MethodBinding] = {}

    @property
    def method_bindings(self) -> Dict[str, MethodBinding]:
        """Provides access to the found method bindings per method name

        Returns:
            A dictionary that maps method names to method bindings
        """
        return self._method_bindings

    def analyse_code(self) -> None:
        """Analyses the source code.

        Depending on the value of the `module_only_analysis` parameter this analyser
        instance was created with, the result of the analysis will only incorporate
        types defined in the particular module or also all types that are defined by
        included modules.
        """

        def is_member(obj: object) -> bool:
            return inspect.ismethod(obj) or inspect.isfunction(obj)

        module = importlib.import_module(self._module_name)
        for class_name, class_obj in inspect.getmembers(module, inspect.isclass):
            if self._module_only_analysis and class_obj.__module__ != self._module_name:
                continue

            defining_class = DefiningClass(class_name, class_obj)
            for method_name, method_obj in inspect.getmembers(class_obj, is_member):
                signature = inspect.signature(method_obj)
                if method_name not in self._method_bindings:
                    method_binding = MethodBinding(
                        method_name=method_name,
                        method_obj=method_obj,
                        defining_classes={defining_class},
                        signature=signature,
                    )
                else:
                    method_binding = self._method_bindings[method_name]
                    method_binding.defining_classes.add(defining_class)
                self._method_bindings[method_name] = method_binding


class DuckMockAnalysis:
    """Provides an analysis that collects all methods provided by classes."""

    _logger = logging.getLogger(__name__)

    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._method_bindings: Dict[str, MethodBinding] = {}

    def analyse(self) -> None:
        """Do the analysis."""

    def update_test_cluster(self, test_cluster: TestCluster) -> None:
        """

        Args:
            test_cluster:

        Returns:

        """
