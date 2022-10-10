#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from typing import Any, List, Set, Tuple, TypeVar, Union
from unittest import mock

import pytest

import pynguin.configuration as config
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import (
    UNSUPPORTED,
    AnyType,
    InferredSignature,
    Instance,
    NoneType,
    TupleType,
    TypeInfo,
    TypeSystem,
    UnionType,
    is_collection_type,
    is_primitive_type,
)
from pynguin.configuration import TypeInferenceStrategy
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.typetracing import ProxyKnowledge
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
                "a": UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(int)))),
                "b": UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(int)))),
            },
            UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(int)))),
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


A = TypeVar("A")


@pytest.mark.parametrize(
    "hint,expected",
    [
        (list, Instance(TypeInfo(list), (AnyType(),))),
        (
            list[int],
            Instance(TypeInfo(list), (Instance(TypeInfo(int)),)),
        ),
        (List[int], Instance(TypeInfo(list), (Instance(TypeInfo(int)),))),
        (
            set[int],
            Instance(TypeInfo(set), (Instance(TypeInfo(int)),)),
        ),
        (
            set,
            Instance(TypeInfo(set), (AnyType(),)),
        ),
        (Set[int], Instance(TypeInfo(set), (Instance(TypeInfo(int)),))),
        (
            set[int],
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
            dict[int, str],
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
                (NoneType(), Instance(TypeInfo(int))),
            ),
        ),
        (
            tuple[int, str],
            TupleType(
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            tuple[int, str],
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
        (A, AnyType()),
        (
            List,
            Instance(TypeInfo(list), (AnyType(),)),
        ),
        (Tuple, TupleType((AnyType(),), unknown_size=True)),
    ],
)
def test_convert_type_hints(hint, expected):
    graph = TypeSystem()
    assert graph.convert_type_hint(hint) == expected
    assert repr(graph.convert_type_hint(hint)) == repr(expected)


@pytest.mark.parametrize(
    "hint, expected",
    [(A, UNSUPPORTED), (list[A], Instance(TypeInfo(list), (UNSUPPORTED,)))],
)
def test_convert_type_hint_unsupported(hint, expected):
    ts = TypeSystem()
    ts.convert_type_hint(hint, unsupported=UNSUPPORTED)


def test_unsupported_str():
    assert str(UNSUPPORTED) == "<?>"


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
        (int, type(None), False, False),
        (type(None), int, False, False),
        (tuple[str], tuple[str, int], False, False),
        (tuple[int, str], tuple[int, str], True, True),
        (tuple[int, int], tuple[int, str], False, False),
        (tuple[Any, Any], tuple[int, int], True, True),
        (tuple[int, int], tuple[Any, Any], True, True),
        (tuple[Any, Any], tuple[Any, Any], True, True),
        (tuple[int, str], tuple[int, str] | str, True, True),
        (tuple[bool, bool], tuple[int, int], True, True),
        (tuple[int, int], tuple[bool, bool], False, False),
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
        (list[int], list[bool], False, False),
        (list[int], list[int], True, True),
        (set[int], set[bool], False, False),
        (set[bool], set[bool], True, True),
        (dict[str, int], dict[str, bool], False, False),
        (dict[int, int], dict[float, int], False, False),
        (dict[str, int], dict[str, int], True, True),
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
        (type(None) | int, "None | int"),
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
        (Instance(TypeInfo(list)), False),
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


@pytest.mark.parametrize(
    "symbol,types",
    [
        ("a", ("tests.fixtures.types.symbols.Foo", "tests.fixtures.types.symbols.Baz")),
        ("b", ("tests.fixtures.types.symbols.Bar",)),
        ("foo", ("tests.fixtures.types.symbols.Foo",)),
        (
            "bar",
            (
                "tests.fixtures.types.symbols.Foo",
                "tests.fixtures.types.symbols.Baz",
            ),
        ),
        ("not_defined", ()),
        (
            "__lt__",
            (
                "builtins.str",
                "builtins.bytes",
                "builtins.complex",
                "builtins.list",
                "builtins.set",
                "builtins.dict",
                "builtins.tuple",
            ),
        ),
        ("isspace", ("builtins.str", "builtins.bytes")),
        ("e", ("tests.fixtures.types.symbols.E",)),
        ("f", ("tests.fixtures.types.symbols.F",)),
        ("g", ("tests.fixtures.types.symbols.G",)),
    ],
)
def test_find_by_symbols(symbol, types):
    test_cluster = generate_test_cluster("tests.fixtures.types.symbols")
    tps = test_cluster.type_system
    assert test_cluster.type_system.find_by_symbol(symbol) == OrderedSet(
        [tps.find_type_info("" + t) for t in types]
    )


@pytest.mark.parametrize(
    "outside_of,expected_types",
    [
        (
            ("tests.fixtures.types.outside.Foo",),
            (
                "builtins.int",
                "builtins.str",
                "builtins.bool",
                "builtins.float",
                "builtins.bytes",
                "builtins.complex",
                "builtins.list",
                "builtins.set",
                "builtins.dict",
                "builtins.tuple",
                "builtins.object",
            ),
        ),
        (
            ("tests.fixtures.types.outside.Bar",),
            (
                "tests.fixtures.types.outside.Foo",
                "builtins.int",
                "builtins.str",
                "builtins.bool",
                "builtins.float",
                "builtins.bytes",
                "builtins.complex",
                "builtins.list",
                "builtins.set",
                "builtins.dict",
                "builtins.tuple",
                "builtins.object",
            ),
        ),
        (
            ("tests.fixtures.types.outside.Bar", "builtins.complex"),
            (
                "tests.fixtures.types.outside.Foo",
                "builtins.str",
                "builtins.bytes",
                "builtins.list",
                "builtins.set",
                "builtins.dict",
                "builtins.tuple",
                "builtins.object",
            ),
        ),
        (("builtins.object",), ()),
    ],
)
def test_get_type_outside_of(outside_of, expected_types):
    test_cluster = generate_test_cluster("tests.fixtures.types.outside")
    tps = test_cluster.type_system
    outside_set = OrderedSet(tps.find_type_info(t) for t in outside_of)
    assert set(tps.get_type_outside_of(outside_set)) == set(
        tps.find_type_info(t) for t in expected_types
    )


@pytest.mark.parametrize(
    "tp, expected",
    [
        (tuple, TupleType((AnyType(),), unknown_size=True)),
        (int, Instance(TypeInfo(int))),
    ],
)
def test_make_instance(tp, expected):
    tps = TypeSystem()
    type_info = tps.to_type_info(tp)
    assert tps.make_instance(type_info) == expected


@pytest.mark.parametrize(
    "tp, expected",
    [
        (Instance(TypeInfo(list)), Instance(TypeInfo(list), (AnyType(),))),
        (
            Instance(TypeInfo(list), (AnyType(), AnyType())),
            Instance(TypeInfo(list), (AnyType(),)),
        ),
        (Instance(TypeInfo(set)), Instance(TypeInfo(set), (AnyType(),))),
        (
            Instance(TypeInfo(set), (AnyType(), AnyType())),
            Instance(TypeInfo(set), (AnyType(),)),
        ),
        (Instance(TypeInfo(dict)), Instance(TypeInfo(dict), (AnyType(), AnyType()))),
        (
            Instance(TypeInfo(dict), (AnyType(), AnyType(), AnyType())),
            Instance(TypeInfo(dict), (AnyType(), AnyType())),
        ),
    ],
)
def test_fixup_generics(tp, expected):
    assert TypeSystem._fixup_known_generics(tp) == expected


def test_union_single_element():
    assert str(UnionType((NoneType(),))) == "None"


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, list, list[int]) for sym in InferredSignature._LIST_ELEMENT_SYMBOLS]
    + [(sym, set, set[int]) for sym in InferredSignature._SET_ELEMENT_SYMBOLS],
)
def test_guess_generic_types_list_set_from_elements(
    inferred_signature, symbol, typ, result
):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    knowledge.symbol_table[symbol].type_checks.add(int)
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
    ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, dict, dict[int, Any]) for sym in InferredSignature._DICT_KEY_SYMBOLS],
)
def test_guess_generic_types_dict_key_from_elements(
    inferred_signature, symbol, typ, result
):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    knowledge.symbol_table[symbol].type_checks.add(int)
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
    ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [
        (sym, dict, dict[int, Any])
        for sym in InferredSignature._DICT_KEY_FROM_ARGUMENT_TYPES
    ],
)
def test_guess_generic_types_dict_key_from_arguments(
    inferred_signature, symbol, typ, result
):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    knowledge.symbol_table[symbol].arg_types[0].add(int)
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
    ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, dict, dict[Any, int]) for sym in InferredSignature._DICT_VALUE_SYMBOLS],
)
def test_guess_generic_types_dict_value_from_elements(
    inferred_signature, symbol, typ, result
):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    knowledge.symbol_table[symbol].type_checks.add(int)
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
    ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [
        (sym, dict, dict[Any, int])
        for sym in InferredSignature._DICT_VALUE_FROM_ARGUMENT_TYPES
    ],
)
def test_guess_generic_types_dict_value_from_arguments(
    inferred_signature, symbol, typ, result
):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    knowledge.symbol_table[symbol].arg_types[1].add(int)
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
    ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [
        (sym, list, list[int])
        for sym in InferredSignature._LIST_ELEMENT_FROM_ARGUMENT_TYPES
    ]
    + [
        (sym, set, set[int])
        for sym in InferredSignature._SET_ELEMENT_FROM_ARGUMENT_TYPES
    ],
)
def test_guess_generic_types_list_set_from_arguments(
    inferred_signature, symbol, typ, result
):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    knowledge.symbol_table[symbol].arg_types[0].add(int)
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
    ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize("inp, result", [(int, int), (Any, Any)])
