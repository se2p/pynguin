#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the LLM Deserializer."""

from collections import Counter
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
    Disposition,
    ParseStatus,
    deserialize_code_to_testcases,
    parse_assertion,
)
from pynguin.large_language_model.parsing.rewriter import RewrittenTests
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
    rewriter's literal-hoisting rewriting the input first. Returns the
    ``FunctionDeserialization`` (``test_case`` plus per-``Disposition`` ``counts``).
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
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 1
    stmt = testcase.get_statement(0)
    assert stmt.bound_type is expected_type
    assert stmt.bound_variable == "a"
    assert result.counts == Counter({Disposition.ADMITTED: 1})


def test_deserialize_code_to_testcases_keeps_collections(test_cluster):
    """Collection assignment RHS is parsed and bound_type is list directly."""
    code = """
def test_foo():
    e = [1, 2]
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    testcase = result.test_cases[0]
    statements = testcase.statements()
    assert len(statements) == 1
    assert statements[0].bound_type is list
    assert statements[0].bound_variable == "e"
    assert result.counts[Disposition.ADMITTED] == 1


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
    testcase = _deserialize_function(code, test_cluster).test_case
    assert [s.bound_variable for s in testcase.statements()] == ["x", "y", "z"]
    source = testcase.to_code()
    assert source == "x = 5\ny = x\nz = y\n"
    # The code must actually execute without NameErrors.
    exec_globals: dict = {}
    exec(source, exec_globals)  # noqa: S102


def test_bound_statement_own_target_is_renamed_not_just_later_references(test_cluster):
    """Test variable target binding preservation."""
    code = """
def test_foo():
    original_name = 42
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.bound_variable == "original_name"
    assert testcase.to_code() == "original_name = 42\n"


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
    result = _deserialize_function(code, test_cluster)
    stmt = result.test_case.get_statement(0)
    assert stmt.bound_type is _Foo
    assert stmt.accessible is ctor
    assert result.counts == Counter({Disposition.ADMITTED: 1})


def test_call_resolution_generic_method(test_cluster):
    ctor = _make_constructor("Foo", _Foo)
    method = _make_method(_Foo.__name__, "bar", str)
    test_cluster.accessible_objects_under_test = [ctor, method]
    code = "def test_foo():\n    a = Foo()\n    b = a.bar()\n"
    testcase = _deserialize_function(code, test_cluster).test_case
    method_stmt = testcase.get_statement(1)
    assert method_stmt.bound_type is str
    assert method_stmt.accessible is method
    assert testcase.to_code() == "a = Foo()\nb = a.bar()\n"


def test_call_resolution_generic_function(test_cluster):
    func = _make_function("myfunc", int)
    test_cluster.accessible_objects_under_test = [func]
    code = "def test_foo():\n    a = myfunc()\n"
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.bound_type is int
    assert stmt.accessible is func


def test_call_to_unknown_name_is_dropped(test_cluster):
    test_cluster.accessible_objects_under_test = []
    code = "def test_foo():\n    a = some_unknown_call()\n"
    result = _deserialize_function(code, test_cluster)
    # names not in scope -> dropped entirely
    assert result.test_case.size() == 0
    assert result.counts == Counter({Disposition.DROPPED_UNKNOWN_NAMES: 1})


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
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 2
    assert result.counts[Disposition.DROPPED_UNKNOWN_NAMES] == 1
    # var_0 = 2 resolves as a literal; y = var_0 is admitted but unresolved
    # (its RHS is a bare name, not a literal or a resolvable call).
    assert result.counts[Disposition.ADMITTED] == 1
    assert result.counts[Disposition.ADMITTED_UNRESOLVED_CALL] == 1
    rendered = testcase.to_code()
    assert "some_unknown_func" not in rendered


def test_deserializer_handles_invalid_code_returns_unparseable(test_cluster):
    with patch(
        "pynguin.large_language_model.parsing.deserializer.rewrite_tests",
        return_value=RewrittenTests(functions={"test_x": "def test_x(:"}, module_imports=[]),
    ):
        result = deserialize_code_to_testcases("irrelevant source", test_cluster)
    assert result.status is ParseStatus.UNPARSEABLE
    assert result.test_cases == []
    assert result.counts == Counter()


