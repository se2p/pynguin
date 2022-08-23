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
    is_collection_type,
    is_primitive_type,
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
def inferred_signature(signature, type_system):
    return InferredSignature(
        signature=signature,
        original_parameters={
            "x": type_system.convert_type_hint(int),
            "y": type_system.convert_type_hint(int),
        },
        original_return_type=type_system.convert_type_hint(int),
        type_system=type_system,
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
    assert result.original_parameters == expected_parameters
    assert result.return_type == expected_return


@pytest.mark.parametrize(
    "hint,expected",
    [
        (list, Instance(TypeInfo(list), (AnyType(),))),
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
            set,
            Instance(TypeInfo(set), (AnyType(),)),
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
    "left_hint,right_hint,subtype_result, maybe_subtype_result",
    [
        (int, int, True, True),
        (int, str, False, False),
        (str, str, True, True),
        (str, tuple[str], False, False),
        (tuple, int, False, False),
        (int, type(None), False, False),
        (type(None), type(None), True, True),
        (tuple[str], tuple[str, int], False, False),
        (tuple[int, str], tuple[int, str], True, True),
        (tuple[int, int], tuple[int, str], False, False),
        (tuple[Any, Any], tuple[int, int], True, True),
        (tuple[int, int], tuple[Any, Any], True, True),
        (tuple[Any, Any], tuple[Any, Any], True, True),
        (tuple[int, str], tuple[int, str] | str, True, True),
        (int, int | str, True, True),
        (int | str, str, False, True),
        (float, int | str, False, False),
        (int | str, int | str, True, True),
        (int | str | float, int | str, False, True),
        (int | str, int | str | float, True, True),
        (int, Union[int, None], True, True),
        (Sub, Super, True, True),
        (Sub, Super | int, True, True),
        (Sub, Sub | int, True, True),
        (Sub, object | int, True, True),
        (object, Sub | int, False, False),
        (Sub, float | int, False, False),
        (Super, Sub, False, False),
        (Sub, Sub, True, True),
        (Super, Super, True, True),
        (tuple[int | str | bytes, int | str | bytes], tuple[int, int], False, True),
        (int | float, float, True, True),
        (int | str, float, False, True),
        (float | bool, int, False, True),
    ],
)
def test_is_subtype(
    subtyping_cluster, left_hint, right_hint, subtype_result, maybe_subtype_result
):
    type_system = subtyping_cluster.type_system
    left = type_system.convert_type_hint(left_hint)
    right = type_system.convert_type_hint(right_hint)
    assert type_system.is_subtype(left, right) is subtype_result
    assert type_system.is_maybe_subtype(left, right) is maybe_subtype_result


@pytest.mark.parametrize(
    "hint, hint_str",
    [
        (type(None), "None"),
        (type(None) | int, "Union[None, int]"),
        (str, "str"),
        (Any, "Any"),
        (tuple[int, int], "tuple[int, int]"),
        (list[int], "list[int]"),
    ],
)
def test_str_proper_type(type_system, hint, hint_str):
    proper = type_system.convert_type_hint(hint)
    assert str(proper) == hint_str


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


def test_inferred_signature_identity(type_system):
    assert InferredSignature(None, None, {}, type_system) != InferredSignature(
        None, None, {}, type_system
    )


def test_get_parameter_types_consistent(inferred_signature):
    assert inferred_signature.get_parameter_types({inferred_signature: 42}) == 42


def test_get_parameter_types_consistent_2(inferred_signature):
    cache = {}
    assert inferred_signature.get_parameter_types(cache)
    assert cache


@pytest.mark.parametrize(
    "left,right,result",
    [
        (AnyType(), AnyType(), True),
        (AnyType(), NoneType(), False),
        (NoneType(), NoneType(), True),
        (NoneType(), AnyType(), False),
        (TupleType((AnyType(),)), TupleType((AnyType(),)), True),
        (TupleType((AnyType(),)), TupleType((NoneType(),)), False),
        (Instance(TypeInfo(int), ()), Instance(TypeInfo(int), ()), True),
        (Instance(TypeInfo(int), ()), AnyType(), False),
        (UnionType((AnyType(),)), UnionType((AnyType(),)), True),
        (UnionType((AnyType(),)), UnionType((NoneType(),)), False),
    ],
)
def test_types_equality_self(left, right, result):
    assert (left == right) == result


@pytest.mark.parametrize(
    "typ,result",
    [
        (AnyType(), False),
        (TupleType((AnyType(),)), False),
        (Instance(TypeInfo(int)), True),
        (Instance(TypeInfo(float)), True),
        (Instance(TypeInfo(str)), True),
        (Instance(TypeInfo(complex)), True),
        (Instance(TypeInfo(bool)), True),
        (Instance(TypeInfo(bytes)), True),
        (Instance(TypeInfo(type)), False),
        (UnionType((AnyType(),)), False),
        (NoneType(), False),
    ],
)
def test_is_primitive_type(typ, result):
    assert typ.accept(is_primitive_type) is result


@pytest.mark.parametrize(
    "typ,result",
    [
        (AnyType(), False),
        (TupleType((AnyType(),)), True),
        (Instance(TypeInfo(list)), True),
        (Instance(TypeInfo(set)), True),
        (Instance(TypeInfo(dict)), True),
        (Instance(TypeInfo(int)), False),
        (UnionType((AnyType(),)), False),
        (NoneType(), False),
    ],
)
def test_is_collection_type(typ, result):
    assert typ.accept(is_collection_type) is result
