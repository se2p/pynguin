# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
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

    def parse(self, type_str: str) -> type | str | None:  # noqa: C901
        """Converts a string to a type object, if possible.

        Uses the typeSystem to resolve types.

        Args:
            type_str: The string representation of the type.

        Returns:
            The corresponding type object, or None if it cannot be resolved.
        """
        if self._is_any(type_str):
            # type_str could be "Any", "typing.Any", or "builtins.object"
            return type(builtins.object)
        if self._is_none(type_str):
            # type_str could be "None", "NoneType", or "type(None)"
            return type(None)
        if self._is_str_subtype(type_str):
            return str
        if self._is_tuple(type_str):
            # type_str could be e.g. "Tuple[int, str]", "tuple[int, str]", "typing.Tuple[int, str]"
            inner_types = self._get_inner_types(type_str)
            resolved_inner = [self.parse(t) or type(builtins.object) for t in inner_types]
            return type(tuple(resolved_inner))
        if self._is_dict(type_str):
            # type_str could be e.g. "Dict[str, int]", "dict[str, int]", "typing.Dict[str, int]"
            inner_types = self._get_inner_types(type_str)
            if len(inner_types) == 2:
                key_type = self.parse(inner_types[0]) or type(builtins.object)
                value_type = self.parse(inner_types[1]) or type(builtins.object)
                return type(dict[key_type, value_type])  # type: ignore[valid-type]
            return type(dict[builtins.object, builtins.object])
        if self._is_set(type_str):
            # type_str could be e.g. "Set[int]", "set[int]", "typing.Set[int]"
            inner_type = self._get_inner_types(type_str).pop()
            resolved_inner = self.parse(inner_type) if inner_type else None  # type: ignore[assignment]
            return type(set[resolved_inner] or type(builtins.object))  # type: ignore[truthy-function, valid-type]
        if self._is_list(type_str):
            # type_str could be e.g. "List[int]", "list[int]", "typing.List[int]"
            inner_type = self._get_inner_types(type_str).pop()
            resolved_inner = self.parse(inner_type) if inner_type else None  # type: ignore[assignment]
            return type(list[resolved_inner or type(builtins.object)])  # type: ignore[misc]
        if self._is_union(type_str):
            # type_str could be e.g. "Union[int, str]", "typing.Union[int, str]", or "int | str"
            inner_types = self._get_inner_types(type_str)
            resolved_inner = [self.parse(t) or type(builtins.object) for t in inner_types]
            return type(typing.Union[tuple(resolved_inner)])  # noqa: UP007
        if self._is_optional(type_str):
            # type_str could be e.g. "Optional[int]", "typing.Optional[int]"
            inner_type = self._get_inner_types(type_str).pop()
            resolved_inner = self.parse(inner_type)  # type: ignore[assignment]
            return type(typing.Optional[resolved_inner])  # noqa: UP045
        if self._is_deque(type_str):
            # type_str could be e.g. "Deque[int]", "deque[int]", "typing.Deque[int]"
            inner_type = self._get_inner_types(type_str).pop()
            resolved_inner = self.parse(inner_type) if inner_type else None  # type: ignore[assignment]
            return type(collections.deque[resolved_inner or type(builtins.object)])  # type: ignore[misc]
        if self._is_iterable(type_str):
            # type_str could be e.g. "Iterable[int]", "iterable[int]", "typing.Iterable[int]"
            inner_type = self._get_inner_types(type_str).pop()
            resolved_inner = self.parse(inner_type) if inner_type else None  # type: ignore[assignment]
            return type(typing.Iterable[resolved_inner or type(builtins.object)])  # type: ignore[misc]
        # Try to resolve the type directly
        return self._resolve_type_by_name(type_str)

    def _resolve_type_by_name(self, type_str: str) -> type | None:
        simple_types = self._type_system.get_all_types()
        for t in simple_types:
            if type_str.lower() in {t.qualname.lower(), t.name.lower()}:
                return t.raw_type
        # Could not resolve the type
        return None

    # ---- type string parsing helpers ----
    @staticmethod
    def _is_any(hint: str) -> bool:
        return hint in {"Any", "typing.Any", "builtins.object"}

    @staticmethod
    def _is_none(hint: str) -> bool:
        return hint in {"None", "NoneType", "type(None)"}

    @staticmethod
    def _is_tuple(hint: str) -> bool:
        """Check if the hint represents a tuple type."""
        return hint.startswith(("Tuple", "tuple", "typing.Tuple", "collections.abc.Tuple"))

    @staticmethod
    def _is_list(hint: str) -> bool:
        """Check if the hint represents a list type."""
        return hint.startswith(("List", "list", "typing.List", "collections.abc.List"))

    @staticmethod
    def _is_union(hint: str) -> bool:
        """Check if the hint represents a union type."""
        return hint.startswith(("Union", "typing.Union")) or " | " in hint

    @staticmethod
    def _is_optional(hint: str) -> bool:
        """Check if the hint represents an optional type."""
        return hint.startswith(("Optional", "typing.Optional"))

    @staticmethod
    def _is_set(hint: str) -> bool:
        """Check if the hint represents a set type."""
        return hint.startswith(("Set", "set", "typing.Set", "collections.abc.Set"))

    @staticmethod
    def _is_dict(hint: str) -> bool:
        """Check if the hint represents a dict type."""
        return hint.startswith(("Dict", "dict", "typing.Dict", "collections.abc.Dict"))

    @staticmethod
    def _is_iterable(hint: str) -> bool:
        """Check if the hint represents an iterable type."""
        return hint.startswith((
            "Iterable",
            "iterable",
            "typing.Iterable",
            "collections.abc.Iterable",
        ))

    @staticmethod
    def _is_deque(hint: str) -> bool:
        """Check if the hint represents a deque type."""
        return hint.lower().startswith((
            "deque",
            "typing.deque",
            "collections.deque",
            "collections.abc.deque",
        ))

    @staticmethod
    def _is_str_subtype(hint: str) -> bool:
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

    @staticmethod
    def _get_inner_types(hint: str) -> list[str]:
        """Extract inner types from type hint.

        E.g. for "Tuple[int, str]" returns ["int", "str"].
        """
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return []
        inner = hint[start + 1 : end]
        return [t.strip() for t in inner.split(",")]