def test_empty_function_is_dropped(test_cluster):
    code = "def test_empty():\n    pass\n"
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    assert result.test_cases == []


def test_compound_statement_is_admitted_whole(test_cluster):
    code = """
def test_foo():
    x = 1
    if x:
        y = 2
    z = x
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    rendered = testcase.to_code()
    assert "if x:" in rendered
    assert "y = 2" in rendered
    assert [s.bound_variable for s in testcase.statements()] == ["x", None, "z"]
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 1


def test_compound_with_block_internal_binding_is_local(test_cluster):
    code = """
def test_foo():
    path = "x"
    with open(path) as handle:
        for line in handle:
            data = line
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    rendered = testcase.to_code()
    assert "with open(path) as handle:" in rendered
    assert "for line in handle:" in rendered
    assert [s.bound_variable for s in testcase.statements()] == ["path", None]
    assert result.counts[Disposition.ADMITTED] == 1
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 1


def test_compound_statement_with_unknown_external_read_is_dropped(test_cluster):
    code = """
def test_foo():
    for item in undefined_name:
        y = item
"""
    result = _deserialize_function(code, test_cluster)
    assert result.test_case.size() == 0
    assert result.counts == Counter({Disposition.DROPPED_UNKNOWN_NAMES: 1})


def test_compound_classdef_is_admitted_and_binds_name(test_cluster):
    code = """
def test_foo():
    class MyClass:
        pass
    inst = MyClass()
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 2
    assert [s.bound_variable for s in testcase.statements()] == ["MyClass", "inst"]
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 1
    assert result.counts[Disposition.ADMITTED_UNRESOLVED_CALL] == 1


def test_compound_classdef_inheritance_with_known_base(test_cluster):
    code = """
def test_foo():
    class BaseClass:
        pass
    class SubClass(BaseClass):
        pass
    inst = SubClass()
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 3
    assert [s.bound_variable for s in testcase.statements()] == [
        "BaseClass",
        "SubClass",
        "inst",
    ]
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 2
    assert result.counts[Disposition.ADMITTED_UNRESOLVED_CALL] == 1


def test_compound_classdef_inheritance_with_unknown_base_is_dropped(test_cluster):
    code = """
def test_foo():
    class SubClass(UndefinedBase):
        pass
"""
    result = _deserialize_function(code, test_cluster)
    assert result.test_case.size() == 0
    assert result.counts == Counter({Disposition.DROPPED_UNKNOWN_NAMES: 1})


def test_compound_functiondef_binds_name_for_subsequent_calls(test_cluster):
    code = """
def test_foo():
    def helper(arg):
        return arg + 1
    res = helper(1)
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 2
    assert [s.bound_variable for s in testcase.statements()] == ["helper", "res"]
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 1
    assert result.counts[Disposition.ADMITTED_UNRESOLVED_CALL] == 1


def test_compound_class_and_function_property_pattern(test_cluster):
    code = """
def test_prop():
    call_count = 0
    def my_prop(cls):
        return cls.__name__ + '_value'
    class MyClass:
        pass
    result = my_prop(MyClass)
    assert result == 'MyClass_value'
"""
    result = _deserialize_function(code, test_cluster, create_assertions=True)
    testcase = result.test_case
    assert testcase.size() == 4
    assert [s.bound_variable for s in testcase.statements()] == [
        "call_count",
        "my_prop",
        "MyClass",
        "result",
    ]
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 2
    assert result.counts[Disposition.ASSERTION_LIFTED] == 1


def test_deserialize_code_to_testcases_with_nested_class_and_function(test_cluster):
    code = """
class TestSuite:
    def test_descriptor(self):
        class Target:
            pass
        def helper(cls):
            return 42
        val = helper(Target)
        assert val == 42
