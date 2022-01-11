#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a naming scope."""
from abc import abstractmethod
from collections import defaultdict
from typing import Any, Dict

import pynguin.testcase.variablereference as vr


class AbstractNamingScope:
    """Provides names for objects."""

    @abstractmethod
    def get_name(self, obj) -> str:
        """Get the name for the given object within this scope.

        Args:
            obj: the object for which a name is requested

        Returns:
            the variable name
        """

    @abstractmethod
    def is_known_name(self, obj) -> bool:
        """Does the given object have an assigned name in this scope.

        Args:
            obj: The object to check

        Returns:
            True, iff the object has a name.
        """

    @abstractmethod
    def __len__(self):
        """Return the amount of assigned names."""

    @abstractmethod
    def __iter__(self):
        """Iterate the objects and the associated names"""


class NamingScope(AbstractNamingScope):
    """Maps objects to unique, human friendly names."""

    def __init__(self, prefix: str = "var") -> None:
        """Initialises the scope

        Args:
            prefix: The prefix that will be used in the name.
        """
        self._known_name_indices: Dict[Any, int] = {}
        self._prefix = prefix

    def get_name(self, obj: Any) -> str:
        if obj in self._known_name_indices:
            index = self._known_name_indices.get(obj)
        else:
            index = len(self._known_name_indices)
            self._known_name_indices[obj] = index
        return self._prefix + "_" + str(index)

    def __len__(self):
        return len(self._known_name_indices)

    def __iter__(self):
        for obj in self._known_name_indices:
            yield obj, self.get_name(obj)

    def is_known_name(self, obj) -> bool:
        return obj in self._known_name_indices


class VariableTypeNamingScope(AbstractNamingScope):
    """Names variables according to their type."""

    def __init__(self, prefix: str = "var"):
        self._known_variable_names: Dict[vr.VariableReference, str] = {}
        self._type_counter: Dict[str, int] = defaultdict(int)
        self._prefix = prefix

    def get_name(self, obj: vr.VariableReference) -> str:
        if (name := self._known_variable_names.get(obj)) is not None:
            return name
        type_ = obj.type
        tp_name = self._prefix
        if type_ is not None:
            if isinstance(type_, type):
                # Regular type
                tp_name = snake_case(type_.__name__)
            elif (name_ := getattr(type_, "_name", None)) is not None:
                # Some type hint. Not sure if all have "_name"
                tp_name = snake_case(name_)

        name = f"{tp_name}_{self._type_counter[tp_name]}"
        self._type_counter[tp_name] += 1
        self._known_variable_names[obj] = name
        return name

    def __len__(self):
        return len(self._known_variable_names)

    def __iter__(self):
        for obj, name in self._known_variable_names.items():
            yield obj, name

    def is_known_name(self, obj) -> bool:
        return obj in self._known_variable_names


def snake_case(name: str) -> str:
    """We assume that we only have to lowercase the first char.

    Args:
        name: the string to camel case

    Returns:
        The cheaply camel cased string.
    """
    assert len(name) > 0, "Cannot snake_case empty string"
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")
