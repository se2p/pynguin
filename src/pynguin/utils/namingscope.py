#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a naming scope."""

from __future__ import annotations

import typing

from abc import abstractmethod
from collections import defaultdict
from typing import Any

from pynguin.analyses.typesystem import TypeVisitor


if typing.TYPE_CHECKING:
    from collections.abc import Callable

    import pynguin.testcase.variablereference as vr

    from pynguin.analyses.typesystem import AnyType
    from pynguin.analyses.typesystem import Instance
    from pynguin.analyses.typesystem import NoneType
    from pynguin.analyses.typesystem import ProperType
    from pynguin.analyses.typesystem import TupleType
    from pynguin.analyses.typesystem import UnionType
    from pynguin.analyses.typesystem import Unsupported


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
        """Iterate the objects and the associated names."""


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

    def get_name(self, obj: Any) -> str:  # noqa: D102
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

    def is_known_name(self, obj) -> bool:  # noqa: D102
        return obj in self._known_names


class VariableTypeNamingScope(AbstractNamingScope):
    """Names variables according to their type."""

    def __init__(
        self,
        *,
        return_type_trace: dict[int, ProperType] | None = None,
        prefix: str = "var",
    ):
        """Constructs the naming scope.

        Args:
            return_type_trace: A dictionary of return-type traces
            prefix: The prefix for the variable names
        """
        self._known_variable_names: dict[vr.VariableReference, str] = {}
        self._type_counter: dict[str, int] = defaultdict(int)
        self._prefix = prefix
        self._return_type_trace = return_type_trace

    def get_name(self, obj: vr.VariableReference) -> str:  # noqa: D102
        if (name := self._known_variable_names.get(obj)) is not None:
            return name

        # Statically annotated type
        type_ = obj.type

        # Lookup runtime type if available from trace:
        if (
            self._return_type_trace is not None
            and (runtime_type := self._return_type_trace.get(obj.get_statement_position()))
            is not None
        ):
            type_ = runtime_type

        tp_name = snake_case(type_.accept(_VariableNameTypeVisitor(self._prefix)))

        name = f"{tp_name}_{self._type_counter[tp_name]}"
        self._type_counter[tp_name] += 1
        self._known_variable_names[obj] = name
        return name

    def __len__(self):
        return len(self._known_variable_names)

    def __iter__(self):
        yield from self._known_variable_names.items()

    def is_known_name(self, obj) -> bool:  # noqa: D102
        return obj in self._known_variable_names


class _VariableNameTypeVisitor(TypeVisitor[str]):
    def __init__(self, prefix: str):
        self._prefix = prefix

    def visit_any_type(self, left: AnyType) -> str:
        return self._prefix

    def visit_none_type(self, left: NoneType) -> str:
        return "none_type"

    def visit_instance(self, left: Instance) -> str:
        return left.type.name

    def visit_tuple_type(self, left: TupleType) -> str:
        return "tuple"

    def visit_union_type(self, left: UnionType) -> str:
        return self._prefix

    def visit_unsupported_type(self, left: Unsupported) -> str:
        raise NotImplementedError("This type shall not be used during runtime")


def snake_case(name: str) -> str:
    """Create a snake case representation from the given string.

    Args:
        name: the string to camel case

    Returns:
        The snake-cased string.
    """
    assert len(name) > 0, "Cannot snake_case empty string"
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")
