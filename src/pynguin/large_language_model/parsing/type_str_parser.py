# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-FileCopyrightText: 2023 Microsoft
#
# SPDX-License-Identifier: MIT
#
"""Provides a parser for type strings."""

import builtins
import collections
import typing


class TypeStrParser:
    """Parses type strings into type objects."""

    def __init__(self, type_system):
        """Creates a new TypeStrParser.

        Args:
            type_system: the type system to use for parsing
        """
        self._type_system = type_system

    def parse(self, type_str: str) -> type | str | None:
        """Converts a string to a type object, if possible.

        Uses the typeSystem to resolve types.

        Args:
            type_str: The string representation of the type.

        Returns:
            The corresponding type object, or None if it cannot be resolved.
        """
        if self._is_any(type_str):
            # type_str could be "Any", "typing.Any", or "builtins.object"
            return builtins.object
        if self._is_none(type_str):
            # type_str could be "None", "NoneType", or "type(None)"
            return type(None)
        if self._is_str_subtype(type_str):
            return str
        if self._is_tuple(type_str):
            # type_str could be e.g. "Tuple[int, str]", "tuple[int, str]", "typing.Tuple[int, str]"
            inner_types = self._get_inner_types(type_str)
            resolved_inner = [self.parse(t) or builtins.object for t in inner_types]
            return tuple(resolved_inner)
        if self._is_dict(type_str):
            # type_str could be e.g. "Dict[str, int]", "dict[str, int]", "typing.Dict[str, int]"
            inner_types = self._get_inner_types(type_str)
            if len(inner_types) == 2:
                key_type = self.parse(inner_types[0]) or builtins.object
                value_type = self.parse(inner_types[1]) or builtins.object
                return dict[key_type, value_type]
            return dict[builtins.object, builtins.object]
        if self._is_set(type_str):
            # type_str could be e.g. "Set[int]", "set[int]", "typing.Set[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self.parse(inner_type) if inner_type else None
            return set[resolved_inner or builtins.object]
        if self._is_list(type_str):
            # type_str could be e.g. "List[int]", "list[int]", "typing.List[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self.parse(inner_type) if inner_type else None
            return list[resolved_inner or builtins.object]
        if self._is_union(type_str):
            # type_str could be e.g. "Union[int, str]", "typing.Union[int, str]", or "int | str"
            inner_types = self._get_union_inner_types(type_str)
            resolved_inner = [self.parse(t) or builtins.object for t in inner_types]
            return typing.Union[tuple(resolved_inner)]  # noqa: UP007
        if self._is_optional(type_str):
            # type_str could be e.g. "Optional[int]", "typing.Optional[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self.parse(inner_type)
            return typing.Optional[resolved_inner]  # noqa: UP045
        if self._is_deque(type_str):
            # type_str could be e.g. "Deque[int]", "deque[int]", "typing.Deque[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self.parse(inner_type) if inner_type else None
            return collections.deque[resolved_inner or builtins.object]
        if self._is_iterable(type_str):
            # type_str could be e.g. "Iterable[int]", "iterable[int]", "typing.Iterable[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self.parse(inner_type) if inner_type else None
            return typing.Iterable[resolved_inner or builtins.object]
        # Try to resolve the type directly
        simple_types = self._type_system.get_all_types()
        for t in simple_types:
            if type_str.lower() in {t.qualname.lower(), t.name.lower()}:
                return t.raw_type
        # Could not resolve the type
        return None

    # ---- type string parsing helpers ----
    def _is_any(self, hint: str) -> bool:
        return hint in {"Any", "typing.Any", "builtins.object"}

    def _is_none(self, hint: str) -> bool:
        return hint in {"None", "NoneType", "type(None)"}

    def _is_tuple(self, hint: str) -> bool:
        """Check if the hint represents a tuple type."""
        return hint.startswith(("Tuple", "tuple", "typing.Tuple", "collections.abc.Tuple"))

    def _is_list(self, hint: str) -> bool:
        """Check if the hint represents a list type."""
        return hint.startswith(("List", "list", "typing.List", "collections.abc.List"))

    def _is_union(self, hint: str) -> bool:
        """Check if the hint represents a union type."""
        return hint.startswith(("Union", "typing.Union")) or " | " in hint

    def _is_optional(self, hint: str) -> bool:
        """Check if the hint represents an optional type."""
        return hint.startswith(("Optional", "typing.Optional"))

    def _is_set(self, hint: str) -> bool:
        """Check if the hint represents a set type."""
        return hint.startswith(("Set", "set", "typing.Set", "collections.abc.Set"))

    def _is_dict(self, hint: str) -> bool:
        """Check if the hint represents a dict type."""
        return hint.startswith(("Dict", "dict", "typing.Dict", "collections.abc.Dict"))

    def _is_iterable(self, hint: str) -> bool:
        """Check if the hint represents an iterable type."""
        return hint.startswith((
            "Iterable",
            "iterable",
            "typing.Iterable",
            "collections.abc.Iterable",
        ))

    def _is_deque(self, hint: str) -> bool:
        """Check if the hint represents a deque type."""
        return hint.startswith((
            "Deque",
            "deque",
            "typing.Deque",
            "collections.deque",
            "collections.abc.Deque",
        ))

    def _is_str_subtype(self, hint: str) -> bool:
        """Checks if the hint refers to a string subtype."""
        return hint.startswith((
            "substring",
            "Substring",
            "subString",
            "SubString",
            "substr",
            "Substr",
            "subStr",
            "subStr",
        ))

    def _get_inner_types(self, hint: str) -> list[str]:
        """Extract inner types from type hint.

        E.g. for "Tuple[int, str]" returns ["int", "str"].
        """
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return []
        inner = hint[start + 1 : end]
        return [t.strip() for t in inner.split(",")]

    def _get_list_inner_type(self, hint: str) -> str | None:
        """Extract inner type from a list type hint."""
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return None
        return hint[start + 1 : end].strip()

    def _get_union_inner_types(self, hint: str) -> list[str]:
        """Extract inner types from a union type hint."""
        if " | " in hint:
            return [t.strip() for t in hint.split(" | ")]
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return []
        inner = hint[start + 1 : end]
        return [t.strip() for t in inner.split(",")]
