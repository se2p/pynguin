#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# ruff: noqa: PLC2701

import inspect
import operator
import re
from typing import Any, TypeVar, Union
from unittest import mock

import pytest

import pynguin.configuration as config
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.type_inference import HintInference, NoInference
from pynguin.analyses.typesystem import (
    _DICT_KEY_ATTRIBUTES,
    _DICT_KEY_FROM_ARGUMENT_TYPES,
    _DICT_VALUE_ATTRIBUTES,
    _DICT_VALUE_FROM_ARGUMENT_TYPES,
    _LIST_ELEMENT_ATTRIBUTES,
    _LIST_ELEMENT_FROM_ARGUMENT_TYPES,
    _SET_ELEMENT_ATTRIBUTES,
    _SET_ELEMENT_FROM_ARGUMENT_TYPES,
    UNSUPPORTED,
    AnyType,
    InferredSignature,
    Instance,
    NoneType,
    StringSubtype,
    TupleType,
    TypeInfo,
    TypeSystem,
    UnionType,
    _is_partial_type_match,
    is_collection_type,
    is_primitive_type,
)
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.typetracing import UsageTraceNode
from tests.fixtures.types.subtyping import Sub, Super


def __dummy(x: int, y: int) -> int:  # noqa: FURB118
    return x * y  # pragma: no cover


def __func_1(x: int) -> int:
    return x  # pragma: no cover


def __typed_dummy(a: int, b: float, c) -> str:
    return f"int {a} float {b} any {c}"  # pragma: no cover


def __untyped_dummy(a, b, c):
    return f"int {a} float {b} any {c}"  # pragma: no cover


