#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from typing import Any, Dict, List, Set, Tuple, Union

import pytest

from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import (
    AnyType,
    InferredSignature,
    Instance,
    NoneType,
    TupleType,
    TypeInferenceStrategy,
    TypeInfo,
    TypeSystem,
    UnionType,
)
from tests.fixtures.types.subtyping import Sub, Super


def __dummy(x: int, y: int) -> int:
    return x * y  # pragma: no cover


def __func_1(x: int) -> int:
    return x  # pragma: no cover


def __typed_dummy(a: int, b: float, c) -> str:
    return f"int {a} float {b} any {c}"  # pragma: no cover


def __untyped_dummy(a, b, c):
    return f"int {a} float {b} any {c}"  # pragma: no cover


def __union_dummy(a: int | float, b: int | float) -> int | float:
    return a + b  # pragma: no cover


def __return_tuple() -> tuple[int, int]:
    return 23, 42  # pragma: no cover


def __return_tuple_no_annotation():
    return 23, 42  # pragma: no cover


class __TypedDummy:
    def __init__(self, a: Any) -> None:
        self.__a = a  # pragma: no cover

    def get_a(self) -> Any:
        return self.__a  # pragma: no cover


class __UntypedDummy:
    def __init__(self, a):
        self.__a = a  # pragma: no cover

    def get_a(self):
        return self.__a  # pragma: no cover


@pytest.fixture
def signature():
    return inspect.signature(__dummy)


@pytest.fixture
def inferred_signature(signature):
    return InferredSignature(
        signature=signature,
        parameters={"x": Instance(TypeInfo(int)), "y": Instance(TypeInfo(int))},
        return_type=Instance(TypeInfo(int)),
    )


@pytest.mark.parametrize(
    "func, infer_types, expected_parameters, expected_return",
    [
        pytest.param(
            __func_1,
            TypeInferenceStrategy.TYPE_HINTS,
            {"x": Instance(TypeInfo(int))},
            Instance(TypeInfo(int)),
        ),
        pytest.param(__func_1, TypeInferenceStrategy.NONE, {"x": AnyType()}, AnyType()),
        pytest.param(
            __typed_dummy,
            TypeInferenceStrategy.TYPE_HINTS,
            {
                "a": Instance(TypeInfo(int)),
                "b": Instance(TypeInfo(float)),
                "c": AnyType(),
            },
            Instance(TypeInfo(str)),
        ),
        pytest.param(
            __untyped_dummy,
            TypeInferenceStrategy.TYPE_HINTS,
            {"a": AnyType(), "b": AnyType(), "c": AnyType()},
            AnyType(),
        ),
        pytest.param(
            __union_dummy,
            TypeInferenceStrategy.TYPE_HINTS,
            {
                "a": UnionType((Instance(TypeInfo(int)), Instance(TypeInfo(float)))),
                "b": UnionType((Instance(TypeInfo(int)), Instance(TypeInfo(float)))),
            },
            UnionType((Instance(TypeInfo(int)), Instance(TypeInfo(float)))),
        ),
        pytest.param(
            __return_tuple,
            TypeInferenceStrategy.TYPE_HINTS,
            {},
            TupleType((Instance(TypeInfo(int)), Instance(TypeInfo(int)))),
        ),
        pytest.param(
            __return_tuple_no_annotation,
            TypeInferenceStrategy.TYPE_HINTS,
            {},
            AnyType(),
        ),
        pytest.param(
            __TypedDummy, TypeInferenceStrategy.TYPE_HINTS, {"a": AnyType()}, NoneType()
        ),
        pytest.param(
            __UntypedDummy,
            TypeInferenceStrategy.TYPE_HINTS,
            {"a": AnyType()},
            AnyType(),
        ),
        pytest.param(
            __TypedDummy, TypeInferenceStrategy.NONE, {"a": AnyType()}, AnyType()
        ),
        pytest.param(
            __UntypedDummy, TypeInferenceStrategy.NONE, {"a": AnyType()}, AnyType()
        ),
    ],
)
def test_infer_type_info(func, infer_types, expected_parameters, expected_return):
    type_system = TypeSystem()
    result = type_system.infer_type_info(func, infer_types)
    assert result.parameters == expected_parameters
    assert result.return_type == expected_return


