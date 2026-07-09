#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the LLM Deserializer."""

from unittest.mock import MagicMock, patch

import libcst as cst
import pytest

import pynguin.configuration as config
from pynguin.assertion.assertion import (
    CollectionLengthAssertion,
    FloatAssertion,
    IsInstanceAssertion,
    ObjectAssertion,
)
from pynguin.large_language_model.parsing.deserializer import (
    CstStatementDeserializer,
    deserialize_code_to_testcases,
    parse_assertion,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)


@pytest.fixture
def test_cluster():
    cluster = MagicMock()
    cluster.accessible_objects_under_test = []
    return cluster


@pytest.fixture(autouse=True)
def _reset_module_name(monkeypatch):
    # config.configuration is global mutable state; make sure tests that set
    # module_name don't leak into other tests.
    monkeypatch.setattr(config.configuration, "module_name", "")


def _deserialize_function(code: str, test_cluster, *, create_assertions: bool = True):
    """Parse *code* directly with libcst (bypassing the rewriter) and deserialize it.

    Useful for tests that need precise control over the CST shape without the
    rewriter's literal-hoisting rewriting the input first.
    """
    fn = cst.parse_module(code).body[0]
    assert isinstance(fn, cst.FunctionDef)
    deserializer = CstStatementDeserializer(test_cluster, create_assertions=create_assertions)
    return deserializer.deserialize_function(fn)


# ---------------------------------------------------------------------------
# Literal assigns set bound_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("literal", "expected_type"),
    [
        ("1", int),
        ("1.5", float),
        ('"hello"', str),
        ("True", bool),
        ("[]", list),
        ("{}", dict),
    ],
)
def test_literal_assign_sets_bound_type(test_cluster, literal, expected_type):
    code = f"def test_foo():\n    a = {literal}\n"
    testcase, total, parsed, uninterpreted = _deserialize_function(code, test_cluster)
    assert testcase.size() == 1
    stmt = testcase.get_statement(0)
    assert stmt.bound_type is expected_type
    assert stmt.bound_variable == "var_0"
    assert total == 1
    assert parsed == 1
    assert uninterpreted == 0


def test_deserialize_code_to_testcases_hoists_nonempty_collections(test_cluster):
    """Through the full pipeline, the rewriter hoists list/dict elements first.

    So the final collection assignment's RHS is no longer a pure literal and
    its bound_type is None (but the statement is still admitted).
    """
    code = """
def test_foo():
    e = [1, 2]
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result is not None
    testcase = result.test_cases[0]
    statements = testcase.statements()
    # var_0 = 1, var_1 = 2, e = [var_0, var_1]
    assert len(statements) == 3
    assert statements[0].bound_type is int
    assert statements[1].bound_type is int
    assert statements[2].bound_type is None
    assert result.uninterpreted_statements >= 1


# ---------------------------------------------------------------------------
# Variable renaming
# ---------------------------------------------------------------------------


def test_variable_renaming_to_var_n_and_consistent_references(test_cluster):
    code = """
def test_foo():
    x = 5
    y = x
    z = y
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    assert [s.bound_variable for s in testcase.statements()] == ["var_0", "var_1", "var_2"]
    source = testcase.to_code()
    assert "x" not in source
    assert "y" not in source
    assert "z" not in source
    assert source == "var_0 = 5\nvar_1 = var_0\nvar_2 = var_1\n"
    # The renamed code must actually execute without NameErrors.
    exec_globals: dict = {}
    exec(source, exec_globals)  # noqa: S102