def __union_dummy(  # noqa: FURB118
    a: int | float,  # noqa: PYI041
    b: int | float,  # noqa: PYI041
) -> int | float:
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
            HintInference(),
            {"x": Instance(TypeInfo(int))},
            Instance(TypeInfo(int)),
        ),
        pytest.param(__func_1, NoInference(), {"x": AnyType()}, AnyType()),
        pytest.param(
            __typed_dummy,
            HintInference(),
            {
                "a": Instance(TypeInfo(int)),
                "b": Instance(TypeInfo(float)),
                "c": AnyType(),
            },
            Instance(TypeInfo(str)),
        ),
        pytest.param(
            __untyped_dummy,
            HintInference(),
            {"a": AnyType(), "b": AnyType(), "c": AnyType()},
            AnyType(),
        ),
        pytest.param(
            __union_dummy,
            HintInference(),
            {
                "a": UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(int)))),
                "b": UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(int)))),
            },
            UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(int)))),
        ),
        pytest.param(
            __return_tuple,
            HintInference(),
            {},
            TupleType((Instance(TypeInfo(int)), Instance(TypeInfo(int)))),
        ),
        pytest.param(
            __return_tuple_no_annotation,
            HintInference(),
            {},
            AnyType(),
        ),
        pytest.param(
            __TypedDummy.__init__,
            HintInference(),
            {"a": AnyType()},
            NoneType(),
        ),
        pytest.param(
            __UntypedDummy.__init__,
            HintInference(),
            {"a": AnyType()},
            AnyType(),
        ),
        pytest.param(
            __TypedDummy.__init__,
            NoInference(),
            {"a": AnyType()},
            AnyType(),
        ),
        pytest.param(
            __UntypedDummy.__init__,
            NoInference(),
            {"a": AnyType()},
            AnyType(),
        ),
    ],
)
def test_infer_type_info(func, infer_types, expected_parameters, expected_return):
    type_system = TypeSystem()
    result = type_system.infer_type_info(func, type_inference_provider=infer_types)
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
        (
            set[int],
            Instance(TypeInfo(set), (Instance(TypeInfo(int)),)),
        ),
        (
            set,
            Instance(TypeInfo(set), (AnyType(),)),
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
            Union[int, str],  # noqa: UP007
            UnionType(
                (Instance(TypeInfo(int)), Instance(TypeInfo(str))),
            ),
        ),
        (
            Union[int, type(None)],  # noqa: UP007
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
def test_convert_type_hint_unsupported(hint, expected):  # noqa: ARG001
    ts = TypeSystem()
    ts.convert_type_hint(hint, unsupported=UNSUPPORTED)


def test_unsupported_str():
    assert str(UNSUPPORTED) == "<?>"


@pytest.fixture(scope="module")
def subtyping_cluster():
    config.configuration.generator_selection.generator_selection_algorithm = (
        config.Selection.RANK_SELECTION
    )
    config.configuration.pynguinml.ml_testing_enabled = False
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
        (int, Union[int, None], True, True),  # noqa: UP007
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
        (Any, int, True, True),
        (int, Any, True, True),
        (Any, Any, True, True),
    ],
)
def test_is_subtype(subtyping_cluster, left_hint, right_hint, subtype_result, maybe_subtype_result):
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
    assert test_cluster.type_system.find_by_attribute(symbol) == OrderedSet([
        tps.find_type_info("" + t) for t in types
    ])


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
    assert set(tps.get_type_outside_of(outside_set)) == {
        tps.find_type_info(t) for t in expected_types
    }


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
    [(sym, list, list[int]) for sym in _LIST_ELEMENT_ATTRIBUTES]
    + [(sym, set, set[int]) for sym in _SET_ELEMENT_ATTRIBUTES],
)
def test_guess_generic_types_list_set_from_elements(inferred_signature, symbol, typ, result):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    knowledge.children[symbol].type_checks.add(int)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        assert inferred_signature._guess_generic_type_parameters_for_builtins(
            inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
        ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, dict, dict[int, Any]) for sym in _DICT_KEY_ATTRIBUTES],
)
def test_guess_generic_types_dict_key_from_elements(inferred_signature, symbol, typ, result):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    knowledge.children[symbol].type_checks.add(int)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        assert inferred_signature._guess_generic_type_parameters_for_builtins(
            inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
        ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, dict, dict[int, Any]) for sym in _DICT_KEY_FROM_ARGUMENT_TYPES],
)
def test_guess_generic_types_dict_key_from_arguments(inferred_signature, symbol, typ, result):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    knowledge.children[symbol].arg_types[0].add(int)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        assert inferred_signature._guess_generic_type_parameters_for_builtins(
            inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
        ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, dict, dict[Any, int]) for sym in _DICT_VALUE_ATTRIBUTES],
)
def test_guess_generic_types_dict_value_from_elements(inferred_signature, symbol, typ, result):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    knowledge.children[symbol].type_checks.add(int)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        assert inferred_signature._guess_generic_type_parameters_for_builtins(
            inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
        ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, dict, dict[Any, int]) for sym in _DICT_VALUE_FROM_ARGUMENT_TYPES],
)
def test_guess_generic_types_dict_value_from_arguments(inferred_signature, symbol, typ, result):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    knowledge.children[symbol].arg_types[1].add(int)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        assert inferred_signature._guess_generic_type_parameters_for_builtins(
            inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
        ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize(
    "symbol, typ, result",
    [(sym, list, list[int]) for sym in _LIST_ELEMENT_FROM_ARGUMENT_TYPES]
    + [(sym, set, set[int]) for sym in _SET_ELEMENT_FROM_ARGUMENT_TYPES],
)
def test_guess_generic_types_list_set_from_arguments(inferred_signature, symbol, typ, result):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    knowledge.children[symbol].arg_types[0].add(int)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        assert inferred_signature._guess_generic_type_parameters_for_builtins(
            inferred_signature.type_system.convert_type_hint(typ), knowledge, 0
        ) == inferred_signature.type_system.convert_type_hint(result)


@pytest.mark.parametrize("inp, result", [(int, int), (Any, Any)])
def test_guess_generic_types_falltrough(inferred_signature, inp, result):
    assert inferred_signature._guess_generic_type_parameters_for_builtins(
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
    with mock.patch.object(inferred_signature.type_system, "get_type_outside_of") as outside_mock:
        outside_mock.return_value = OrderedSet()
        assert inferred_signature._choose_type_or_negate(
            OrderedSet((inferred_signature.type_system.to_type_info(object),))
        ) == inferred_signature.type_system.convert_type_hint(object)


def test_update_guess(inferred_signature):
    inferred_signature._update_guess("x", None)
    assert "x" not in inferred_signature.current_guessed_parameters


def test_update_guess_single(inferred_signature):
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(int))
    assert inferred_signature.current_guessed_parameters["x"] == [
        inferred_signature.type_system.convert_type_hint(int)
    ]


def test_update_guess_multi(inferred_signature):
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(int))
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(int))
    assert inferred_signature.current_guessed_parameters["x"] == [
        inferred_signature.type_system.convert_type_hint(int)
    ]


def test_update_guess_multi_drop(inferred_signature):
    config.configuration.test_creation.type_tracing_kept_guesses = 5
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(int))
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(float))
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(str))
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(bytes))
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(bool))
    inferred_signature._update_guess("x", inferred_signature.type_system.convert_type_hint(complex))
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
    knowledge = UsageTraceNode("ROOT")
    assert knowledge.children[symbol] is not None
    with mock.patch.object(inferred_signature, "_guess_parameter_type_from") as guess:
        inferred_signature._guess_parameter_type(knowledge, kind)
        guess.assert_called_with(knowledge.children[symbol])