"""
    result = deserialize_code_to_testcases(code, test_cluster, create_assertions=True)
    assert result.status is ParseStatus.OK
    assert len(result.test_cases) == 1
    testcase = result.test_cases[0]
    assert testcase.size() == 3
    assert [s.bound_variable for s in testcase.statements()] == [
        "Target",
        "helper",
        "val",
    ]
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 2
    assert result.counts[Disposition.ASSERTION_LIFTED] == 1


def test_deserialize_nested_class_with_self_attributes_runs(test_cluster):
    """End-to-end: a nested class using ``self.`` deserializes into runnable code.

    Regression for issue #274: the rewriter used to strip ``self.`` from nested local
    classes, so the emitted (compound-admitted) test raised ``UnboundLocalError`` at
    runtime and contributed no coverage. The exported code must both parse and execute.
    """
    code = """
class TestCounter:
    def test_bump(self):
        class Counter:
            def __init__(self):
                self.n = 0
            def bump(self):
                self.n += 1
                return self.n
        c = Counter()
        r = c.bump()
        assert r == 1
"""
    result = deserialize_code_to_testcases(code, test_cluster, create_assertions=True)
    assert result.status is ParseStatus.OK
    assert len(result.test_cases) == 1
    source = result.test_cases[0].to_code()
    assert "self.n = 0" in source
    assert "self.n += 1" in source
    # The exported test must run without raising.
    exec(source, {})  # noqa: S102


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
    result = _deserialize_function(code, test_cluster)
    stmt = result.test_case.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("x", value=True)]
    assert result.counts[Disposition.ASSERTION_LIFTED] == 1


def test_assertion_equality_with_literal_becomes_object_assertion(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x == 5
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("x", 5)]


def test_assertion_equality_with_float_literal_becomes_float_assertion(test_cluster):
    code = """
def test_foo():
    x = 5.0
    assert x == 5.0
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [FloatAssertion("x", 5.0)]


def test_assertion_isinstance_builtin_becomes_isinstance_assertion(test_cluster):
    code = """
def test_foo():
    x = 5
    assert isinstance(x, int)
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [IsInstanceAssertion("x", "builtins", "int")]


def test_assertion_isinstance_module_type_becomes_isinstance_assertion(test_cluster, monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "mymodule")
    code = """
def test_foo():
    x = mymodule_.Foo()
    assert isinstance(x, mymodule_.Foo)
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [IsInstanceAssertion("x", "mymodule", "Foo")]


def test_assertion_len_equality_becomes_collection_length_assertion(test_cluster):
    code = """
def test_foo():
    x = [1, 2]
    assert len(x) == 2
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [CollectionLengthAssertion("x", 2)]


def test_assertion_or_split_uses_first_parseable_operand(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x == 5 or unknown_thing == 1
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("x", 5)]


def test_assertion_or_split_falls_back_to_second_operand(test_cluster):
    code = """
def test_foo():
    x = 5
    assert unknown_thing == 1 or x == 5
"""
    testcase = _deserialize_function(code, test_cluster).test_case
    stmt = testcase.get_statement(0)
    assert stmt.assertions == [ObjectAssertion("x", 5)]


def test_assertion_unsupported_shape_kept_as_raw_statement_when_known(test_cluster):
    code = """
def test_foo():
    x = 5
    assert callable(x)
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 2
    assert testcase.get_statement(1).bound_variable is None
    assert testcase.get_statement(1).assertions == []
    assert result.counts[Disposition.ASSERTION_KEPT_RAW] == 1
    assert testcase.to_code() == "x = 5\nassert callable(x)\n"


def test_assertion_unsupported_shape_with_unknown_name_is_dropped(test_cluster):
    code = """
def test_foo():
    x = 5
    assert some_unknown_predicate(x)
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 1
    assert "assert" not in testcase.to_code()
    assert result.counts[Disposition.ASSERTION_DROPPED] == 1


def test_create_assertions_false_drops_all_asserts(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x
"""
    result = _deserialize_function(code, test_cluster, create_assertions=False)
    testcase = result.test_case
    assert testcase.size() == 1
    assert testcase.get_statement(0).assertions == []
    # A skipped assert is not tallied under any assertion disposition.
    assert result.counts[Disposition.ASSERTION_LIFTED] == 0
    assert result.counts[Disposition.ASSERTION_KEPT_RAW] == 0
    assert result.counts[Disposition.ASSERTION_DROPPED] == 0


