#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-backed :mod:`pynguin.testcase.testfactory`.

These tests target the non-disabled surface of the re-derived ``TestFactory``:
statement insertion/deletion, variable reuse by exact/subtype, primitive value
and call mutation, recursive object creation with depth limiting, parameter
satisfaction (including positional-only / optional handling) and enum building.

Disabled features (field statements, the ``change_statement_type`` operator,
pynguinml, reference-carrying collections and seeding) are intentionally not
covered here.
"""

from __future__ import annotations

import collections.abc
import enum
import operator
from inspect import Parameter, Signature
from unittest import mock
from unittest.mock import MagicMock

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.typesystem import (
    AnyType,
    InferredSignature,
    Instance,
    NoneType,
    TupleType,
    TypeInfo,
    TypeSystem,
)
from tests.fixtures.accessibles.accessible import SomeType, simple_function
from tests.testcase._builders import assign, call_stmt, int_stmt, make_test_case, stmt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_factory(cluster=None, provider=None) -> tf.TestFactory:
    """Build a factory over a (mock) cluster with an optional constant provider."""
    if cluster is None:
        cluster = MagicMock(ModuleTestCluster)
    return tf.TestFactory(cluster, provider)


def _make_signature(params, param_types, return_type, type_system) -> InferredSignature:
    """Build an :class:`InferredSignature` from raw inspect parameters."""
    return InferredSignature(
        signature=Signature(parameters=params),
        original_return_type=return_type,
        original_parameters=param_types,
        type_system=type_system,
    )


def _positional_only_function(type_system) -> gao.GenericFunction:
    """A function with positional-only params: required ``a`` + optional ``b``/``c``."""
    params = [
        Parameter("a", Parameter.POSITIONAL_ONLY, annotation=int),
        Parameter("b", Parameter.POSITIONAL_ONLY, annotation=int, default=0),
        Parameter("c", Parameter.POSITIONAL_ONLY, annotation=int, default=0),
    ]
    param_types = {
        "a": Instance(TypeInfo(int)),
        "b": Instance(TypeInfo(int)),
        "c": Instance(TypeInfo(int)),
    }
    return gao.GenericFunction(
        function=simple_function,  # type: ignore[arg-type]
        inferred_signature=_make_signature(
            params, param_types, Instance(TypeInfo(float)), type_system
        ),
    )


def _make_enum() -> gao.GenericEnum:
    """A GenericEnum over a small runtime enum."""
    Color = enum.Enum("Color", "RED GREEN BLUE")  # noqa: N806
    return gao.GenericEnum(TypeInfo(Color))


def _bad_function(type_system) -> gao.GenericFunction:
    """A function whose callable has a non-identifier name (``<lambda>``)."""
    bad = lambda z: z  # noqa: E731
    bad.__name__ = "<lambda>"
    return gao.GenericFunction(
        function=bad,  # type: ignore[arg-type]
        inferred_signature=_make_signature([], {}, NoneType(), type_system),
    )


def _bad_method(type_system) -> gao.GenericMethod:
    """A method whose callable has a non-identifier name (``<lambda>``)."""
    bad = lambda self: self  # noqa: E731
    bad.__name__ = "<lambda>"
    return gao.GenericMethod(
        owner=TypeInfo(SomeType),
        method=bad,  # type: ignore[arg-type]
        inferred_signature=_make_signature([], {}, NoneType(), type_system),
    )


def _var_args_function(type_system) -> gao.GenericFunction:
    """A function with an untyped param plus ``*args`` / ``**kwargs``."""
    params = [
        Parameter("p", Parameter.POSITIONAL_OR_KEYWORD),
        Parameter("args", Parameter.VAR_POSITIONAL),
        Parameter("kwargs", Parameter.VAR_KEYWORD),
    ]
    param_types = {"p": AnyType(), "args": AnyType(), "kwargs": AnyType()}
    return gao.GenericFunction(
        function=simple_function,  # type: ignore[arg-type]
        inferred_signature=_make_signature(
            params, param_types, Instance(TypeInfo(float)), type_system
        ),
    )


def _call_expr(node) -> cst.Call:
    """Extract the ``cst.Call`` from an ``lhs = call(...)`` statement node."""
    assert isinstance(node, cst.SimpleStatementLine)
    small = node.body[0]
    assert isinstance(small, cst.Assign)
    call = small.value
    assert isinstance(call, cst.Call)
    return call


def _call_with(name, expr, accessible, bound_type=None) -> tc.Statement:
    """Build an assignment statement and attach an accessible object to it."""
    statement = call_stmt(name, expr, bound_type=bound_type)
    statement.accessible = accessible
    return statement


def _accessible_index(test_case: tc.TestCase, accessible) -> int | None:
    """Return the index of the first statement bound to *accessible*."""
    for idx, statement in enumerate(test_case.statements()):
        if statement.accessible is accessible:
            return idx
    return None


# ---------------------------------------------------------------------------
# Construction / trivial public API
# ---------------------------------------------------------------------------


def test_init_defaults_constant_provider():
    factory = _make_factory()
    assert isinstance(factory._constant_provider, EmptyConstantProvider)


def test_insert_random_statement_no_accessible():
    cluster = MagicMock(ModuleTestCluster)
    cluster.get_random_accessible.return_value = None
    assert tf.TestFactory(cluster).insert_random_statement(tc.TestCase(), 0) == -1


@pytest.mark.parametrize(
    "position,expected_first,expected_last",
    [
        (-1, "var_0", "var_9"),  # append at the end
        (0, "var_9", "var_0"),  # insert at the front
    ],
)
def test_append_statement_positions(position, expected_first, expected_last):
    test_case = make_test_case(int_stmt("var_0", 1))
    _make_factory().append_statement(test_case, int_stmt("var_9", 9), position=position)
    assert test_case.size() == 2
    assert test_case.get_statement(0).bound_variable == expected_first
    assert test_case.get_statement(1).bound_variable == expected_last


@pytest.mark.parametrize(
    "position,expected,remaining",
    [
        (0, True, 1),
        (5, False, 2),
        (-1, False, 2),
    ],
)
def test_delete_statement(position, expected, remaining):
    test_case = make_test_case(int_stmt("var_0", 1), int_stmt("var_1", 2))
    assert tf.TestFactory.delete_statement(test_case, position) is expected
    assert test_case.size() == remaining


@pytest.mark.parametrize(
    "builder,position,expected,size_after",
    [
        # out of range -> False, nothing removed
        (lambda: make_test_case(int_stmt("var_0", 1)), 9, False, 1),
        # cascade: var_1 reads var_0 -> deleting 0 removes both
        (
            lambda: make_test_case(int_stmt("var_0", 1), assign("var_1", "f(var_0)")),
            0,
            True,
            0,
        ),
        # independent statements -> only the target is removed
        (
            lambda: make_test_case(int_stmt("var_0", 1), int_stmt("var_1", 2)),
            0,
            True,
            1,
        ),
    ],
)
def test_delete_statement_gracefully(builder, position, expected, size_after):
    test_case = builder()
    assert tf.TestFactory.delete_statement_gracefully(test_case, position) is expected
    assert test_case.size() == size_after


# ---------------------------------------------------------------------------
# Variable lookup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,statements,position,expected",
    [
        # raw None never matches
        (None, [int_stmt("var_0", 1)], 1, None),
        # exact type match
        (int, [int_stmt("var_0", 1)], 1, "var_0"),
        # subtype match: bool is a subclass of int
        (int, [assign("var_0", "True", bound_type=bool)], 1, "var_0"),
        # no match
        (int, [assign("var_0", "'x'", bound_type=str)], 1, None),
        # position limit excludes statements at/after position
        (int, [int_stmt("var_0", 1)], 0, None),
    ],
)
def test_find_variable_of_type(raw, statements, position, expected):
    test_case = make_test_case(*statements)
    assert tf.TestFactory._find_variable_of_type(test_case, raw, position) == expected


@pytest.mark.parametrize(
    "raw,node_type", [(list, cst.List), (dict, cst.Dict), (set, (cst.Set, cst.Call))]
)
def test_fallback_literal_value_collection(raw, node_type):
    value = _make_factory()._fallback_literal_value(raw)
    assert isinstance(value, node_type)


# ---------------------------------------------------------------------------
# Value mutation (primitives)
# ---------------------------------------------------------------------------


def _compound_statement() -> tc.Statement:
    node = cst.parse_module("if var_0:\n    pass\n").body[0]
    return tc.Statement(node=node, bound_variable="var_0", bound_type=int)


@pytest.mark.parametrize(
    "builder,position",
    [
        # out of range
        (lambda: make_test_case(int_stmt("var_0", 1)), 9),
        # bound_type is not a literal type
        (lambda: make_test_case(_call_with("var_0", "_.SomeType()", None, bound_type=SomeType)), 0),
        # bound_type is None
        (lambda: make_test_case(stmt("var_0", bound_variable="var_0")), 0),
        # node is a compound statement (not SimpleStatementLine)
        (lambda: make_test_case(_compound_statement()), 0),
        # SimpleStatementLine whose first small statement is not an Assign
        (lambda: make_test_case(stmt("var_0", bound_variable="var_0", bound_type=int)), 0),
    ],
)
def test_mutate_value_returns_false(builder, position):
    assert _make_factory().mutate_value(builder(), position) is False


def test_mutate_value_success():
    test_case = make_test_case(int_stmt("var_0", 5))
    assert _make_factory().mutate_value(test_case, 0) is True
    mutated = test_case.get_statement(0)
    assert mutated.bound_variable == "var_0"
    assert mutated.bound_type is int
    assert isinstance(mutated.node, cst.SimpleStatementLine)


# ---------------------------------------------------------------------------
# Call mutation
# ---------------------------------------------------------------------------


def test_mutate_call_returns_false_out_of_range():
    assert _make_factory().mutate_call(tc.TestCase(), 9) is False


def test_mutate_call_returns_false_no_accessible():
    # primitive statement carries no accessible object
    test_case = make_test_case(int_stmt("var_0", 5))
    assert _make_factory().mutate_call(test_case, 0) is False


def test_mutate_call_returns_false_unknown_accessible():
    unknown = MagicMock(gao.GenericAccessibleObject)
    test_case = make_test_case(_call_with("var_0", "_.thing()", unknown))
    assert _make_factory().mutate_call(test_case, 0) is False


def test_mutate_call_method_without_receiver_returns_false(method_mock):
    # no SomeType variable in scope -> receiver cannot be found
    test_case = make_test_case(_call_with("var_0", "obj.simple_method(x)", method_mock))
    assert _make_factory().mutate_call(test_case, 0) is False


def test_mutate_call_constructor(constructor_mock):
    test_case = make_test_case(
        _call_with("var_0", "_.SomeType(y)", constructor_mock, bound_type=SomeType)
    )
    assert _make_factory().mutate_call(test_case, 0) is True
    node = test_case.get_statement(0).node
    assert "SomeType" in cst.Module(body=[node]).code


def test_mutate_call_function(function_mock):
    test_case = make_test_case(
        _call_with("var_0", "_.simple_function(z)", function_mock, bound_type=float)
    )
    assert _make_factory().mutate_call(test_case, 0) is True
    assert "simple_function" in cst.Module(body=[test_case.get_statement(0).node]).code


def test_mutate_call_method(method_mock):
    test_case = make_test_case(
        assign("obj", "_.SomeType()", bound_type=SomeType),
        _call_with("var_1", "obj.simple_method(x)", method_mock, bound_type=float),
    )
    assert _make_factory().mutate_call(test_case, 1) is True
    assert "simple_method" in cst.Module(body=[test_case.get_statement(1).node]).code


def test_mutate_call_enum():
    enum_gao = _make_enum()
    test_case = make_test_case(_call_with("var_0", "_.Color.RED", enum_gao))
    assert _make_factory().mutate_call(test_case, 0) is True
    assert "Color" in cst.Module(body=[test_case.get_statement(0).node]).code


def test_mutate_call_regenerates_positional_only_args(type_system):
    config.configuration.test_creation.skip_optional_parameter_probability = 1.0
    func = _positional_only_function(type_system)
    test_case = make_test_case(
        _call_with("var_0", "_.simple_function(1, 2, 3)", func, bound_type=float)
    )
    assert _make_factory().mutate_call(test_case, 0) is True
    call = _call_expr(test_case.get_statement(0).node)
    # optional b and c are skipped; only the required positional-only ``a`` remains
    assert len(call.args) == 1
    assert call.args[0].keyword is None


# ---------------------------------------------------------------------------
# Parameter satisfaction during emission
# ---------------------------------------------------------------------------


def test_satisfy_params_positional_only(type_system):
    config.configuration.test_creation.skip_optional_parameter_probability = 1.0
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    factory = tf.TestFactory(cluster)
    func = _positional_only_function(type_system)
    test_case = tc.TestCase()
    position = factory.append_generic_accessible(test_case, func)
    assert position >= 0
    call = _call_expr(test_case.get_statement(position).node)
    # only the required positional-only parameter is emitted, as a positional arg
    assert len(call.args) == 1
    assert call.args[0].keyword is None


def test_satisfy_params_tuple_annotation_receives_a_tuple(type_system):
    # ``tuple`` is never an Instance (see TupleType), so it must be mapped
    # explicitly; otherwise the parameter degrades to an arbitrary scalar.
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    factory = tf.TestFactory(cluster)
    params = [Parameter("source", Parameter.POSITIONAL_OR_KEYWORD, annotation=tuple)]
    param_types = {"source": TupleType((Instance(TypeInfo(int)),))}
    func = gao.GenericFunction(
        function=simple_function,  # type: ignore[arg-type]
        inferred_signature=_make_signature(
            params, param_types, Instance(TypeInfo(float)), type_system
        ),
    )
    test_case = tc.TestCase()
    position = factory.append_generic_accessible(test_case, func)
    assert position >= 0
    call = _call_expr(test_case.get_statement(position).node)
    assert len(call.args) == 1
    # the value is emitted as a named dependency statement holding a tuple
    dep = test_case.get_statement(position - 1).node
    assert isinstance(dep, cst.SimpleStatementLine)
    assert isinstance(dep.body[0], cst.Assign)
    assert isinstance(dep.body[0].value, cst.Tuple)


def test_satisfy_params_honours_chosen_parameter_types(type_system):
    # The drawn type (here: NoneType via none_weight) must be used rather than
    # the annotation, so that None-guarded branches of the SUT stay reachable.
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 0
    config.configuration.test_creation.original_type_weight = 0
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    factory = tf.TestFactory(cluster)
    params = [Parameter("text", Parameter.POSITIONAL_OR_KEYWORD, annotation=str)]
    func = gao.GenericFunction(
        function=simple_function,  # type: ignore[arg-type]
        inferred_signature=_make_signature(
            params, {"text": Instance(TypeInfo(str))}, Instance(TypeInfo(float)), type_system
        ),
    )
    test_case = tc.TestCase()
    with mock.patch.object(tf.randomness, "next_float", return_value=0.0):
        position = factory.append_generic_accessible(test_case, func)
    assert position >= 0
    call = _call_expr(test_case.get_statement(position).node)
    assert len(call.args) == 1
    assert isinstance(call.args[0].value, cst.Name)
    assert call.args[0].value.value == "None"


def test_satisfy_params_emits_var_args_and_var_kwargs(type_system):
    # ``*args``/``**kwargs`` must actually be passed to the callable.
    config.configuration.test_creation.skip_optional_parameter_probability = 0.0
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    factory = tf.TestFactory(cluster)
    func = _var_args_function(type_system)
    test_case = tc.TestCase()
    position = factory.append_generic_accessible(test_case, func)
    assert position >= 0
    call = _call_expr(test_case.get_statement(position).node)
    assert [arg.star for arg in call.args] == ["", "*", "**"]
    # a preceding POSITIONAL_OR_KEYWORD must go positionally alongside ``*args``
    assert call.args[0].keyword is None


@pytest.mark.parametrize("kind", ["enum", "method", "bad_function", "bad_method", "unknown"])
def test_append_generic_accessible(kind, type_system, constructor_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_generators_for = lambda _: [constructor_mock]
    factory = tf.TestFactory(cluster)
    test_case = tc.TestCase()

    accessible: gao.GenericAccessibleObject
    needle: str | None
    if kind == "enum":
        accessible = _make_enum()
        expected_ok, needle = True, "Color"
    elif kind == "method":
        # receiver is auto-created via the constructor generator
        accessible = gao.GenericMethod(
            owner=TypeInfo(SomeType),
            method=SomeType.simple_method,  # type: ignore[arg-type]
            inferred_signature=_make_signature(
                [Parameter("x", Parameter.POSITIONAL_OR_KEYWORD, annotation=int)],
                {"x": Instance(TypeInfo(int))},
                Instance(TypeInfo(float)),
                type_system,
            ),
        )
        expected_ok, needle = True, "simple_method"
    elif kind == "bad_function":
        accessible = _bad_function(type_system)
        expected_ok, needle = False, None
    elif kind == "bad_method":
        accessible = _bad_method(type_system)
        expected_ok, needle = False, None
    else:  # unknown accessible type
        accessible = MagicMock(gao.GenericAccessibleObject)
        expected_ok, needle = False, None

    result = factory.append_generic_accessible(test_case, accessible)
    if expected_ok:
        assert needle is not None
        assert result >= 0
        assert needle in test_case.to_code()
    else:
        assert result == -1


# ---------------------------------------------------------------------------
# Recursive object creation / depth limiting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["depth_limit", "no_generators", "success"])
def test_create_var_of_type(kind, constructor_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    if kind == "no_generators":
        cluster.get_generators_for = lambda _: []
    else:
        cluster.get_generators_for = lambda _: [constructor_mock]
    factory = tf.TestFactory(cluster)
    test_case = tc.TestCase()
    param_type = Instance(TypeInfo(SomeType))
    depth = config.configuration.test_creation.max_recursion if kind == "depth_limit" else 0

    name, _cursor = factory._create_var_of_type(test_case, param_type, SomeType, 0, depth)

    if kind == "success":
        assert name is not None
        assert test_case.size() >= 1
    else:
        assert name is None
        assert test_case.size() == 0


# ---------------------------------------------------------------------------
# change_random_call + _build_replacement_node
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["out_of_range", "primitive", "no_candidates"])
def test_change_random_call_returns_false(kind, function_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    # the statement's own accessible is the only generator -> no alternative
    cluster.get_generators_for = lambda _: {function_mock}
    factory = tf.TestFactory(cluster)
    if kind == "out_of_range":
        test_case = make_test_case(int_stmt("var_0", 1))
        position = 9
    elif kind == "primitive":
        # a primitive statement carries no callable accessible
        test_case = make_test_case(int_stmt("var_0", 1))
        position = 0
    else:  # no_candidates
        test_case = make_test_case(_call_with("var_0", "_.simple_function(z)", function_mock))
        position = 0
    assert factory.change_random_call(test_case, position) is False


def test_change_random_call_method_unbuildable(function_mock, method_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    calls = {"n": 0}

    def generators(_):
        calls["n"] += 1
        # first call yields the replacement candidate; receiver creation finds none
        return {function_mock, method_mock} if calls["n"] == 1 else []

    cluster.get_generators_for = generators
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(_call_with("var_0", "_.simple_function(z)", function_mock))
    assert factory.change_random_call(test_case, 0) is False


@pytest.mark.parametrize("kind", ["constructor", "function", "method", "enum"])
def test_change_random_call_success(kind, constructor_mock, function_mock, method_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    factory = tf.TestFactory(cluster)

    original: gao.GenericAccessibleObject
    replacement: gao.GenericAccessibleObject
    if kind == "constructor":
        original = function_mock
        replacement = constructor_mock
        statements = [_call_with("var_0", "_.simple_function(z)", original)]
        position = 0
    elif kind == "function":
        original = constructor_mock
        replacement = function_mock
        statements = [_call_with("var_0", "_.SomeType(y)", original)]
        position = 0
    elif kind == "method":
        original = function_mock
        replacement = method_mock
        statements = [
            assign("obj", "_.SomeType()", bound_type=SomeType),
            _call_with("var_1", "_.simple_function(z)", original),
        ]
        position = 1
    else:  # enum
        original = function_mock
        replacement = _make_enum()
        statements = [_call_with("var_0", "_.simple_function(z)", original)]
        position = 0

    cluster.get_generators_for = lambda _: {original, replacement}
    test_case = make_test_case(*statements)
    assert factory.change_random_call(test_case, position) is True
    assert _accessible_index(test_case, replacement) is not None


@pytest.mark.parametrize("kind", ["bad_function", "bad_method", "unknown"])
def test_change_random_call_unbuildable_replacement(kind, constructor_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    replacement: gao.GenericAccessibleObject
    if kind == "bad_function":
        replacement = _bad_function(type_system)
    elif kind == "bad_method":
        replacement = _bad_method(type_system)
    else:
        replacement = MagicMock(gao.GenericAccessibleObject)
    cluster.get_generators_for = lambda _: {constructor_mock, replacement}
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(_call_with("var_0", "_.SomeType(y)", constructor_mock))
    assert factory.change_random_call(test_case, 0) is False


# ---------------------------------------------------------------------------
# Low-level argument resolution / variable reuse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["mapped_collection", "unresolvable_fallback", "any_var_reuse"])
def test_resolve_arg_value(kind):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    cluster.get_generators_for = lambda _: []
    factory = tf.TestFactory(cluster)

    if kind == "mapped_collection":
        # abstract collection is not a literal type but maps to a concrete builtin
        test_case = tc.TestCase()
        value, _cursor = factory._resolve_arg_value(
            test_case, Instance(TypeInfo(list)), collections.abc.Iterable, 0, 0
        )
        assert isinstance(value, cst.BaseExpression)
    elif kind == "unresolvable_fallback":
        # unconstructible type with no reusable variable -> fallback literal
        test_case = tc.TestCase()
        value, _cursor = factory._resolve_arg_value(
            test_case, Instance(TypeInfo(SomeType)), SomeType, 0, 0
        )
        assert isinstance(value, cst.Name)
    else:  # any_var_reuse
        test_case = make_test_case(int_stmt("var_0", 1))
        with mock.patch.object(tf.randomness, "next_bool", return_value=True):
            value, _cursor = factory._resolve_arg_value(
                test_case, Instance(TypeInfo(SomeType)), SomeType, 1, 0
            )
        assert isinstance(value, cst.Name)
        assert value.value == "var_0"


@pytest.mark.parametrize("kind", ["none_raw", "primitive_reuse", "object_create"])
def test_create_or_reuse_var(kind, constructor_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    cluster.get_generators_for = lambda _: [constructor_mock]
    factory = tf.TestFactory(cluster)

    if kind == "none_raw":
        name, _cursor = factory._create_or_reuse_var(tc.TestCase(), AnyType(), None, 0, 0)
        assert name is None
    elif kind == "primitive_reuse":
        test_case = make_test_case(int_stmt("var_0", 1))
        with mock.patch.object(tf.randomness, "next_float", return_value=0.0):
            name, _cursor = factory._create_or_reuse_var(
                test_case, Instance(TypeInfo(int)), int, 1, 0
            )
        assert name == "var_0"
    else:  # object_create
        test_case = tc.TestCase()
        name, _cursor = factory._create_or_reuse_var(
            test_case, Instance(TypeInfo(SomeType)), SomeType, 0, 0
        )
        assert name is not None
        assert test_case.size() >= 1


@pytest.mark.parametrize(
    "position,expected",
    [
        (2, "var_0"),  # a bound variable in scope is returned
        (0, None),  # nothing in scope before position 0
    ],
)
def test_find_any_variable(position, expected):
    test_case = make_test_case(int_stmt("var_0", 1), int_stmt("var_1", 2))
    with mock.patch.object(tf.randomness, "choice", side_effect=operator.itemgetter(0)):
        result = tf.TestFactory._find_any_variable(test_case, position)
    assert result == expected


def test_mutate_call_skips_var_args_and_reuses_variable(type_system):
    # p is untyped (Any); *args/**kwargs are skipped; a prior variable is reused
    func = _var_args_function(type_system)
    test_case = make_test_case(
        int_stmt("var_0", 1),
        _call_with("var_1", "_.simple_function(var_0)", func, bound_type=float),
    )
    with mock.patch.object(tf.randomness, "next_bool", return_value=True):
        assert _make_factory().mutate_call(test_case, 1) is True
    call = _call_expr(test_case.get_statement(1).node)
    assert len(call.args) == 1  # only p survives; *args/**kwargs are dropped


def test_mutate_call_var_args_fallback_literal(type_system):
    # no reusable variable in scope -> untyped param falls back to a literal
    func = _var_args_function(type_system)
    test_case = make_test_case(_call_with("var_0", "_.simple_function()", func, bound_type=float))
    assert _make_factory().mutate_call(test_case, 0) is True


def test_mutate_call_bad_function_name_returns_false(type_system):
    func = _bad_function(type_system)
    test_case = make_test_case(_call_with("var_0", "_.thing()", func))
    assert _make_factory().mutate_call(test_case, 0) is False


def test_mutate_call_bad_method_name_returns_false(type_system):
    method = _bad_method(type_system)
    test_case = make_test_case(
        assign("obj", "_.SomeType()", bound_type=SomeType),
        _call_with("var_1", "obj.thing()", method),
    )
    assert _make_factory().mutate_call(test_case, 1) is False


# ---------------------------------------------------------------------------
# Complex-number & class/type-object primitives (DISABLED_SUBSYSTEMS point 15)
# ---------------------------------------------------------------------------


def _bare_cluster():
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()
    cluster.get_generators_for = lambda _: []
    return cluster


def test_resolve_arg_value_complex_emits_named_statement():
    factory = tf.TestFactory(_bare_cluster())
    test_case = tc.TestCase()
    value, cursor = factory._resolve_arg_value(
        test_case, Instance(TypeInfo(complex)), complex, 0, 0
    )
    assert isinstance(value, cst.Name)
    assert cursor == 1
    stmt = test_case.get_statement(0)
    assert stmt.bound_type is complex
    rhs = stmt.node.body[0].value
    assert isinstance(rhs, cst.Call)
    assert rhs.func.value == "complex"


def test_mutate_value_perturbs_complex():
    factory = tf.TestFactory(_bare_cluster())
    config.configuration.search_algorithm.random_perturbation = 0.0
    test_case = make_test_case(assign("var_0", "complex(1.0, 2.0)", bound_type=complex))
    assert factory.mutate_value(test_case, 0) is True
    rhs = test_case.get_statement(0).node.body[0].value
    assert isinstance(rhs, cst.Call)
    assert rhs.func.value == "complex"


def test_class_literal_candidates_include_builtins_and_sut_class():
    cluster = _bare_cluster()
    cluster.type_system.to_type_info(SomeType)
    config.configuration.module_name = SomeType.__module__
    factory = tf.TestFactory(cluster)
    rendered = {
        cst.Module(body=[]).code_for_node(node) for node in factory._class_literal_candidates()
    }
    assert "int" in rendered
    assert "object" in rendered
    alias = tf.get_module_alias(SomeType.__module__)
    assert f"{alias}.SomeType" in rendered


def test_resolve_arg_value_type_emits_class_literal():
    factory = tf.TestFactory(_bare_cluster())
    test_case = tc.TestCase()
    value, cursor = factory._resolve_arg_value(test_case, Instance(TypeInfo(type)), type, 0, 0)
    assert isinstance(value, cst.Name)
    assert cursor == 1
    assert test_case.get_statement(0).bound_type is type


def test_mutate_value_swaps_class_literal():
    factory = tf.TestFactory(_bare_cluster())
    test_case = make_test_case(assign("var_0", "int", bound_type=type))
    assert factory.mutate_value(test_case, 0) is True
    new_rhs = cst.Module(body=[]).code_for_node(test_case.get_statement(0).node.body[0].value)
    assert new_rhs != "int"
    assert test_case.get_statement(0).bound_type is type


# ---------------------------------------------------------------------------
# Reference-carrying collections (DISABLED_SUBSYSTEMS point 16)
# ---------------------------------------------------------------------------


def _cluster_with_sometype_generator(constructor_mock):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = TypeSystem()

    def gens(param_type):
        if isinstance(param_type, Instance) and param_type.type.raw_type is SomeType:
            return [constructor_mock]
        return []

    cluster.get_generators_for = gens
    return cluster


def _assert_refs_bound_before(test_case, index):
    """Every variable used by statement *index* is bound strictly before it."""
    bound_before = {
        s.bound_variable for s in test_case.statements()[:index] if s.bound_variable is not None
    }
    used = test_case.get_statement(index).used_variables()
    var_refs = {name for name in used if name.startswith("var_")}
    assert var_refs <= bound_before


def test_typed_list_collection_carries_references(constructor_mock):
    factory = tf.TestFactory(_cluster_with_sometype_generator(constructor_mock))
    config.configuration.test_creation.collection_reference_probability = 1.0
    list_type = Instance(TypeInfo(list), (Instance(TypeInfo(SomeType)),))
    saw_reference = False
    for _ in range(40):
        test_case = tc.TestCase()
        var, cursor = factory._emit_collection_statement(test_case, list, list_type, 0, 0)
        coll_index = cursor - 1
        coll_stmt = test_case.get_statement(coll_index)
        assert coll_stmt.bound_variable == var
        assert coll_stmt.bound_type is list
        _assert_refs_bound_before(test_case, coll_index)
        elements = coll_stmt.node.body[0].value.elements
        if any(
            isinstance(e.value, cst.Name) and e.value.value.startswith("var_") for e in elements
        ):
            saw_reference = True
    assert saw_reference


def test_typed_dict_keys_literal_values_referenceable(constructor_mock):
    factory = tf.TestFactory(_cluster_with_sometype_generator(constructor_mock))
    dict_type = Instance(TypeInfo(dict), (Instance(TypeInfo(str)), Instance(TypeInfo(SomeType))))
    for _ in range(20):
        test_case = tc.TestCase()
        _var, cursor = factory._emit_collection_statement(test_case, dict, dict_type, 0, 0)
        coll_index = cursor - 1
        _assert_refs_bound_before(test_case, coll_index)
        for entry in test_case.get_statement(coll_index).node.body[0].value.elements:
            # keys stay literal strings (never a var reference)
            assert not (isinstance(entry.key, cst.Name) and entry.key.value.startswith("var_"))


def test_untyped_collection_uses_reference_pool():
    factory = tf.TestFactory(_bare_cluster())
    config.configuration.test_creation.collection_reference_probability = 1.0
    saw_reference = False
    for _ in range(40):
        test_case = make_test_case(int_stmt("var_0", 1), int_stmt("var_1", 2))
        _var, cursor = factory._emit_collection_statement(test_case, list, None, 2, 0)
        coll_index = cursor - 1
        _assert_refs_bound_before(test_case, coll_index)
        elements = test_case.get_statement(coll_index).node.body[0].value.elements
        if any(
            isinstance(e.value, cst.Name) and e.value.value in {"var_0", "var_1"} for e in elements
        ):
            saw_reference = True
    assert saw_reference


def test_mutate_value_reference_list_keeps_refs_valid():
    factory = tf.TestFactory(_bare_cluster())
    config.configuration.search_algorithm.random_perturbation = 0.0
    config.configuration.test_creation.collection_reference_probability = 1.0
    for _ in range(30):
        test_case = make_test_case(
            int_stmt("var_0", 1),
            int_stmt("var_1", 2),
            assign("var_2", "[var_0]", bound_type=list),
        )
        assert factory.mutate_value(test_case, 2) is True
        _assert_refs_bound_before(test_case, 2)


def test_tuple_typed_collection_fixed_length(constructor_mock):
    factory = tf.TestFactory(_cluster_with_sometype_generator(constructor_mock))
    tuple_type = TupleType((Instance(TypeInfo(int)), Instance(TypeInfo(int))))
    test_case = tc.TestCase()
    _var, cursor = factory._emit_collection_statement(test_case, tuple, tuple_type, 0, 0)
    coll_index = cursor - 1
    elements = test_case.get_statement(coll_index).node.body[0].value.elements
    assert len(elements) == 2
    _assert_refs_bound_before(test_case, coll_index)


# ---------------------------------------------------------------------------
# Field-access statements (DISABLED_SUBSYSTEMS.md #13)
# ---------------------------------------------------------------------------


def _attr_rhs(node) -> cst.Attribute:
    """Extract the ``cst.Attribute`` RHS from a ``lhs = recv.field`` statement."""
    assert isinstance(node, cst.SimpleStatementLine)
    small = node.body[0]
    assert isinstance(small, cst.Assign)
    assert isinstance(small.value, cst.Attribute)
    return small.value


def _field(name, field_type=None):
    """Build a ``GenericField`` over ``SomeType`` for *name*."""
    return gao.GenericField(
        TypeInfo(SomeType), name, Instance(TypeInfo(float if field_type is None else field_type))
    )


def test_emit_accessible_field_creates_receiver(constructor_mock, field_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_generators_for = lambda _: [constructor_mock]
    factory = tf.TestFactory(cluster)
    test_case = tc.TestCase()

    pos = factory._emit_accessible(test_case, field_mock, 0, 0)

    assert pos >= 0
    field_stmt = test_case.get_statement(pos)
    assert field_stmt.accessible is field_mock
    assert field_stmt.bound_type is float
    attr = _attr_rhs(field_stmt.node)
    assert attr.attr.value == "y"
    receiver_name = attr.value.value
    # the receiver was constructed before the field access
    assert any(
        s.bound_variable == receiver_name and s.accessible is constructor_mock
        for s in test_case.statements()[:pos]
    )


def test_emit_accessible_field_no_receiver_returns_minus_one(field_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_generators_for = lambda _: []  # no way to build a receiver
    factory = tf.TestFactory(cluster)
    with mock.patch.object(tf.randomness, "next_bool", return_value=False):
        assert factory._emit_accessible(tc.TestCase(), field_mock, 0, 0) == -1


def test_change_random_field_call_swaps_field(field_mock, type_system):
    other = _field("z")
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_generators_for = lambda _: {field_mock, other}
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(
        assign("var_0", "_.SomeType()", bound_type=SomeType),
        _call_with("var_1", "var_0.y", field_mock, bound_type=float),
    )

    assert factory.change_random_field_call(test_case, 1) is True

    attr = _attr_rhs(test_case.get_statement(1).node)
    assert attr.value.value == "var_0"  # receiver preserved
    assert attr.attr.value == "z"  # field swapped
    assert test_case.get_statement(1).accessible is other
    assert test_case.get_statement(1).bound_variable == "var_1"


def test_change_random_field_call_no_alternatives(field_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_generators_for = lambda _: {field_mock}
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(
        assign("var_0", "_.SomeType()", bound_type=SomeType),
        _call_with("var_1", "var_0.y", field_mock, bound_type=float),
    )
    assert factory.change_random_field_call(test_case, 1) is False


def test_change_random_field_call_non_field_statement(constructor_mock):
    test_case = make_test_case(_call_with("var_0", "_.SomeType(y)", constructor_mock))
    assert _make_factory().change_random_field_call(test_case, 0) is False


def test_mutate_call_field_repicks_receiver(field_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(
        assign("var_0", "_.SomeType()", bound_type=SomeType),
        _call_with("var_1", "var_0.y", field_mock, bound_type=float),
    )

    assert factory.mutate_call(test_case, 1) is True

    attr = _attr_rhs(test_case.get_statement(1).node)
    assert attr.attr.value == "y"
    assert attr.value.value == "var_0"  # only one SomeType var in scope
    assert test_case.get_statement(1).accessible is field_mock
    assert test_case.get_statement(1).bound_variable == "var_1"


def test_mutate_call_field_no_receiver_returns_false(field_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(_call_with("var_0", "missing.y", field_mock, bound_type=float))
    assert factory.mutate_call(test_case, 0) is False


def test_field_statement_delete_cascade(field_mock):
    test_case = make_test_case(
        assign("var_0", "_.SomeType()", bound_type=SomeType),
        _call_with("var_1", "var_0.y", field_mock, bound_type=float),
    )
    # deleting the receiver cascades to the field read (name-based dependency)
    assert tf.TestFactory.delete_statement_gracefully(test_case, 0) is True
    assert test_case.size() == 0


# ---------------------------------------------------------------------------
# change_statement_type mutation operator (DISABLED_SUBSYSTEMS.md #14)
# ---------------------------------------------------------------------------


def test_change_statement_type_primitive():
    factory = _make_factory()
    test_case = make_test_case(int_stmt("var_0", 5), assign("var_1", "f(var_0)"))
    with mock.patch.object(tf.randomness, "next_float", return_value=0.0):
        assert factory.change_statement_type(test_case, 0) is True
    stmt0 = test_case.get_statement(0)
    assert stmt0.bound_variable == "var_0"
    assert stmt0.accessible is None
    assert stmt0.bound_type in {bool, float, str, bytes}  # different from int
    # later reader untouched, code still parses
    assert test_case.get_statement(1).bound_variable == "var_1"
    cst.parse_module(test_case.to_code())


def test_change_statement_type_collection():
    factory = _make_factory()
    test_case = make_test_case(int_stmt("var_0", 5))
    with mock.patch.object(tf.randomness, "next_float", return_value=0.5):
        assert factory.change_statement_type(test_case, 0) is True
    stmt0 = test_case.get_statement(0)
    assert stmt0.bound_type in {list, set, tuple, dict}
    assert stmt0.accessible is None


def test_change_statement_type_accessible_inserts_deps(constructor_mock, type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_random_accessible.return_value = constructor_mock
    cluster.get_generators_for = lambda _: [constructor_mock]
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(
        assign("var_0", "'x'", bound_type=str),
        assign("var_1", "f(var_0)"),
    )
    size_before = test_case.size()
    with mock.patch.object(tf.randomness, "next_float", return_value=1.0):
        assert factory.change_statement_type(test_case, 0) is True
    idx = _accessible_index(test_case, constructor_mock)
    assert idx is not None
    # the replaced statement keeps the original variable name
    assert test_case.get_statement(idx).bound_variable == "var_0"
    # a dependency statement was inserted (test case grew)
    assert test_case.size() > size_before
    cst.parse_module(test_case.to_code())


def test_change_statement_type_out_of_range():
    factory = _make_factory()
    test_case = make_test_case(int_stmt("var_0", 1))
    assert factory.change_statement_type(test_case, 5) is False


def test_change_statement_type_no_bound_variable():
    factory = _make_factory()
    test_case = make_test_case(stmt("print(1)"))
    assert factory.change_statement_type(test_case, 0) is False


def test_change_statement_type_no_accessible_available(type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_random_accessible.return_value = None
    factory = tf.TestFactory(cluster)
    test_case = make_test_case(int_stmt("var_0", 1))
    with mock.patch.object(tf.randomness, "next_float", return_value=1.0):
        assert factory.change_statement_type(test_case, 0) is False