@pytest.mark.parametrize("kind", [inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL])
def test__guess_parameter_type_2(inferred_signature, kind):
    knowledge = UsageTraceNode("ROOT")
    assert inferred_signature._guess_parameter_type(knowledge, kind) is None


def test__guess_parameter_type_3(inferred_signature):
    knowledge = UsageTraceNode("ROOT")
    with mock.patch.object(inferred_signature, "_guess_parameter_type_from") as guess:
        inferred_signature._guess_parameter_type(knowledge, 42)
        guess.assert_called_with(knowledge)


def test_from_symbol_table(inferred_signature):
    knowledge = UsageTraceNode("ROOT")
    assert knowledge.children["foo"] is not None
    assert inferred_signature._from_attr_table(knowledge) is None


def test_from_symbol_table_2(inferred_signature):
    config.configuration.test_creation.negate_type = 0.0
    knowledge = UsageTraceNode("ROOT")
    assert knowledge.children["foo"] is not None
    inferred_signature.type_system._attribute_map["foo"].add(
        inferred_signature.type_system.to_type_info(int)
    )
    assert inferred_signature._from_attr_table(
        knowledge
    ) == inferred_signature.type_system.convert_type_hint(int)


def test_from_symbol_table_3(inferred_signature):
    config.configuration.test_creation.negate_type = 0.0
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        knowledge = UsageTraceNode("ROOT")
        knowledge.children["__eq__"].arg_types[0].add(int)
        assert inferred_signature._from_attr_table(
            knowledge
        ) == inferred_signature.type_system.convert_type_hint(int)