def test_bound_statement_own_target_is_renamed_not_just_later_references(test_cluster):
    """Regression test for a renaming bug.

    The statement that introduces a new bound variable must rename its own
    assignment target, not just later references to it.
    """
    code = """
def test_foo():
    original_name = 42
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.bound_variable == "var_0"
    assert testcase.to_code() == "var_0 = 42\n"


# ---------------------------------------------------------------------------
# Call resolution
# ---------------------------------------------------------------------------


class _Foo:
    pass


def _make_constructor(owner_name: str, generated_type):
    owner = MagicMock()
    owner.name = owner_name
    ctor = MagicMock(spec=GenericConstructor)
    ctor.owner = owner
    gen_type = MagicMock()
    gen_type.type.raw_type = generated_type
    ctor.generated_type.return_value = gen_type
    return ctor


def _make_method(owner_name: str, method_name: str, generated_type):
    owner = MagicMock()
    owner.name = owner_name
    method = MagicMock(spec=GenericMethod)
    method.owner = owner
    method.method_name = method_name
    gen_type = MagicMock()
    gen_type.type.raw_type = generated_type
    method.generated_type.return_value = gen_type
    return method


def _make_function(function_name: str, generated_type):
    func = MagicMock(spec=GenericFunction)
    func.function_name = function_name
    gen_type = MagicMock()
    gen_type.type.raw_type = generated_type
    func.generated_type.return_value = gen_type
    return func


def test_call_resolution_generic_constructor(test_cluster):
    ctor = _make_constructor("Foo", _Foo)
    test_cluster.accessible_objects_under_test = [ctor]
    code = "def test_foo():\n    a = Foo()\n"
    testcase, _total, parsed, uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.bound_type is _Foo
    assert stmt.accessible is ctor
    assert parsed == 1
    assert uninterpreted == 0


def test_call_resolution_generic_method(test_cluster):
    ctor = _make_constructor("Foo", _Foo)
    method = _make_method(_Foo.__name__, "bar", str)
    test_cluster.accessible_objects_under_test = [ctor, method]
    code = "def test_foo():\n    a = Foo()\n    b = a.bar()\n"
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    method_stmt = testcase.get_statement(1)
    assert method_stmt.bound_type is str
    assert method_stmt.accessible is method
    assert testcase.to_code() == "var_0 = Foo()\nvar_1 = var_0.bar()\n"


def test_call_resolution_generic_function(test_cluster):
    func = _make_function("myfunc", int)
    test_cluster.accessible_objects_under_test = [func]
    code = "def test_foo():\n    a = myfunc()\n"
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.bound_type is int
    assert stmt.accessible is func


def test_call_resolution_unresolved_call_is_uninterpreted(test_cluster):
    test_cluster.accessible_objects_under_test = []
    code = "def test_foo():\n    a = some_unknown_call()\n"
    testcase, _total, parsed, uninterpreted = _deserialize_function(code, test_cluster)
    # names not in scope -> dropped entirely
    assert testcase.size() == 0
    assert parsed == 0
    assert uninterpreted == 0


# ---------------------------------------------------------------------------
# Partial parse
# ---------------------------------------------------------------------------


def test_partial_parse_drops_unknown_name_keeps_rest(test_cluster):
    code = """
def test_incomplete():
    var_0 = 2
    x = some_unknown_func()
    y = var_0
"""
    testcase, total, parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    assert testcase.size() == 2
    assert parsed < total
    rendered = testcase.to_code()
    assert "some_unknown_func" not in rendered


def test_deserializer_handles_invalid_code_returns_none(test_cluster):
    with patch(
        "pynguin.large_language_model.parsing.deserializer.rewrite_tests",
        return_value={"test_x": "def test_x(:"},
    ):
        result = deserialize_code_to_testcases("irrelevant source", test_cluster)
    assert result is None


def test_empty_function_is_dropped(test_cluster):
    code = "def test_empty():\n    pass\n"
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result is not None
    assert result.test_cases == []


def test_compound_statement_is_dropped(test_cluster):
    code = """
def test_foo():
    x = 1
    if x:
        y = 2
    z = x
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    rendered = testcase.to_code()
    assert "if" not in rendered
    assert [s.bound_variable for s in testcase.statements()] == ["var_0", "var_1"]