def test_assert_is_not_counted_as_a_statement(test_cluster):
    code = """
def test_foo():
    x = 5
    assert x
"""
    result = _deserialize_function(code, test_cluster)
    # The assert is tracked as a lifted assertion, not as a statement.
    assert result.counts[Disposition.ADMITTED] == 1
    assert result.counts[Disposition.ASSERTION_LIFTED] == 1


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
    assert result.status is ParseStatus.OK
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
    assert result.status is ParseStatus.OK
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
    result = _deserialize_function(code, test_cluster)
    rendered = result.test_case.to_code()
    assert "import math" in rendered
    assert result.counts[Disposition.ADMITTED_IMPORT] == 1
    assert result.counts[Disposition.ADMITTED_UNRESOLVED_CALL] == 1


# ---------------------------------------------------------------------------
# Ambient names respect element_visibility (Issue #285)
# ---------------------------------------------------------------------------


def _write_module_with_protected_helper(monkeypatch, tmp_path, name):
    mod_file = tmp_path / f"{name}.py"
    mod_file.write_text("def _protected_helper():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(config.configuration, "project_path", str(tmp_path))
    monkeypatch.setattr(config.configuration, "module_name", name)
    monkeypatch.syspath_prepend(str(tmp_path))


def test_call_to_non_visible_module_function_dropped_by_default(
    test_cluster, monkeypatch, tmp_path
):
    """Regression test for Issue #285.

    A call to a module-level helper that ``element_visibility`` (default
    ``PUBLIC``) excludes from the test cluster's public API must be dropped
    as an unknown name at admission, not kept as an ``ADMITTED_UNRESOLVED_CALL``
    that only fails later, at export.
    """
    _write_module_with_protected_helper(monkeypatch, tmp_path, "mod_285_public")
    code = """
def test_foo():
    x = _protected_helper()
"""
    result = _deserialize_function(code, test_cluster)
    assert result.test_case.size() == 0
    assert result.counts == Counter({Disposition.DROPPED_UNKNOWN_NAMES: 1})


def test_call_to_non_visible_module_function_admitted_with_visibility_all(
    test_cluster, monkeypatch, tmp_path
):
    """The same call is admitted once ``element_visibility`` includes it.

    It becomes part of the ambient names and is then only unresolved, not
    an unknown name.
    """
    monkeypatch.setattr(config.configuration, "element_visibility", config.ElementVisibility.ALL)
    _write_module_with_protected_helper(monkeypatch, tmp_path, "mod_285_all")
    code = """
def test_foo():
    x = _protected_helper()
"""
    result = _deserialize_function(code, test_cluster)
    assert result.counts == Counter({Disposition.ADMITTED_UNRESOLVED_CALL: 1})


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


def test_parse_assertion_isinstance_non_sut_module_resolves_to_real_module(monkeypatch):
    """A dotted type from a non-SUT module keeps that module, not the SUT module.

    Regression for #275: every dotted type used to be attributed to
    ``config.module_name``, so ``collections.defaultdict`` was exported as
    ``<sut_alias>.defaultdict`` and raised ``AttributeError`` at runtime.
    """
    monkeypatch.setattr(config.configuration, "module_name", "pytutils.trees")
    node = cst.parse_statement("assert isinstance(x, collections.defaultdict)").body[0]
    result = parse_assertion(node, _known(x=None))
    assert result == ("x", IsInstanceAssertion("x", "collections", "defaultdict"))


def test_parse_assertion_isinstance_unresolvable_module_not_lifted(monkeypatch):
    """A dotted type that resolves to no importable module is left for the raw fallback."""
    monkeypatch.setattr(config.configuration, "module_name", "pytutils.trees")
    node = cst.parse_statement("assert isinstance(x, nonexistent_pkg.Thing)").body[0]
    assert parse_assertion(node, _known(x=None)) is None


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


# ---------------------------------------------------------------------------
# Module-level imports for mocking / context managers (issue #278)
# ---------------------------------------------------------------------------


def test_module_level_mock_import_enables_with_patch_block(test_cluster):
    """A ``with patch(...)`` block is admitted once its import is hoisted."""
    code = """
from unittest.mock import patch

def test_foo():
    with patch("os.getcwd") as p:
        x = 1
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    testcase = result.test_cases[0]
    rendered = testcase.to_code()
    assert "from unittest.mock import patch" in rendered
    assert "with patch(" in rendered
    assert result.counts[Disposition.ADMITTED_IMPORT] == 1
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 1
    assert result.counts[Disposition.DROPPED_UNKNOWN_NAMES] == 0


def test_module_level_tempfile_import_enables_with_block(test_cluster):
    """A ``with tempfile.TemporaryDirectory()`` block is admitted once hoisted."""
    code = """
import tempfile

def test_foo():
    with tempfile.TemporaryDirectory() as d:
        y = 2
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    testcase = result.test_cases[0]
    rendered = testcase.to_code()
    assert "import tempfile" in rendered
    assert "with tempfile.TemporaryDirectory()" in rendered
    assert result.counts[Disposition.ADMITTED_COMPOUND] == 1


def test_unreferenced_module_import_is_not_hoisted(test_cluster):
    """An import a test does not reference is not attached to it."""
    code = """
import os
import tempfile

def test_foo():
    with tempfile.TemporaryDirectory() as d:
        y = 2
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    rendered = result.test_cases[0].to_code()
    assert "import tempfile" in rendered
    assert "import os" not in rendered


def test_tzlocal_style_mock_test_produces_nonempty_testcase(test_cluster):
    """The mock+attr-assign shape from the issue yields a runnable test case."""
    code = """
from unittest.mock import patch, MagicMock

def test_localzone():
    mock_env = MagicMock()
    mock_env.return_value = "UTC"
    with patch("os.environ", {"TZ": "UTC"}):
        result = 1
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    assert len(result.test_cases) == 1
    testcase = result.test_cases[0]
    assert testcase.size() > 0
    rendered = testcase.to_code()
    assert "mock_env.return_value" in rendered
    assert "with patch(" in rendered


# ---------------------------------------------------------------------------
# Attribute-target assignments (issue #278)
# ---------------------------------------------------------------------------


def test_attribute_target_assignment_on_known_receiver_is_admitted(test_cluster):
    code = """
def test_foo():
    m = []
    m.attr = 5
"""
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 2
    assert [s.bound_variable for s in testcase.statements()] == ["m", None]
    assert "m.attr = 5" in testcase.to_code()
    assert result.counts[Disposition.ADMITTED] == 2


def test_attribute_target_assignment_on_unknown_receiver_is_dropped(test_cluster):
    code = """
def test_foo():
    undefined_obj.attr = 5
"""
    result = _deserialize_function(code, test_cluster)
    assert result.test_case.size() == 0
    assert result.counts == Counter({Disposition.DROPPED_UNKNOWN_NAMES: 1})


# ---------------------------------------------------------------------------
# Docstring and string literal handling (issue #280)
# ---------------------------------------------------------------------------


def test_docstring_is_not_admitted_as_statement(test_cluster):
    code = '''
def test_foo():
    """This is a docstring explaining the test."""
    x = 1
'''
    result = _deserialize_function(code, test_cluster)
    testcase = result.test_case
    assert testcase.size() == 1
    assert "docstring" not in testcase.to_code()
    assert result.counts[Disposition.DROPPED_UNSUPPORTED_SHAPE] == 1
    assert result.counts[Disposition.ADMITTED] == 1


def test_docstring_only_function_is_not_admitted(test_cluster):
    code = '''
def test_3():
    """
    Test the branch where key is not None and a matching element is found.
    This exercises the else branch with key(el) returning True.
    """
'''
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    assert len(result.test_cases) == 0
    assert result.counts[Disposition.DROPPED_UNSUPPORTED_SHAPE] == 1


def test_docstring_with_dropped_statements_does_not_admit_empty_testcase(test_cluster):
    code = '''
def test_3():
    """Docstring explaining what we intended to test."""
    result = undefined_func()
    assert result == 1
'''
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result.status is ParseStatus.OK
    assert len(result.test_cases) == 0
    assert result.counts[Disposition.DROPPED_UNSUPPORTED_SHAPE] == 1
    assert result.counts[Disposition.DROPPED_UNKNOWN_NAMES] == 1