def test_guess_generic_types_falltrough(inferred_signature, inp, result):
    assert inferred_signature._guess_generic_parameters_for_builtins(
        inferred_signature.type_system.convert_type_hint(inp), None, None
    ) == inferred_signature.type_system.convert_type_hint(result)


def test_choose_type_or_negate_empty(inferred_signature):
    assert inferred_signature._choose_type_or_negate(OrderedSet()) is None


def test_choose_type_or_negate(inferred_signature):
    config.configuration.test_creation.negate_type = 0.0
    assert inferred_signature._choose_type_or_negate(
        OrderedSet((inferred_signature.type_system.to_type_info(int),))
    ) == inferred_signature.type_system.convert_type_hint(int)


def test_choose_type_or_negate_negate(inferred_signature):
    config.configuration.test_creation.negate_type = 1.0
    assert inferred_signature._choose_type_or_negate(
        OrderedSet((inferred_signature.type_system.to_type_info(int),))
    ) != inferred_signature.type_system.convert_type_hint(int)


def test_choose_type_or_negate_empty_2(inferred_signature):
    config.configuration.test_creation.negate_type = 1.0
    with mock.patch.object(
        inferred_signature.type_system, "get_type_outside_of"
    ) as outside_mock:
        outside_mock.return_value = OrderedSet()
        assert inferred_signature._choose_type_or_negate(
            OrderedSet((inferred_signature.type_system.to_type_info(object),))
        ) == inferred_signature.type_system.convert_type_hint(object)