# ---------------------------------------------------------------------------
# Assertion shapes (through the full deserializer, using directly-fed CST so the
# rewriter's comparison-hoisting does not obscure the shape under test).
# ---------------------------------------------------------------------------


def test_assertion_bare_name_becomes_object_assertion_true(test_cluster):
    code = """
def test_foo():
    x = True
    assert x
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("var_0", value=True)]


def test_assertion_equality_with_literal_becomes_object_assertion(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x == 5
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("var_0", 5)]


def test_assertion_equality_with_float_literal_becomes_float_assertion(test_cluster):
    code = """
def test_foo():
    x = 5.0
    assert x == 5.0
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [FloatAssertion("var_0", 5.0)]


def test_assertion_isinstance_builtin_becomes_isinstance_assertion(test_cluster):
    code = """
def test_foo():
    x = 5
    assert isinstance(x, int)
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [IsInstanceAssertion("var_0", "builtins", "int")]


def test_assertion_isinstance_module_type_becomes_isinstance_assertion(test_cluster, monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "mymodule")
    code = """
def test_foo():
    x = mymodule_.Foo()
    assert isinstance(x, mymodule_.Foo)
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [IsInstanceAssertion("var_0", "mymodule", "Foo")]


def test_assertion_len_equality_becomes_collection_length_assertion(test_cluster):
    code = """
def test_foo():
    x = [1, 2]
    assert len(x) == 2
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [CollectionLengthAssertion("var_0", 2)]


def test_assertion_or_split_uses_first_parseable_operand(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x == 5 or unknown_thing == 1
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("var_0", 5)]


def test_assertion_or_split_falls_back_to_second_operand(test_cluster):
    code = """
def test_foo():
    x = 5
    assert unknown_thing == 1 or x == 5
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("var_0", 5)]


def test_assertion_unsupported_shape_kept_as_raw_statement_when_known(test_cluster):
    code = """
def test_foo():
    x = 5
    assert callable(x)
"""
    testcase, _total, _parsed, uninterpreted = _deserialize_function(code, test_cluster)
    assert testcase.size() == 2
    assert testcase.get_statement(1).bound_variable is None
    assert testcase.get_statement(1).assertions == []
    assert uninterpreted == 1
    # And the raw assert must be renamed consistently with the bound variable.
    assert testcase.to_code() == "var_0 = 5\nassert callable(var_0)\n"


def test_assertion_unsupported_shape_with_unknown_name_is_dropped(test_cluster):
    code = """
def test_foo():
    x = 5
    assert some_unknown_predicate(x)
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    assert testcase.size() == 1
    assert "assert" not in testcase.to_code()


def test_create_assertions_false_drops_all_asserts(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x
"""
    testcase, _total, _parsed, _uninterpreted = _deserialize_function(
        code, test_cluster, create_assertions=False
    )
    assert testcase.size() == 1
    assert testcase.get_statement(0).assertions == []


