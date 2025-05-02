#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import enum

from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_to_ast as ata
import pynguin.testcase.variablereference as vr
import pynguin.utils.ast_util as au

from pynguin.utils.namingscope import NamingScope


@pytest.fixture
def assertion_to_ast_ref() -> tuple[ata.PyTestAssertionToAstVisitor, vr.VariableReference]:
    scope = NamingScope()
    module_aliases = NamingScope(prefix="module")
    var = vr.VariableReference(MagicMock(), None)
    return (
        ata.PyTestAssertionToAstVisitor(
            scope,
            module_aliases,
            set(),
            statement_node=au.create_ast_assign(
                au.create_ast_name(scope.get_name(var)), au.create_ast_constant(5)
            ),
        ),
        var,
    )


def __create_source_from_ast(module_body: list[ast.stmt]) -> str:
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=module_body, type_ignores=[])))


def test_type_name(assertion_to_ast_ref):
    assertion_to_ast, ref = assertion_to_ast_ref
    assertion = ass.TypeNameAssertion(source=ref, module="foo", qualname="bar")
    assertion.accept(assertion_to_ast)
    assert (
        __create_source_from_ast(assertion_to_ast.nodes)
        == "var_0 = 5\nassert f'{type(var_0).__module__}.{type(var_0).__qualname__}' "
        "== 'foo.bar'"
    )


@pytest.mark.parametrize(
    "obj,output",
    [
        (True, "assert var_0 is True"),
        (False, "assert var_0 is False"),
        ((True, False), "assert var_0 == (True, False)"),
        ([3, 8], "assert var_0 == [3, 8]"),
        ([[3, 8], {"foo"}], "assert var_0 == [[3, 8], {'foo'}]"),
        (
            {"foo": ["nope", 1, False, None]},
            "assert var_0 == {'foo': ['nope', 1, False, None]}",
        ),
        (
            {"foo": "bar", "baz": "argh"},
            "assert var_0 == {'foo': 'bar', 'baz': 'argh'}",
        ),
        (
            {enum.Enum("Dummy", "a").a: False},
            "assert var_0 == {module_0.Dummy.a: False}",
        ),
    ],
)
def test_object_assertion(assertion_to_ast_ref, obj, output):
    assertion_to_ast, ref = assertion_to_ast_ref
    assertion = ass.ObjectAssertion(source=ref, value=obj)
    assertion.accept(assertion_to_ast)
    assert __create_source_from_ast(assertion_to_ast.nodes) == "var_0 = 5\n" + output


def test_float_assertion(assertion_to_ast_ref):
    assertion_to_ast, ref = assertion_to_ast_ref
    assertion = ass.FloatAssertion(source=ref, value=1.5)
    assertion.accept(assertion_to_ast)
    assert (
        __create_source_from_ast(assertion_to_ast.nodes)
        == "var_0 = 5\nassert var_0 == pytest.approx(1.5, abs=0.01, rel=0.01)"
    )


@pytest.mark.parametrize(
    "length, output",
    [(0, "assert len(var_0) == 0"), (42, "assert len(var_0) == 42")],
)
def test_collection_length(assertion_to_ast_ref, length, output):
    assertion_to_ast, ref = assertion_to_ast_ref
    assertion = ass.CollectionLengthAssertion(source=ref, length=length)
    assertion.accept(assertion_to_ast)
    assert __create_source_from_ast(assertion_to_ast.nodes) == "var_0 = 5\n" + output


def test_raises_exception(assertion_to_ast_ref):
    assertion_to_ast, _ref = assertion_to_ast_ref
    assertion = ass.ExceptionAssertion(module="builtins", exception_type_name="AssertionError")
    assertion.accept(assertion_to_ast)
    assert (
        __create_source_from_ast(assertion_to_ast.nodes)
        == "with pytest.raises(AssertionError):\n    var_0 = 5"
    )


def test_isinstance_assertion(assertion_to_ast_ref):
    assertion_to_ast, ref = assertion_to_ast_ref
    expected_type = ast.Name(id="int", ctx=ast.Load())
    assertion = ass.IsInstanceAssertion(source=ref, expected_type=expected_type)
    assertion.accept(assertion_to_ast)
    assert (
        __create_source_from_ast(assertion_to_ast.nodes)
        == "var_0 = 5\nassert isinstance(var_0, int)"
    )