def test_update_guess(inferred_signature):
    inferred_signature._update_guess("x", None)
    assert "x" not in inferred_signature.current_guessed_parameters


def test_update_guess_single(inferred_signature):
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(int)
    )
    assert inferred_signature.current_guessed_parameters["x"] == [
        inferred_signature.type_system.convert_type_hint(int)
    ]


def test_update_guess_multi(inferred_signature):
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(int)
    )
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(int)
    )
    assert inferred_signature.current_guessed_parameters["x"] == [
        inferred_signature.type_system.convert_type_hint(int)
    ]


def test_update_guess_multi_drop(inferred_signature):
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(int)
    )
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(float)
    )
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(str)
    )
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(bytes)
    )
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(bool)
    )
    inferred_signature._update_guess(
        "x", inferred_signature.type_system.convert_type_hint(complex)
    )
    assert inferred_signature.current_guessed_parameters["x"] == [
        inferred_signature.type_system.convert_type_hint(tp)
        for tp in [float, str, bytes, bool, complex]
    ]


@pytest.mark.parametrize(
    "symbol,kind",
    [
        ("__getitem__", inspect.Parameter.VAR_KEYWORD),
        ("__iter__", inspect.Parameter.VAR_POSITIONAL),
    ],
)
def test__guess_parameter_type(inferred_signature, symbol, kind):
    knowledge = ProxyKnowledge("ROOT")
    assert knowledge.symbol_table[symbol]
    with mock.patch.object(inferred_signature, "_guess_parameter_type_from") as guess:
        inferred_signature._guess_parameter_type(knowledge, kind)
        guess.assert_called_with(knowledge.symbol_table[symbol])


@pytest.mark.parametrize(
    "kind", [inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL]
)
def test__guess_parameter_type_2(inferred_signature, kind):
    knowledge = ProxyKnowledge("ROOT")
    assert inferred_signature._guess_parameter_type(knowledge, kind) is None


def test__guess_parameter_type_3(inferred_signature):
    knowledge = ProxyKnowledge("ROOT")
    with mock.patch.object(inferred_signature, "_guess_parameter_type_from") as guess:
        inferred_signature._guess_parameter_type(knowledge, 42)
        guess.assert_called_with(knowledge)


def test_from_symbol_table(inferred_signature):
    knowledge = ProxyKnowledge("ROOT")
    assert knowledge.symbol_table["foo"]
    assert inferred_signature._from_symbol_table(knowledge) is None


def test_from_symbol_table_2(inferred_signature):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = ProxyKnowledge("ROOT")
    assert knowledge.symbol_table["foo"]
    inferred_signature.type_system._symbol_map["foo"].add(
        inferred_signature.type_system.to_type_info(int)
    )
    assert inferred_signature._from_symbol_table(
        knowledge
    ) == inferred_signature.type_system.convert_type_hint(int)


def test_from_symbol_table_3(inferred_signature):
    config.configuration.test_creation.negate_type = 0.0
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        knowledge = ProxyKnowledge("ROOT")
        knowledge.symbol_table["__eq__"].arg_types[0].add(int)
        assert inferred_signature._from_symbol_table(
            knowledge
        ) == inferred_signature.type_system.convert_type_hint(int)


def test_from_symbol_table_4(inferred_signature):
    config.configuration.test_creation.negate_type = 1.0
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        knowledge = ProxyKnowledge("ROOT")
        knowledge.symbol_table["__eq__"].arg_types[0].add(int)
        assert inferred_signature._from_symbol_table(
            knowledge
        ) != inferred_signature.type_system.convert_type_hint(int)


@pytest.mark.parametrize(
    "numeric,subtypes",
    [
        (complex, [complex, float, int, bool]),
        (float, [float, int, bool]),
        (int, [int, bool]),
        (bool, [bool]),
    ],
)
def test_numeric_tower(type_system, numeric, subtypes):
    assert type_system.numeric_tower[type_system.convert_type_hint(numeric)] == [
        type_system.convert_type_hint(typ) for typ in subtypes
    ]
