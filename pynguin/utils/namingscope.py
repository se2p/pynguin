#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a naming scope."""
from __future__ import annotations

import typing
from abc import abstractmethod
from collections import defaultdict
from typing import Any, Callable

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

    def __init__(
        self,
        prefix: str = "var",
        new_name_callback: Callable[[Any, str], None] | None = None,
    ) -> None:
        """Initialises the scope.

        Args:
            prefix: The prefix that will be used in all assigned names.
            new_name_callback: Called when a new object is named.
        """
        self._known_names: dict[Any, str] = {}
        self._prefix = prefix
        self._new_name_callback = new_name_callback

    def get_name(self, obj: Any) -> str:
        if obj in self._known_names:
            return self._known_names[obj]

        index = len(self._known_names)
        self._known_names[obj] = name = f"{self._prefix}_{index}"
        if self._new_name_callback is not None:
            self._new_name_callback(obj, name)
        return name

    def __len__(self):
        return len(self._known_names)

    def __iter__(self):
        for obj in self._known_names:
            yield obj, self.get_name(obj)

    def is_known_name(self, obj) -> bool:
        return obj in self._known_names


class VariableTypeNamingScope(AbstractNamingScope):
    """Names variables according to their type."""

    def __init__(
        self, *, return_type_trace: dict[int, type] | None = None, prefix: str = "var"
    ):
        self._known_variable_names: dict[vr.VariableReference, str] = {}
        self._type_counter: dict[str, int] = defaultdict(int)
        self._prefix = prefix
        self._return_type_trace = return_type_trace

    def get_name(self, obj: vr.VariableReference) -> str:
        if (name := self._known_variable_names.get(obj)) is not None:
            return name

        # Statically annotated type
        type_ = obj.type

        # Lookup runtime type if available from trace:
        if (
            self._return_type_trace is not None
            and (
                runtime_type := self._return_type_trace.get(
                    obj.get_statement_position()
                )
            )
            is not None
        ):
            type_ = runtime_type

        tp_name = self._prefix
        if type_ is not None:
            if isinstance(type_, type):
                # Regular type
                tp_name = snake_case(type_.__name__)
            elif type_ == typing.Any:
                # In case the type is `Any`, still keep the default prefix
                tp_name = self._prefix
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
        yield from self._known_variable_names.items()

    def is_known_name(self, obj) -> bool:
        return obj in self._known_variable_names


def snake_case(name: str) -> str:
    """Create a snake case representation from the given string.

    Args:
        name: the string to camel case

    Returns:
        The snake-cased string.
    """
    assert len(name) > 0, "Cannot snake_case empty string"
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")
