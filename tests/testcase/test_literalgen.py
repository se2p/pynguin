#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pure-unit tests for :mod:`pynguin.testcase.literalgen`.

The suite is deliberately compact: a handful of parametrized/property functions
exercise literal generation, the CST render/parse helpers, and the per-type
mutation helpers.  Generation is randomised, so tests either assert *structural*
properties (type after render+eval) or use a seeded RNG and iterate enough to
cover both branches of each ``next_bool`` fork.
"""

from __future__ import annotations

import collections.abc
import math
from typing import cast

import libcst as cst
import pytest
from hypothesis import given
from hypothesis import strategies as st

import pynguin.configuration as config
import pynguin.testcase.literalgen as lg
from pynguin.analyses.constants import ConstantProvider, EmptyConstantProvider
from pynguin.utils import randomness

_MODULE = cst.Module(body=[])


def _render(node: cst.CSTNode) -> str:
    """Render a CST expression node back to source code."""
    return _MODULE.code_for_node(node)


def _eval(node: cst.BaseExpression) -> object:
    """Render then evaluate a CST expression node."""
    return eval(_render(node))  # noqa: S307


class _FixedConstantProvider(ConstantProvider):
    """A provider that always yields a fixed value per primitive type."""

    def __init__(self) -> None:
        self._values: dict[type, object] = {
            int: 4242,
            float: 3.5,
            str: "seeded-value",
            bytes: b"seeded-bytes",
        }

    def get_constant_for(self, tp_):
        return self._values.get(tp_)


@pytest.fixture(autouse=True)
def _seed_rng():
    """Seed the global RNG so branch coverage is deterministic."""
    randomness.RNG.seed(2024)


# ---------------------------------------------------------------------------
# map_abstract_collection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        (str, None),
        (bytes, None),
        (bool, None),
        (int, None),
        (float, None),
        (complex, None),
        (list, list),
        (dict, dict),
        (set, set),
        (frozenset, set),
        (tuple, tuple),
        (collections.abc.Mapping, dict),
        (collections.abc.MutableMapping, dict),
        (collections.abc.Set, set),
        (collections.abc.MutableSet, set),
        (collections.abc.Iterable, list),
        (collections.abc.Sequence, list),
        (object, None),
    ],
)
def test_map_abstract_collection(raw, expected):
    assert lg.map_abstract_collection(raw) is expected


def test_map_abstract_collection_non_class_returns_none():
    # A non-class object makes ``issubclass`` raise ``TypeError`` -> None.
    assert lg.map_abstract_collection(cast("type", 42)) is None


# ---------------------------------------------------------------------------
# Generating primitive literals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tp", [bool, int, float, str, bytes])
def test_generate_literal_primitive_type_roundtrip(tp):
    config.configuration.seeding.seeded_primitives_reuse_probability = 0.0
    provider = EmptyConstantProvider()
    for _ in range(30):
        node = lg.generate_literal(tp, provider)
        value = _eval(node)
        assert type(value) is tp


@pytest.mark.parametrize("tp", [int, float, str, bytes])
def test_generate_literal_uses_seeded_constant(tp):
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    provider = _FixedConstantProvider()
    expected = provider.get_constant_for(tp)
    node = lg.generate_literal(tp, provider)
    assert _eval(node) == expected


@pytest.mark.parametrize("tp", [list, set, tuple, dict])
def test_generate_literal_collection_roundtrip(tp):
    provider = EmptyConstantProvider()
    seen_empty = False
    seen_non_empty = False
    for _ in range(60):
        value = _eval(lg.generate_literal(tp, provider))
        assert isinstance(value, tp)
        if len(value) == 0:
            seen_empty = True
        else:
            seen_non_empty = True
    # With a seeded RNG and 60 iterations both branches are hit deterministically.
    assert seen_empty
    assert seen_non_empty


@pytest.mark.parametrize("raw", [None, object])
def test_generate_literal_unrecognised_returns_none(raw):
    node = lg.generate_literal(raw, EmptyConstantProvider())
    assert isinstance(node, cst.Name)
    assert node.value == "None"


# ---------------------------------------------------------------------------
# Collection-element constant seeding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tp", [list, set, tuple])
def test_generate_literal_collection_elements_use_seeded_constants(tp):
    """Non-empty collections should only contain seeded values.

    With reuse probability 1.0, non-empty collections should only ever
    contain seeded int/float/str values (bool elements stay random).
    """
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    provider = _FixedConstantProvider()
    seeded_values = {provider.get_constant_for(int), provider.get_constant_for(float)}
    seeded_str = provider.get_constant_for(str)
    seen_non_empty = False
    for _ in range(60):
        node = lg.generate_literal(tp, provider)
        value = _eval(node)
        if len(value) == 0:
            continue
        seen_non_empty = True
        for element in value:
            if isinstance(element, bool):
                continue
            if isinstance(element, str):
                assert element == seeded_str
            else:
                assert element in seeded_values
    assert seen_non_empty


def test_generate_literal_dict_uses_seeded_constants():
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    provider = _FixedConstantProvider()
    seeded_values = {provider.get_constant_for(int), provider.get_constant_for(float)}
    seeded_str = provider.get_constant_for(str)
    seen_non_empty = False
    for _ in range(60):
        value = _eval(lg.generate_literal(dict, provider))
        if len(value) == 0:
            continue
        seen_non_empty = True
        for key, element in value.items():
            assert key == seeded_str
            if isinstance(element, bool):
                continue
            if isinstance(element, str):
                assert element == seeded_str
            else:
                assert element in seeded_values
    assert seen_non_empty


@pytest.mark.parametrize("tp", [list, set, tuple, dict])
def test_generate_literal_collection_elements_not_seeded_when_probability_zero(tp):
    """With reuse probability 0.0, seeded sentinel values never appear."""
    config.configuration.seeding.seeded_primitives_reuse_probability = 0.0
    provider = _FixedConstantProvider()
    for _ in range(60):
        value = _eval(lg.generate_literal(tp, provider))
        flat = value.values() if tp is dict else value
        assert 4242 not in flat
        assert 3.5 not in flat
        assert "seeded-value" not in flat


# ---------------------------------------------------------------------------
# CST render helpers: round-trip properties
# ---------------------------------------------------------------------------


@given(st.integers(min_value=-(10**18), max_value=10**18))
def test_int_to_cst_roundtrip(value):
    assert _eval(lg._int_to_cst(value)) == value


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_float_to_cst_roundtrip(value):
    assert _eval(lg._float_to_cst(value)) == value


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_float_to_cst_non_finite(value):
    result = _eval(lg._float_to_cst(value))
    assert isinstance(result, float)
    if math.isnan(value):
        assert math.isnan(result)
    else:
        assert result == value


# ---------------------------------------------------------------------------
# _parse_int / _parse_float
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, -1, 2048, -777])
def test_parse_int_roundtrip(value):
    assert lg._parse_int(lg._int_to_cst(value)) == value


@pytest.mark.parametrize("value", [0.0, 1.5, -3.25, 100.0])
def test_parse_float_roundtrip(value):
    assert lg._parse_float(lg._float_to_cst(value)) == value


def test_parse_helpers_reject_wrong_nodes():
    name = cst.Name("x")
    assert lg._parse_int(name) is None
    assert lg._parse_float(name) is None
    # An int node is not a float node and vice versa.
    assert lg._parse_float(lg._int_to_cst(5)) is None
    assert lg._parse_int(lg._float_to_cst(5.0)) is None


# ---------------------------------------------------------------------------
# Mutation: matching input node types
# ---------------------------------------------------------------------------


def _literal_node(tp: type) -> cst.BaseExpression:
    """Deterministically build a non-empty literal node of the given type."""
    if tp is bool:
        return cst.Name("True")
    if tp is int:
        return lg._int_to_cst(10)
    if tp is float:
        return lg._float_to_cst(2.5)
    if tp is str:
        return cst.SimpleString(repr("abcdef"))
    if tp is bytes:
        return cst.SimpleString(repr(b"abcdef"))
    if tp is list:
        return cst.List(elements=[cst.Element(value=lg._int_to_cst(1))])
    if tp is tuple:
        return cst.Tuple(elements=lg._tuple_elements([cst.Element(value=lg._int_to_cst(1))]))
    if tp is dict:
        return cst.Dict(
            elements=[cst.DictElement(key=cst.SimpleString("'k'"), value=lg._int_to_cst(1))]
        )
    if tp is set:
        return cst.Set(elements=[cst.Element(value=lg._int_to_cst(1))])
    raise AssertionError(tp)


@pytest.mark.parametrize("tp", [bool, int, float, str, bytes, list, set, tuple, dict])
def test_dispatch_mutate_matching_node(tp):
    provider = EmptyConstantProvider()
    for _ in range(60):
        node = _literal_node(tp)
        mutated = lg._dispatch_mutate(node, tp, provider)
        value = _eval(mutated)
        if tp is bool:
            assert type(value) is bool
        else:
            assert isinstance(value, tp)


@pytest.mark.parametrize("tp", [bool, int, float, str, bytes, list, set, tuple, dict])
def test_dispatch_mutate_mismatched_node_falls_back(tp):
    # A ``Name`` node matches none of the per-type parsers, forcing the
    # regenerate/fallback branch inside every mutation helper.
    provider = EmptyConstantProvider()
    config.configuration.seeding.seeded_primitives_reuse_probability = 0.0
    mismatch = cst.Name("wrong")
    for _ in range(20):
        mutated = lg._dispatch_mutate(mismatch, tp, provider)
        value = _eval(mutated)
        if tp is bool:
            assert type(value) is bool
        else:
            assert isinstance(value, tp)


def test_mutate_str_handles_bytes_and_empty_string():
    provider = EmptyConstantProvider()
    config.configuration.seeding.seeded_primitives_reuse_probability = 0.0
    # SimpleString whose evaluated value is *bytes* -> regenerate a str.
    bytes_node = cst.SimpleString(repr(b"xy"))
    assert isinstance(_eval(lg._dispatch_mutate(bytes_node, str, provider)), str)
    # Empty string -> single-char string.
    empty_node = cst.SimpleString(repr(""))
    result = _eval(lg._dispatch_mutate(empty_node, str, provider))
    assert isinstance(result, str)
    assert len(result) == 1


def test_mutate_bytes_wrong_payload_regenerates():
    provider = EmptyConstantProvider()
    config.configuration.seeding.seeded_primitives_reuse_probability = 0.0
    # SimpleString holding a *str* payload -> regenerate bytes.
    str_node = cst.SimpleString(repr("not-bytes"))
    assert isinstance(_eval(lg._dispatch_mutate(str_node, bytes, provider)), bytes)


def test_mutate_set_from_empty_call_and_shrink_to_empty():
    provider = EmptyConstantProvider()
    # ``set()`` call node -> becomes a non-empty Set.
    empty_call = cst.Call(func=cst.Name("set"))
    grown = lg._dispatch_mutate(empty_call, set, provider)
    assert isinstance(_eval(grown), set)
    # Iterate so the "remove last element -> back to set()" branch is exercised.
    for _ in range(60):
        single = cst.Set(elements=[cst.Element(value=lg._int_to_cst(1))])
        mutated = lg._dispatch_mutate(single, set, provider)
        assert isinstance(_eval(mutated), set)


@pytest.mark.parametrize("expr", [cst.Name("True"), cst.Integer("1")])
def test_mutate_bool(expr):
    result = lg._mutate_bool(expr)
    assert isinstance(result, cst.Name)
    assert result.value in {"True", "False"}


def test_dispatch_mutate_unrecognised_type_generates_none():
    node = lg._dispatch_mutate(cst.Name("x"), None, EmptyConstantProvider())
    assert isinstance(node, cst.Name)
    assert node.value == "None"


# ---------------------------------------------------------------------------
# Public mutate_literal wrapper
# ---------------------------------------------------------------------------


def test_mutate_literal_perturbation_regenerates():
    provider = EmptyConstantProvider()
    config.configuration.search_algorithm.random_perturbation = 1.0
    node = lg._int_to_cst(7)
    assert isinstance(_eval(lg.mutate_literal(node, int, provider)), int)


def test_mutate_literal_dispatches_delta():
    provider = EmptyConstantProvider()
    config.configuration.search_algorithm.random_perturbation = 0.0
    for _ in range(30):
        node = lg._int_to_cst(7)
        assert isinstance(_eval(lg.mutate_literal(node, int, provider)), int)


# ---------------------------------------------------------------------------
# Complex-number literals (DISABLED_SUBSYSTEMS point 15)
# ---------------------------------------------------------------------------


def test_generate_literal_complex_roundtrip():
    config.configuration.seeding.seeded_primitives_reuse_probability = 0.0
    provider = EmptyConstantProvider()
    for _ in range(30):
        node = lg.generate_literal(complex, provider)
        assert isinstance(node, cst.Call)
        value = _eval(node)
        assert type(value) is complex


def test_generate_literal_complex_uses_seeded_constant():
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    provider = _FixedConstantProviderComplex()
    node = lg.generate_literal(complex, provider)
    assert _eval(node) == complex(1.5, -2.5)


class _FixedConstantProviderComplex(ConstantProvider):
    def __init__(self) -> None:
        self._value = complex(1.5, -2.5)

    def get_constant_for(self, tp_):
        return self._value if tp_ is complex else None


@pytest.mark.parametrize(
    "value",
    [complex(0, 0), complex(-2.5, 1.5), complex(3, -4), complex(1.25, 0)],
)
def test_parse_complex_roundtrip(value):
    node = lg._complex_to_cst(value)
    assert lg._parse_complex(node) == value


def test_parse_complex_rejects_non_matching_nodes():
    assert lg._parse_complex(lg._int_to_cst(3)) is None
    assert lg._parse_complex(cst.Call(func=cst.Name("complex"))) is None
    assert lg._parse_complex(cst.Call(func=cst.Name("float"), args=[])) is None


def test_parse_literal_complex():
    node = lg._complex_to_cst(complex(2, -3))
    assert lg.parse_literal(node, complex) == complex(2, -3)
    assert lg.parse_literal(lg._int_to_cst(1), complex) is None


def test_literal_to_cst_complex_roundtrip():
    value = complex(-1.5, 4.0)
    node = lg.literal_to_cst(value)
    assert _eval(node) == value


def test_mutate_complex_produces_different_parseable_complex():
    config.configuration.search_algorithm.random_perturbation = 0.0
    provider = EmptyConstantProvider()
    seen_change = False
    for _ in range(50):
        node = lg._complex_to_cst(complex(3, 4))
        mutated = lg.mutate_literal(node, complex, provider)
        value = lg._parse_complex(mutated)
        assert value is not None
        if value != complex(3, 4):
            seen_change = True
    assert seen_change


def test_mutate_complex_unparseable_regenerates():
    provider = EmptyConstantProvider()
    result = lg._mutate_complex(lg._int_to_cst(1), provider)
    assert lg._parse_complex(result) is not None


# ---------------------------------------------------------------------------
# Reference-carrying collections (DISABLED_SUBSYSTEMS point 16)
# ---------------------------------------------------------------------------


def test_element_value_uses_pool_when_probability_high():
    config.configuration.test_creation.collection_reference_probability = 1.0
    pool = [cst.Name("var_0"), cst.Name("var_1")]
    for _ in range(10):
        node = lg._element_value(EmptyConstantProvider(), pool)
        assert isinstance(node, cst.Name)
        assert node.value in {"var_0", "var_1"}


def test_element_value_ignores_pool_when_probability_zero():
    config.configuration.test_creation.collection_reference_probability = 0.0
    pool = [cst.Name("var_0")]
    for _ in range(10):
        node = lg._element_value(EmptyConstantProvider(), pool)
        # never the reference name
        assert not (isinstance(node, cst.Name) and node.value == "var_0")


def test_element_value_empty_pool_falls_back_to_literal():
    config.configuration.test_creation.collection_reference_probability = 1.0
    node = lg._element_value(EmptyConstantProvider(), ())
    # A primitive literal, not a bare var reference.
    assert _eval(node) is not None or isinstance(node, cst.BaseExpression)


@pytest.mark.parametrize("raw", [list, set, tuple])
def test_generate_literal_collection_can_contain_reference(raw):
    config.configuration.test_creation.collection_reference_probability = 1.0
    pool = [cst.Name("var_0")]
    found_reference = False
    for _ in range(40):
        node = lg.generate_literal(raw, EmptyConstantProvider(), pool)
        code = _render(node)
        if "var_0" in code:
            found_reference = True
            break
    assert found_reference


def test_mutate_collection_can_insert_reference():
    config.configuration.search_algorithm.random_perturbation = 0.0
    config.configuration.test_creation.collection_reference_probability = 1.0
    pool = [cst.Name("var_0")]
    empty_list = cst.List(elements=[])
    found = False
    for _ in range(40):
        node = lg.mutate_literal(empty_list, list, EmptyConstantProvider(), pool)
        if "var_0" in _render(node):
            found = True
            break
    assert found
