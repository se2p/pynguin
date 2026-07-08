#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides literal generation and mutation for libcst-backed test cases.

This module generates libcst expression nodes for Python built-in literal types
and mutates existing literal expressions for use in test-case evolution.  It
supports constant seeding via a :class:`ConstantProvider`, non-empty collection
literals, mapping of abstract collection ABCs to concrete builtins, and
perturbation-based mutation.
"""

from __future__ import annotations

import collections.abc
import math
from typing import TYPE_CHECKING

import libcst as cst

import pynguin.configuration as config
from pynguin.utils import randomness

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pynguin.analyses.constants import ConstantProvider


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

LITERAL_TYPES: frozenset[type] = frozenset({bool, int, float, str, bytes, list, dict, set, tuple})

# Primitive element types used when populating collection literals.
_PRIMITIVE_ELEMENT_TYPES: tuple[type, ...] = (int, str, bool, float)

# Special integer boundary values used during generation (20 % chance).
_SPECIAL_INT_VALUES: tuple[int, ...] = (-1, 0, 1, 2, 3)

# Ordered mapping from abstract ABC to the concrete builtin it maps to.
# Mapping/MutableMapping must appear before the Sequence-like ABCs because
# Mapping is also Iterable; order matters when we iterate.
_ABSTRACT_TO_CONCRETE: dict[type, type] = {
    collections.abc.Mapping: dict,
    collections.abc.MutableMapping: dict,
    collections.abc.Set: set,
    collections.abc.MutableSet: set,
    collections.abc.Iterable: list,
    collections.abc.Iterator: list,
    collections.abc.Collection: list,
    collections.abc.Sequence: list,
    collections.abc.MutableSequence: list,
    collections.abc.Reversible: list,
}

# Concrete builtin collection types and their canonical concrete form.
_CONCRETE_COLLECTION_MAP: dict[type, type] = {
    list: list,
    dict: dict,
    set: set,
    frozenset: set,
    tuple: tuple,
}


# ---------------------------------------------------------------------------
# Abstract-collection mapping
# ---------------------------------------------------------------------------


def map_abstract_collection(raw: type | None) -> type | None:
    """Map abstract or ABC collection classes to a concrete builtin type.

    Concrete builtins and str/bytes are checked first so that they are never
    re-mapped to a collection type even though ``str`` and ``bytes`` are
    technically ``Sequence`` subclasses.

    Args:
        raw: The type to map.  May be ``None`` or a non-class object.

    Returns:
        One of ``list``, ``dict``, ``set``, or ``tuple`` when a mapping exists,
        otherwise ``None``.
    """
    if raw is None:
        return None
    if raw in {str, bytes, bool, int, float, complex}:
        return None
    concrete = _CONCRETE_COLLECTION_MAP.get(raw)
    if concrete is not None:
        return concrete
    try:
        for abstract, mapped in _ABSTRACT_TO_CONCRETE.items():
            if issubclass(raw, abstract):
                return mapped
    except TypeError:
        pass
    return None


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------


def _int_to_cst(value: int) -> cst.BaseExpression:
    """Render an integer value as a CST expression node.

    Negative integers are rendered as ``UnaryOperation(Minus, Integer(…))``
    because ``cst.Integer`` cannot hold a leading minus sign.

    Args:
        value: The integer to render.

    Returns:
        A ``cst.Integer`` or ``cst.UnaryOperation`` node.
    """
    if value < 0:
        return cst.UnaryOperation(
            operator=cst.Minus(),
            expression=cst.Integer(str(abs(value))),
        )
    return cst.Integer(str(value))


def _float_to_cst(value: float) -> cst.BaseExpression:
    """Render a float value as a CST expression node.

    Uses ``repr()`` on the absolute value to guarantee a valid float literal
    string, then wraps in ``UnaryOperation(Minus, …)`` for negative values.

    Args:
        value: The float to render.

    Returns:
        A ``cst.Float`` or ``cst.UnaryOperation`` node.
    """
    abs_val = abs(value)
    if not math.isfinite(abs_val):
        # inf/nan are not valid float literal tokens; render as float("inf")/float("nan").
        inner: cst.BaseExpression = cst.Call(
            func=cst.Name("float"),
            args=[cst.Arg(value=cst.SimpleString(repr(repr(abs_val))))],
        )
    else:
        float_str = repr(abs_val)
        if "." not in float_str and "e" not in float_str:
            float_str += ".0"
        inner = cst.Float(float_str)
    if value < 0:
        return cst.UnaryOperation(
            operator=cst.Minus(),
            expression=inner,
        )
    return inner


def _random_primitive_element() -> cst.BaseExpression:
    """Generate a random primitive CST node for use inside collection literals.

    Chooses uniformly among ``int``, ``str``, ``bool``, and ``float``.  No
    constant seeding is applied — collection elements are always random.

    Returns:
        A CST expression for a randomly typed primitive value.
    """
    tc = config.configuration.test_creation
    tp = randomness.choice(_PRIMITIVE_ELEMENT_TYPES)
    if tp is bool:
        return cst.Name("True" if randomness.next_bool() else "False")
    if tp is int:
        return _int_to_cst(round(randomness.next_gaussian() * tc.max_int))
    if tp is float:
        return _float_to_cst(round(randomness.next_gaussian() * tc.max_int, 2))
    # str
    length = randomness.next_int(0, tc.string_length)
    return cst.SimpleString(repr(randomness.next_string(length)))


def _tuple_elements(
    elements: Sequence[cst.BaseElement],
) -> Sequence[cst.BaseElement]:
    """Ensure a single-element sequence carries a trailing comma for tuple syntax.

    A Python tuple with one element requires a trailing comma so it is not
    parsed as a mere parenthesised expression.

    Args:
        elements: The element sequence to process.

    Returns:
        The same sequence, with a trailing comma added when there is exactly one
        plain ``Element`` (not a starred element).
    """
    if len(elements) == 1 and isinstance(elements[0], cst.Element):
        return [
            elements[0].with_changes(comma=cst.Comma(whitespace_after=cst.SimpleWhitespace("")))
        ]
    return elements


def _parse_int(expr: cst.BaseExpression) -> int | None:
    """Extract an integer value from a CST expression.

    Handles plain ``cst.Integer`` and ``cst.UnaryOperation(Minus, Integer)``.

    Args:
        expr: The CST expression to inspect.

    Returns:
        The integer value, or ``None`` if the expression is not parseable.
    """
    if isinstance(expr, cst.Integer):
        return int(expr.value)
    if (
        isinstance(expr, cst.UnaryOperation)
        and isinstance(expr.operator, cst.Minus)
        and isinstance(expr.expression, cst.Integer)
    ):
        return -int(expr.expression.value)
    return None


def _parse_float(expr: cst.BaseExpression) -> float | None:
    """Extract a float value from a CST expression.

    Handles plain ``cst.Float`` and ``cst.UnaryOperation(Minus, Float)``.

    Args:
        expr: The CST expression to inspect.

    Returns:
        The float value, or ``None`` if the expression is not parseable.
    """
    if isinstance(expr, cst.Float):
        return float(expr.value)
    if (
        isinstance(expr, cst.UnaryOperation)
        and isinstance(expr.operator, cst.Minus)
        and isinstance(expr.expression, cst.Float)
    ):
        return -float(expr.expression.value)
    return None


# ---------------------------------------------------------------------------
# Per-type generation helpers
# ---------------------------------------------------------------------------


def _gen_int(constant_provider: ConstantProvider) -> cst.BaseExpression:
    """Generate an integer literal CST node.

    Args:
        constant_provider: Provider that may supply seeded integer values.

    Returns:
        A CST expression for an integer literal.
    """
    tc = config.configuration.test_creation
    seed_prob = config.configuration.seeding.seeded_primitives_reuse_probability
    if randomness.next_float() < seed_prob:
        seeded = constant_provider.get_constant_for(int)
        if seeded is not None:
            return _int_to_cst(seeded)
    if randomness.next_float() < 0.2:
        return _int_to_cst(randomness.choice(_SPECIAL_INT_VALUES))
    return _int_to_cst(round(randomness.next_gaussian() * tc.max_int))


def _gen_float(constant_provider: ConstantProvider) -> cst.BaseExpression:
    """Generate a float literal CST node.

    Args:
        constant_provider: Provider that may supply seeded float values.

    Returns:
        A CST expression for a float literal.
    """
    tc = config.configuration.test_creation
    seed_prob = config.configuration.seeding.seeded_primitives_reuse_probability
    if randomness.next_float() < seed_prob:
        seeded = constant_provider.get_constant_for(float)
        if seeded is not None:
            return _float_to_cst(seeded)
    return _float_to_cst(round(randomness.next_gaussian() * tc.max_int, 2))


def _gen_str(constant_provider: ConstantProvider) -> cst.BaseExpression:
    """Generate a string literal CST node.

    Args:
        constant_provider: Provider that may supply seeded string values.

    Returns:
        A CST expression for a string literal.
    """
    tc = config.configuration.test_creation
    seed_prob = config.configuration.seeding.seeded_primitives_reuse_probability
    if randomness.next_float() < seed_prob:
        seeded = constant_provider.get_constant_for(str)
        if seeded is not None:
            return cst.SimpleString(repr(seeded))
    length = randomness.next_int(0, tc.string_length)
    return cst.SimpleString(repr(randomness.next_string(length)))


def _gen_bytes(constant_provider: ConstantProvider) -> cst.BaseExpression:
    """Generate a bytes literal CST node.

    Args:
        constant_provider: Provider that may supply seeded bytes values.

    Returns:
        A CST expression for a bytes literal.
    """
    tc = config.configuration.test_creation
    seed_prob = config.configuration.seeding.seeded_primitives_reuse_probability
    if randomness.next_float() < seed_prob:
        seeded = constant_provider.get_constant_for(bytes)
        if seeded is not None:
            return cst.SimpleString(repr(seeded))
    length = randomness.next_int(1, max(2, tc.bytes_length))
    return cst.SimpleString(repr(randomness.next_bytes(length)))


def _gen_list() -> cst.BaseExpression:
    """Generate a list literal CST node.

    Returns:
        A ``cst.List`` node, empty or with 1-3 random primitive elements.
    """
    if randomness.next_bool():
        return cst.List(elements=[])
    count = randomness.next_int(1, min(3, config.configuration.test_creation.collection_size) + 1)
    elems = [cst.Element(value=_random_primitive_element()) for _ in range(count)]
    return cst.List(elements=elems)


def _gen_set() -> cst.BaseExpression:
    """Generate a set literal CST node.

    Empty sets are rendered as ``set()`` because there is no empty-set literal
    syntax in Python.

    Returns:
        A ``cst.Call`` (empty) or ``cst.Set`` (non-empty) node.
    """
    if randomness.next_bool():
        return cst.Call(func=cst.Name("set"))
    count = randomness.next_int(1, min(3, config.configuration.test_creation.collection_size) + 1)
    elems = [cst.Element(value=_random_primitive_element()) for _ in range(count)]
    return cst.Set(elements=elems)


def _gen_tuple() -> cst.BaseExpression:
    """Generate a tuple literal CST node.

    Returns:
        A ``cst.Tuple`` node, empty or with 1-3 random primitive elements.
    """
    if randomness.next_bool():
        return cst.Tuple(elements=[])
    count = randomness.next_int(1, min(3, config.configuration.test_creation.collection_size) + 1)
    raw_elems = [cst.Element(value=_random_primitive_element()) for _ in range(count)]
    return cst.Tuple(elements=_tuple_elements(raw_elems))


def _gen_dict() -> cst.BaseExpression:
    """Generate a dict literal CST node.

    Returns:
        A ``cst.Dict`` node, empty or with 1-3 entries whose keys are random
        strings and whose values are random primitives.
    """
    if randomness.next_bool():
        return cst.Dict(elements=[])
    count = randomness.next_int(1, 4)  # 1–3 entries
    dict_elems = [
        cst.DictElement(
            key=cst.SimpleString(repr(randomness.next_string(randomness.next_int(1, 8)))),
            value=_random_primitive_element(),
        )
        for _ in range(count)
    ]
    return cst.Dict(elements=dict_elems)


# ---------------------------------------------------------------------------
# Per-type mutation helpers
# ---------------------------------------------------------------------------


def _mutate_int(
    expr: cst.BaseExpression, constant_provider: ConstantProvider
) -> cst.BaseExpression:
    """Mutate an integer literal by adding a Gaussian delta.

    Args:
        expr: The current CST expression.
        constant_provider: Fallback constant provider.

    Returns:
        A new CST expression for the mutated integer.
    """
    current = _parse_int(expr)
    if current is None:
        return _gen_int(constant_provider)
    delta = round(randomness.next_gaussian() * config.configuration.test_creation.max_delta)
    return _int_to_cst(current + delta)


def _mutate_float(
    expr: cst.BaseExpression, constant_provider: ConstantProvider
) -> cst.BaseExpression:
    """Mutate a float literal by adding a Gaussian delta.

    Args:
        expr: The current CST expression.
        constant_provider: Fallback constant provider.

    Returns:
        A new CST expression for the mutated float.
    """
    current = _parse_float(expr)
    if current is None:
        return _gen_float(constant_provider)
    delta = randomness.next_gaussian() * config.configuration.test_creation.max_delta
    return _float_to_cst(current + delta)


def _mutate_str(
    expr: cst.BaseExpression, constant_provider: ConstantProvider
) -> cst.BaseExpression:
    """Mutate a string literal by inserting, deleting, or replacing a character.

    Args:
        expr: The current CST expression.
        constant_provider: Fallback constant provider.

    Returns:
        A new CST expression for the mutated string.
    """
    if not isinstance(expr, cst.SimpleString):
        return _gen_str(constant_provider)
    evaluated = expr.evaluated_value
    if not isinstance(evaluated, str):
        return _gen_str(constant_provider)
    s = evaluated
    if len(s) == 0:
        return cst.SimpleString(repr(randomness.next_string(1)))
    op = randomness.next_int(0, 3)
    if op == 0:
        pos = randomness.next_int(0, len(s) + 1)
        ch = randomness.next_string(1)
        new_s = s[:pos] + ch + s[pos:]
    elif op == 1:
        pos = randomness.next_int(0, len(s))
        new_s = s[:pos] + s[pos + 1 :]
    else:
        pos = randomness.next_int(0, len(s))
        ch = randomness.next_string(1)
        new_s = s[:pos] + ch + s[pos + 1 :]
    return cst.SimpleString(repr(new_s))


def _mutate_bytes(
    expr: cst.BaseExpression, constant_provider: ConstantProvider
) -> cst.BaseExpression:
    """Mutate a bytes literal by regenerating fresh random bytes.

    Args:
        expr: The current CST expression.
        constant_provider: Fallback constant provider.

    Returns:
        A new CST expression for fresh random bytes.
    """
    if not isinstance(expr, cst.SimpleString) or not isinstance(expr.evaluated_value, bytes):
        return _gen_bytes(constant_provider)
    length = randomness.next_int(1, max(2, config.configuration.test_creation.bytes_length))
    return cst.SimpleString(repr(randomness.next_bytes(length)))


def _mutate_list(expr: cst.BaseExpression) -> cst.BaseExpression:
    """Mutate a list literal by appending or removing a random element.

    Args:
        expr: The current CST expression.

    Returns:
        A new ``cst.List`` node.
    """
    if not isinstance(expr, cst.List):
        return _gen_list()
    elems = list(expr.elements)
    if elems and randomness.next_bool():
        idx = randomness.next_int(0, len(elems))
        elems = elems[:idx] + elems[idx + 1 :]
    else:
        elems += [cst.Element(value=_random_primitive_element())]
    return expr.with_changes(elements=elems)


def _mutate_tuple(expr: cst.BaseExpression) -> cst.BaseExpression:
    """Mutate a tuple literal by appending or removing a random element.

    Args:
        expr: The current CST expression.

    Returns:
        A new ``cst.Tuple`` node.
    """
    if not isinstance(expr, cst.Tuple):
        return _gen_tuple()
    elems = list(expr.elements)
    if elems and randomness.next_bool():
        idx = randomness.next_int(0, len(elems))
        elems = elems[:idx] + elems[idx + 1 :]
    else:
        elems += [cst.Element(value=_random_primitive_element())]
    return expr.with_changes(elements=_tuple_elements(elems))


def _mutate_dict(expr: cst.BaseExpression) -> cst.BaseExpression:
    """Mutate a dict literal by appending or removing a random entry.

    Args:
        expr: The current CST expression.

    Returns:
        A new ``cst.Dict`` node.
    """
    if not isinstance(expr, cst.Dict):
        return _gen_dict()
    delems = list(expr.elements)
    if delems and randomness.next_bool():
        idx = randomness.next_int(0, len(delems))
        delems = delems[:idx] + delems[idx + 1 :]
    else:
        new_entry = cst.DictElement(
            key=cst.SimpleString(repr(randomness.next_string(randomness.next_int(1, 8)))),
            value=_random_primitive_element(),
        )
        delems += [new_entry]
    return expr.with_changes(elements=delems)


def _mutate_set(expr: cst.BaseExpression) -> cst.BaseExpression:
    """Mutate a set literal by appending or removing a random element.

    An empty set is represented as ``set()`` (``cst.Call``); removing the last
    element of a non-empty set reverts to that representation.

    Args:
        expr: The current CST expression.

    Returns:
        A ``cst.Call`` or ``cst.Set`` node.
    """
    if isinstance(expr, cst.Call):
        return cst.Set(elements=[cst.Element(value=_random_primitive_element())])
    if not isinstance(expr, cst.Set):
        return _gen_set()
    selems = list(expr.elements)
    if selems and randomness.next_bool():
        idx = randomness.next_int(0, len(selems))
        selems = selems[:idx] + selems[idx + 1 :]
        if not selems:
            return cst.Call(func=cst.Name("set"))
    else:
        selems += [cst.Element(value=_random_primitive_element())]
    return expr.with_changes(elements=selems)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_literal(
    raw: type | None,
    constant_provider: ConstantProvider,
) -> cst.BaseExpression:
    """Generate a libcst expression node for the given Python type.

    Uses constant seeding via ``constant_provider`` for primitive types when a
    seeded value is available, otherwise falls back to random generation.  For
    collection types, produces empty or small non-empty literals whose elements
    are randomly typed primitives.

    Args:
        raw: The Python type for which to generate a literal, or ``None``.
        constant_provider: A provider that may supply seeded constant values
            for primitive types.

    Returns:
        A ``cst.BaseExpression`` node representing the generated literal.
        Returns ``cst.Name("None")`` when ``raw`` is ``None`` or unrecognised.
    """
    if raw is bool:
        return cst.Name("True" if randomness.next_bool() else "False")
    if raw is int:
        return _gen_int(constant_provider)
    if raw is float:
        return _gen_float(constant_provider)
    if raw is str:
        return _gen_str(constant_provider)
    if raw is bytes:
        return _gen_bytes(constant_provider)
    if raw is list:
        return _gen_list()
    if raw is set:
        return _gen_set()
    if raw is tuple:
        return _gen_tuple()
    if raw is dict:
        return _gen_dict()
    return cst.Name("None")


def _mutate_bool(expr: cst.BaseExpression) -> cst.BaseExpression:
    """Flip a boolean literal.

    Args:
        expr: The current CST expression.

    Returns:
        The negated boolean as a ``cst.Name`` node.
    """
    if isinstance(expr, cst.Name):
        return cst.Name("False" if expr.value == "True" else "True")
    return cst.Name("True" if randomness.next_bool() else "False")


def _dispatch_mutate(
    expr: cst.BaseExpression,
    raw: type | None,
    constant_provider: ConstantProvider,
) -> cst.BaseExpression:
    """Dispatch a type-specific mutation without the random-perturbation guard.

    Args:
        expr: The current CST expression.
        raw: The Python type of the literal, or ``None``.
        constant_provider: Provider used as fallback when parsing fails.

    Returns:
        A mutated ``cst.BaseExpression``.
    """
    if raw is bool:
        return _mutate_bool(expr)
    if raw is int:
        return _mutate_int(expr, constant_provider)
    if raw is float:
        return _mutate_float(expr, constant_provider)
    if raw is str:
        return _mutate_str(expr, constant_provider)
    if raw is bytes:
        return _mutate_bytes(expr, constant_provider)
    if raw is list:
        return _mutate_list(expr)
    if raw is tuple:
        return _mutate_tuple(expr)
    if raw is dict:
        return _mutate_dict(expr)
    if raw is set:
        return _mutate_set(expr)
    return generate_literal(raw, constant_provider)


def mutate_literal(
    expr: cst.BaseExpression,
    raw: type | None,
    constant_provider: ConstantProvider,
) -> cst.BaseExpression:
    """Perturb an existing literal CST expression.

    With probability ``search_algorithm.random_perturbation``, or whenever the
    expression cannot be parsed as the expected type, falls back to a freshly
    generated literal via :func:`generate_literal`.  Otherwise applies a
    type-specific delta mutation.

    Args:
        expr: The current CST expression to mutate.
        raw: The Python type of the literal, or ``None``.
        constant_provider: A provider that may supply seeded constant values
            when falling back to :func:`generate_literal`.

    Returns:
        A new ``cst.BaseExpression`` that is a perturbation of ``expr``.
    """
    if randomness.next_float() < config.configuration.search_algorithm.random_perturbation:
        return generate_literal(raw, constant_provider)
    return _dispatch_mutate(expr, raw, constant_provider)