def test_from_symbol_table_4(inferred_signature):
    config.configuration.test_creation.negate_type = 1.0
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        knowledge = UsageTraceNode("ROOT")
        knowledge.children["__eq__"].arg_types[0].add(int)
        assert inferred_signature._from_attr_table(
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


@pytest.mark.parametrize(
    "left,right,result",
    [
        (int, int, "int"),
        (tuple[int, int], tuple[int, str], "tuple"),
        (dict[int, int], dict[bool, str], "dict"),
        (int | bool, bool | str | float, "bool"),
        (bool | float, bool | str | float, "bool | float"),
        (int, int | str | float, "int"),
        (int | str | float, int | str | float, "float | int | str"),
        (int | str, str, "str"),
        (list[bool], list | bool, "list"),
        (bool, list | bool, "bool"),
        (type(None), type(None), "None"),
    ],
)
def test_partial_type_match(type_system, left, right, result):
    match = _is_partial_type_match(
        type_system.convert_type_hint(left), type_system.convert_type_hint(right)
    )
    assert str(match) == result


@pytest.mark.parametrize(
    "left,right",
    [
        (int | float, bool | str),
        (int | str, bool),
        (dict[int, int], list),
        (int, bool),
        (Any, bool),
        (bool, Any),
        (type(None), str),
        (str, type(None)),
    ],
)
def test_no_partial_type_match(type_system, left, right):
    match = _is_partial_type_match(
        type_system.convert_type_hint(left), type_system.convert_type_hint(right)
    )
    assert match is None


def test_to_type_info_union_type(subtyping_cluster):
    type_system = subtyping_cluster.type_system
    type_system.to_type_info(float | int)


def test__guess_parameter_type_with_type_knowledge_simple(inferred_signature):
    config.configuration.test_creation.negate_type = 0
    knowledge = UsageTraceNode("ROOT")
    kind = ""  # not inspect.Parameter.VAR_KEYWORD or inspect.Parameter.VAR_POSITIONAL
    knowledge.type_checks.add(float)
    expected = Instance(TypeInfo(float))
    actual = inferred_signature._guess_parameter_type(knowledge, kind)
    assert actual == expected


def pick_0_generator():
    while True:
        yield 0


def pick_1_generator():
    while True:
        yield 0
        yield 1
        yield 0


pick_1 = pick_1_generator()
pick_0 = pick_0_generator()


@pytest.mark.parametrize(
    "pick, expected_type",
    [
        (pick_0, Instance(TypeInfo(float))),
        (pick_1, Instance(TypeInfo(int))),
    ],
)
def test__guess_parameter_type_with_type_knowledge(inferred_signature, pick, expected_type):
    config.configuration.test_creation.negate_type = 0
    knowledge = UsageTraceNode("ROOT")
    kind = ""  # not inspect.Parameter.VAR_KEYWORD or inspect.Parameter.VAR_POSITIONAL
    knowledge.type_checks.add(float | int)

    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = lambda x: x[next(pick)]  # noqa: FURB118
        actual = inferred_signature._guess_parameter_type(knowledge, kind)
        assert actual == expected_type


def test_string_subtype():
    string_subtype = StringSubtype(re.compile(r"^bar"))
    assert str(string_subtype) == "StringSubtype(re.compile('^bar'))"


@pytest.mark.xfail(reason="Not implemented yet")
def test_is_subtype_string_subtype(subtyping_cluster):
    type_system = subtyping_cluster.type_system
    left = StringSubtype(re.compile(r"^bar"))
    right = StringSubtype(re.compile(r"^bar"))
    assert type_system.is_subtype(left, right) is True
    assert type_system.is_maybe_subtype(left, right) is True


def test__from_str_values_empty():
    knowledge = UsageTraceNode("ROOT")
    assert InferredSignature._from_str_values(knowledge) is None


def _make_usage_trace_with_strings(strings_by_attr):
    root = UsageTraceNode("ROOT")
    for attr, strings in strings_by_attr.items():
        root.children[attr].children["__call__"].arg_values[0].update(strings)
    return root


def test__from_str_values():
    knowledge = _make_usage_trace_with_strings({"startswith": {"bar"}})
    assert InferredSignature._from_str_values(knowledge) == StringSubtype(re.compile(r"^(?:bar)"))


any_distance = config.configuration.generator_selection.generator_any_distance


@pytest.mark.parametrize(
    "left_hint,right_hint,subtype_distance",
    [
        # basic
        (int, int, 0),
        (int, str, None),
        # none
        (type(None), int, None),
        (int, type(None), None),
        # any
        (Any, int, any_distance),
        (int, Any, any_distance),
        # builtins
        (complex, int, 2),
        (float, int, 1),
        (int, bool, 1),
        (object, str, 1),
        (object, bytes, 1),
        (object, list, 1),
        (object, tuple, None),  # To match a tuple, both must be a tuple
        (tuple, Any, None),  # To match a tuple, both must be a tuple
        (object, set, 1),
        (object, dict, 1),
        (object, int, 1),
        (object, float, 1),
        (object, bool, 2),
        (object, complex, 1),
        # classes
        (object, Super, 1),
        (object, Sub, 2),
        (Super, Sub, 1),
        (Sub, Super, None),
        # union-right
        (int, bytes | str, None),
        (object, object | int, 0),
        (object, Super | int, 1),
        (object, Sub | Sub, 2),
        (object, Super | Sub, 1),
        (object, Super | Any, 1),
        (object, Super | type(None), 1),
        # union-left
        (bytes | int, str, None),
        (object | int, object, 0),
        (object | int, Super, 1),
        (object | int, Sub, 2),
        (object | Sub, Super, 1),
        (object | Any, Super, 1),
        (object | type(None), Super, 1),
        # union-both
        (int | bytes, str | type(None), None),
        (object | int, object | str, 0),
        (object | str, int | float, 1),
        (object | int, Sub | Sub, 2),
        (object | Super, Sub | Sub, 1),
        (object | Any, Super | Sub, 1),
        (object | type(None), Super | Sub, 1),
        # list
        (list, list, any_distance),
        (list[int], list, any_distance),
        (list[int], list[int], 0),
        (list[object], list[int], 1),
        (list[int], list[str], None),
        # set
        (set, set, any_distance),
        (set[int], set, any_distance),
        (set[int], set[int], 0),
        (set[object], set[int], 1),
        (set[int], set[str], None),
        # dict
        (dict, dict, 2 * any_distance),
        (dict[int, int], dict[int], any_distance),
        (dict[int], dict[int, int], any_distance),
        (dict[int, int], dict, 2 * any_distance),
        (dict[int, int], dict[int, int], 0),
        (dict[object, int], dict[int, int], 1),
        (dict[object, object], dict[int, int], 2),
        (dict[int, int], dict[str, int], None),
        # tuple
        (tuple, tuple, any_distance),
        (tuple[int], tuple, any_distance),
        (tuple[int], tuple[int], 0),
        (tuple[object], tuple[int], 1),
        (tuple[int], tuple[str], None),
    ],
)
def test_subtype_distance(subtyping_cluster, left_hint, right_hint, subtype_distance):
    type_system = subtyping_cluster.type_system
    left = type_system.convert_type_hint(left_hint)
    right = type_system.convert_type_hint(right_hint)
    assert type_system.subtype_distance(left, right) == subtype_distance
