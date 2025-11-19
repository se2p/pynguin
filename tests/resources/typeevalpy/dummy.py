#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Dummy module for testing type inference across all type categories."""

from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable
from enum import Enum
from os import PathLike
from types import ModuleType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Final,
    Literal,
    NoReturn,
    Protocol,
    TypedDict,
    TypeVar,
)

# ====== Primitive / builtin types ======


def fn_None(x: None) -> None:  # noqa: N802
    pass


def fn_bool(x: bool) -> None:  # noqa: FBT001
    pass


def fn_int(x: int) -> None:
    pass


def fn_float(x: float) -> None:
    pass


def fn_complex(x: complex) -> None:
    pass


def fn_str(x: str) -> None:
    pass


def fn_bytes(x: bytes) -> None:
    pass


def fn_bytearray(x: bytearray) -> None:
    pass


def fn_memoryview(x: memoryview) -> None:
    pass


def fn_object(x: object) -> None:
    pass


def fn_type(x: type) -> None:
    pass


# ====== Containers (builtins) ======


def fn_list(x: list) -> None:
    pass


def fn_tuple(x: tuple) -> None:
    pass


def fn_set(x: set) -> None:
    pass


def fn_frozenset(x: frozenset) -> None:
    pass


def fn_dict(x: dict) -> None:
    pass


def fn_range(x: range) -> None:
    pass


# ====== Containers (typing) ======


def fn_List(x: list[int]) -> None:  # noqa: N802
    pass


def fn_Dict(x: dict[str, int]) -> None:  # noqa: N802
    pass


def fn_Set(x: set[str]) -> None:  # noqa: N802
    pass


def fn_Tuple(x: tuple[int, str]) -> None:  # noqa: N802
    pass


def fn_Tuple_variadic(x: tuple[int, ...]) -> None:  # noqa: N802
    pass


# ====== Specialized collections ======


def fn_deque(x: deque[int]) -> None:
    pass


def fn_defaultdict(x: defaultdict[str, int]) -> None:
    pass


def fn_OrderedDict(x: OrderedDict[str, int]) -> None:  # noqa: N802
    pass


# ====== Optional / Union ======


def fn_optional(x: int | None) -> None:
    pass


def fn_union_two(x: int | str) -> None:
    pass


def fn_union_three(x: int | str | None) -> None:
    pass


# ====== Callable types ======


def fn_callable_any(x: Callable[..., Any]) -> None:
    pass


def fn_callable_empty(x: Callable[[], None]) -> None:
    pass


def fn_callable_one(x: Callable[[int], str]) -> None:
    pass


def fn_callable_two(x: Callable[[int, str], bool]) -> None:
    pass


# ====== Return types ======


def fn_return_int() -> int:
    pass


def fn_return_str() -> str:
    pass


def fn_return_list() -> list[int]:
    pass


def fn_return_dict() -> dict[str, int]:
    pass


def fn_return_callable() -> Callable[[int], str]:
    pass


def fn_return_NoReturn() -> NoReturn:  # noqa: N802
    pass


# ====== No-parameter ======


def fn_no_params() -> None:
    pass


# ====== Literal ======


def fn_literal(x: Literal[1, "a", True]) -> None:
    pass


# ====== Annotated ======


def fn_annotated(x: Annotated[int, "metadata"]) -> None:
    pass


# ====== Final, ClassVar ======

FINAL_VALUE: Final[int] = 42
CLASS_VAR: ClassVar[str] = "class-level"


# ====== TypedDict ======


class TDExample(TypedDict):
    a: int
    b: str


def fn_typeddict(x: TDExample) -> None:
    pass


# ====== Protocol ======


class ProtoExample(Protocol):
    def method(self, x: int) -> str: ...


def fn_protocol(x: ProtoExample) -> None:
    pass


# ====== Enum ======


class Color(Enum):
    RED = 1
    BLUE = 2


def fn_enum(x: Color) -> None:
    pass


# ====== Custom class ======


class Foo:
    def bar(self, x: int) -> str: ...


def fn_custom_class(x: Foo) -> None:
    pass


# ====== Nested generics ======


def fn_nested_list(x: list[dict[str, list[int]]]) -> None:
    pass


def fn_nested_dict(x: dict[str, list[tuple[int, str]]]) -> None:
    pass


# ====== Module and paths ======


def fn_module(x: ModuleType) -> None:
    pass


def fn_pathlike(x: PathLike) -> None:
    pass


# ====== Multi-param functions ======


def fn_two_params(a: int, b: str) -> None:
    pass


def fn_two_params_complex(a: list[int], b: dict[str, tuple[int, ...]]) -> None:
    pass


# ====== Variadic TypeVar example ======

T = TypeVar("T")


def fn_generic(x: T) -> T:
    pass