def test_assert_does_not_count_toward_total_statements(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x
"""
    _testcase, total, _parsed, _uninterpreted = _deserialize_function(code, test_cluster)
    assert total == 1


# ---------------------------------------------------------------------------
# SUT alias normalization
# ---------------------------------------------------------------------------


def test_sut_alias_normalization_import_as(test_cluster, monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "foo.bar")
    code = """
def test_foo():
    import foo.bar as m
    x = m.f(1)
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result is not None
    rendered = result.test_cases[0].to_code()
    assert "import" not in rendered
    assert "bar_.f(" in rendered


def test_sut_alias_normalization_from_import(test_cluster, monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "foo.bar")
    code = """
def test_foo():
    from foo.bar import baz
    x = baz(1)
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result is not None
    rendered = result.test_cases[0].to_code()
    assert "import" not in rendered
    assert "bar_.baz(" in rendered


def test_non_sut_import_kept_as_raw_statement(test_cluster, monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "foo.bar")
    code = """
def test_foo():
    import math
    x = math.pi
"""
    testcase, total, parsed, uninterpreted = _deserialize_function(code, test_cluster)
    rendered = testcase.to_code()
    assert "import math" in rendered
    assert parsed >= 2
    assert uninterpreted >= 1
    assert total >= 1


# ---------------------------------------------------------------------------
# parse_assertion, tested directly
# ---------------------------------------------------------------------------


def _known(**types):
    return types


def test_parse_assertion_bare_name():
    node = cst.parse_statement("assert x").body[0]
    result = parse_assertion(node, _known(x=bool))
    assert result == ("x", ObjectAssertion("x", value=True))


def test_parse_assertion_bare_name_unknown_var_returns_none():
    node = cst.parse_statement("assert unknown_var").body[0]
    assert parse_assertion(node, _known()) is None


def test_parse_assertion_equality_with_int_literal():
    node = cst.parse_statement("assert x == 5").body[0]
    result = parse_assertion(node, _known(x=int))
    assert result == ("x", ObjectAssertion("x", 5))


def test_parse_assertion_is_with_none_literal():
    node = cst.parse_statement("assert x is None").body[0]
    result = parse_assertion(node, _known(x=type(None)))
    assert result == ("x", ObjectAssertion("x", None))


def test_parse_assertion_equality_with_float_literal():
    node = cst.parse_statement("assert x == 2.5").body[0]
    result = parse_assertion(node, _known(x=float))
    assert result == ("x", FloatAssertion("x", 2.5))


def test_parse_assertion_isinstance_builtin():
    node = cst.parse_statement("assert isinstance(x, str)").body[0]
    result = parse_assertion(node, _known(x=str))
    assert result == ("x", IsInstanceAssertion("x", "builtins", "str"))


def test_parse_assertion_isinstance_module_attribute(monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "pkg.mod")
    node = cst.parse_statement("assert isinstance(x, mod_.Foo)").body[0]
    result = parse_assertion(node, _known(x=None))
    assert result == ("x", IsInstanceAssertion("x", "pkg.mod", "Foo"))


def test_parse_assertion_isinstance_unknown_receiver_returns_none():
    node = cst.parse_statement("assert isinstance(y, int)").body[0]
    assert parse_assertion(node, _known(x=int)) is None


def test_parse_assertion_len_equality():
    node = cst.parse_statement("assert len(x) == 3").body[0]
    result = parse_assertion(node, _known(x=list))
    assert result == ("x", CollectionLengthAssertion("x", 3))


def test_parse_assertion_len_equality_unknown_receiver_returns_none():
    node = cst.parse_statement("assert len(y) == 3").body[0]
    assert parse_assertion(node, _known(x=list)) is None


def test_parse_assertion_or_split_first_operand():
    node = cst.parse_statement("assert x == 1 or y == 2").body[0]
    result = parse_assertion(node, _known(x=int))
    assert result == ("x", ObjectAssertion("x", 1))


def test_parse_assertion_or_split_second_operand():
    node = cst.parse_statement("assert y == 2 or x == 1").body[0]
    result = parse_assertion(node, _known(x=int))
    assert result == ("x", ObjectAssertion("x", 1))


def test_parse_assertion_or_split_neither_operand_parseable():
    node = cst.parse_statement("assert y == 2 or z == 1").body[0]
    assert parse_assertion(node, _known(x=int)) is None


def test_parse_assertion_unsupported_shape_returns_none():
    node = cst.parse_statement("assert some_call(x)").body[0]
    assert parse_assertion(node, _known(x=int)) is None


def test_parse_assertion_from_string():
    result = parse_assertion("assert x == 1", _known(x=int))
    assert result == ("x", ObjectAssertion("x", 1))


def test_parse_assertion_unparseable_string_returns_none():
    assert parse_assertion("this is not python at all !!!", _known()) is None


def test_parse_assertion_non_assert_string_returns_none():
    assert parse_assertion("x = 1", _known(x=int)) is None