@pytest.mark.parametrize(
    "hint,expected",
    [
        (list, Instance(TypeInfo(list))),
        (
            list[int],
            Instance(TypeInfo(list), (Instance(TypeInfo(int)),)),
        ),
        (
            List[int],
            Instance(TypeInfo(list), (Instance(TypeInfo(int)),)),
        ),
        (
            set[int],
            Instance(TypeInfo(set), (Instance(TypeInfo(int)),)),
        ),
        (
            Set[int],
            Instance(TypeInfo(set), (Instance(TypeInfo(int)),)),
        ),
        (
            dict[int, str],
            Instance(
                TypeInfo(dict),
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            Dict[int, str],
            Instance(
                TypeInfo(dict),
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            int | str,
            UnionType(
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            Union[int, str],
            UnionType(
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            Union[int, type(None)],
            UnionType(
                (Instance(TypeInfo(int)), NoneType()),
            ),
        ),
        (
            tuple[int, str],
            TupleType(
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            Tuple[int, str],
            TupleType(
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            tuple,
            TupleType((AnyType(),), unknown_size=True),
        ),
        (
            Any,
            AnyType(),
        ),
        (
            type(None),
            NoneType(),
        ),
    ],
)
def test_convert_type_hints(hint, expected):
    graph = TypeSystem()
    assert graph.convert_type_hint(hint) == expected
    assert repr(graph.convert_type_hint(hint)) == repr(expected)


@pytest.fixture(scope="module")
def subtyping_cluster():
    return generate_test_cluster("tests.fixtures.types.subtyping")


@pytest.mark.parametrize(
    "left_hint,right_hint,result",
    [
        (int, int, True),
        (int, str, False),
        (str, str, True),
        (str, tuple[str], False),
        (tuple, int, False),
        (int, type(None), False),
        (tuple[str], tuple[str, int], False),
        (tuple[int, str], tuple[int, str], True),
        (tuple[int, int], tuple[int, str], False),
        (tuple[Any, Any], tuple[int, int], True),
        (tuple[int, int], tuple[Any, Any], True),
        (tuple[Any, Any], tuple[Any, Any], True),
        (tuple[int, str], tuple[int, str] | str, True),
        (int, int | str, True),
        (int | str, str, False),
        (float, int | str, False),
        (int | str, int | str, True),
        (int | str | float, int | str, False),
        (int | str, int | str | float, True),
        (int, Union[int, None], True),
        (Sub, Super, True),
        (Sub, Super | int, True),
        (Sub, Sub | int, True),
        (Sub, object | int, True),
        (object, Sub | int, False),
        (Sub, float | int, False),
        (Super, Sub, False),
        (Sub, Sub, True),
        (Super, Super, True),
    ],
)
def test_is_subtype(subtyping_cluster, left_hint, right_hint, result):
    type_system = subtyping_cluster.type_system
    left = type_system.convert_type_hint(left_hint)
    right = type_system.convert_type_hint(right_hint)
    assert type_system.is_subtype(left, right) is result


@pytest.mark.parametrize(
    "subclass,superclass,result",
    [
        (int, int, True),
        (int, str, False),
        (Sub, Super, True),
        (Super, Sub, False),
    ],
)
def test_is_subclass(subtyping_cluster, subclass, superclass, result):
    type_system = subtyping_cluster.type_system
    assert (
        type_system.is_subclass(
            type_system.to_type_info(subclass), type_system.to_type_info(superclass)
        )
        == result
    )


@pytest.mark.parametrize(
    "kind,type_,result",
    [
        (inspect.Parameter.VAR_POSITIONAL, None, list[Any]),
        (inspect.Parameter.VAR_POSITIONAL, str, list[str]),
        (inspect.Parameter.VAR_KEYWORD, None, dict[str, Any]),
        (inspect.Parameter.VAR_KEYWORD, str, dict[str, str]),
        (inspect.Parameter.POSITIONAL_OR_KEYWORD, dict, dict),
    ],
)
def test_wrap_var_param_type(kind, type_, result):
    system = TypeSystem()
    proper = system.convert_type_hint(type_)
    assert system.wrap_var_param_type(proper, kind) == system.convert_type_hint(result)
