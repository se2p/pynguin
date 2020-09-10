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
from typing import Any, Dict, Iterable, List, Optional, Set


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


class TypeAnalysis:
    """Provides an analysis that collects all methods provided by classes."""

    _logger = logging.getLogger(__name__)

    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._method_bindings: Dict[str, MethodBinding] = {}

    def analyse(self) -> None:
        """Do the analysis."""

        def is_member(obj: object) -> bool:
            return inspect.ismethod(obj) or inspect.isfunction(obj)

        module = importlib.import_module(self._module_name)
        for class_name, class_obj in inspect.getmembers(module, inspect.isclass):
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
                    self._method_bindings[method_name] = method_binding
                else:
                    method_binding = self._method_bindings[method_name]
                    # TODO(sl) check signatures
                    method_binding.defining_classes.add(defining_class)
                    self._method_bindings[method_name] = method_binding

    @property
    def method_bindings(self) -> Dict[str, MethodBinding]:
        """Provides access to the method-bindings dictionary.

        Returns:
            The method-bindings dictionary
        """
        return self._method_bindings

    def get_classes_for_method(self, method_name: str) -> Optional[Set[DefiningClass]]:
        """Extracts all classes that provide a certain method.

        If no class provides an appropriate method, `None` is returned.

        Args:
            method_name: the name of the method

        Returns:
            A set of defining classes, if any
        """
        if method_name not in self._method_bindings:
            return None
        return self._method_bindings[method_name].defining_classes

    def get_classes_for_methods(
        self, method_names: Iterable[str]
    ) -> Optional[Set[DefiningClass]]:
        """Extracts all classes that provide a given selection of methods.

        If no class provides all methods, `None` is returned.

        Args:
            method_names: the names of the methods as iterable

        Returns:
            A set of defining classes, if any
        """
        defining_classes: List[Set[DefiningClass]] = []
        for method_name in method_names:
            defining_class = self.get_classes_for_method(method_name)
            if defining_class is not None:
                defining_classes.append(defining_class)

        result = set.intersection(*defining_classes) if defining_classes else None
        return result
