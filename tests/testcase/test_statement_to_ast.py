#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from ast import Module
from typing import Dict, List, Set, Tuple
from unittest.mock import MagicMock

import astor
import pytest

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.statements.collectionsstatements as coll_stmt
import pynguin.testcase.statements.fieldstatement as field_stmt
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.variable.variablereference as vr
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.namingscope import NamingScope


@pytest.fixture()
def statement_to_ast_visitor() -> stmt_to_ast.StatementToAstVisitor:
    var_names = NamingScope()
    module_aliases = NamingScope(prefix="module")
    return stmt_to_ast.StatementToAstVisitor(module_aliases, var_names)


def test_statement_to_ast_int(statement_to_ast_visitor):
    int_stmt = MagicMock(stmt.Statement)
    int_stmt.value = 5
    statement_to_ast_visitor.visit_int_primitive_statement(int_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes)) == "var0 = 5\n"
    )


def test_statement_to_ast_float(statement_to_ast_visitor):
    float_stmt = MagicMock(stmt.Statement)
    float_stmt.value = 5.5
    statement_to_ast_visitor.visit_float_primitive_statement(float_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = 5.5\n"
    )


def test_statement_to_ast_str(statement_to_ast_visitor):
    str_stmt = MagicMock(stmt.Statement)
    str_stmt.value = "TestMe"
    statement_to_ast_visitor.visit_string_primitive_statement(str_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = 'TestMe'\n"
    )


def test_statement_to_ast_bytes(statement_to_ast_visitor):
    str_stmt = MagicMock(stmt.Statement)
    str_stmt.value = b"TestMe"
    statement_to_ast_visitor.visit_bytes_primitive_statement(str_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = b'TestMe'\n"
    )


def test_statement_to_ast_bool(statement_to_ast_visitor):
    bool_stmt = MagicMock(stmt.Statement)
    bool_stmt.value = True
    statement_to_ast_visitor.visit_boolean_primitive_statement(bool_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = True\n"
    )


def test_statement_to_ast_none(statement_to_ast_visitor):
    none_stmt = MagicMock(stmt.Statement)
    none_stmt.value = None
    statement_to_ast_visitor.visit_none_statement(none_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = None\n"
    )


def test_statement_to_ast_enum(statement_to_ast_visitor):
    enum_stmt = MagicMock()
    enum_stmt.accessible_object.return_value = MagicMock(
        owner=MagicMock(__name__="Foo")
    )
    enum_stmt.value_name = "BAR"
    statement_to_ast_visitor.visit_enum_statement(enum_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.Foo.BAR\n"
    )


def test_statement_to_ast_assignment(variable_reference_mock, statement_to_ast_visitor):
    assign_stmt = MagicMock(stmt.Statement)
    assign_stmt.ret_val = variable_reference_mock
    assign_stmt.rhs = variable_reference_mock
    statement_to_ast_visitor.visit_assignment_statement(assign_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var0\n"
    )


def test_statement_to_ast_field(
    statement_to_ast_visitor, test_case_mock, field_mock, variable_reference_mock
):
    f_stmt = field_stmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    statement_to_ast_visitor.visit_field_statement(f_stmt)


def all_param_types_signature():
    return InferredSignature(
        signature=inspect.Signature(
            parameters=[
                inspect.Parameter(
                    name="a",
                    kind=inspect.Parameter.POSITIONAL_ONLY,
                    annotation=float,
                ),
                inspect.Parameter(
                    name="b",
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=float,
                ),
                inspect.Parameter(
                    name="c",
                    kind=inspect.Parameter.VAR_POSITIONAL,
                    annotation=float,
                ),
                inspect.Parameter(
                    name="d",
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    annotation=float,
                ),
                inspect.Parameter(
                    name="e",
                    kind=inspect.Parameter.VAR_KEYWORD,
                    annotation=float,
                ),
            ]
        ),
        return_type=float,
        parameters={"a": float, "b": float, "c": float, "d": float, "e": float},
    )


@pytest.fixture()
def all_types_constructor():
    return GenericConstructor(
        owner=MagicMock(__name__="Constructor"),
        inferred_signature=all_param_types_signature(),
    )


@pytest.fixture()
def all_types_method():
    return GenericMethod(
        owner=MagicMock(),
        inferred_signature=all_param_types_signature(),
        method=MagicMock(__name__="method"),
    )


@pytest.fixture()
def all_types_function():
    return GenericFunction(
        function=MagicMock(__name__="function"),
        inferred_signature=all_param_types_signature(),
    )


@pytest.mark.parametrize(
    "args,expected",
    [
        ({}, "var0 = module0.Constructor()\n"),
        ({"a": MagicMock()}, "var0 = module0.Constructor(var1)\n"),
        ({"b": MagicMock()}, "var0 = module0.Constructor(var1)\n"),
        ({"c": MagicMock()}, "var0 = module0.Constructor(*var1)\n"),
        ({"d": MagicMock()}, "var0 = module0.Constructor(d=var1)\n"),
        ({"e": MagicMock()}, "var0 = module0.Constructor(**var1)\n"),
        (
            {
                "a": MagicMock(),
                "b": MagicMock(),
                "c": MagicMock(),
                "d": MagicMock(),
                "e": MagicMock(),
            },
            "var0 = module0.Constructor(var1, var2, *var3, d=var4, **var5)\n",
        ),
    ],
)
def test_statement_to_ast_constructor_args(
    statement_to_ast_visitor, test_case_mock, all_types_constructor, args, expected
):
    constr_stmt = param_stmt.ConstructorStatement(
        test_case_mock, all_types_constructor, args
    )
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes)) == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ({}, "var1 = var0.method()\n"),
        ({"a": MagicMock()}, "var2 = var0.method(var1)\n"),
        ({"b": MagicMock()}, "var2 = var0.method(var1)\n"),
        ({"c": MagicMock()}, "var2 = var0.method(*var1)\n"),
        ({"d": MagicMock()}, "var2 = var0.method(d=var1)\n"),
        ({"e": MagicMock()}, "var2 = var0.method(**var1)\n"),
        (
            {
                "a": MagicMock(),
                "b": MagicMock(),
                "c": MagicMock(),
                "d": MagicMock(),
                "e": MagicMock(),
            },
            "var6 = var0.method(var1, var2, *var3, d=var4, **var5)\n",
        ),
    ],
)
def test_statement_to_ast_method_args(
    statement_to_ast_visitor, test_case_mock, all_types_method, args, expected
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock, all_types_method, MagicMock(), args
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes)) == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ({}, "var0 = module0.function()\n"),
        ({"a": MagicMock()}, "var1 = module0.function(var0)\n"),
        ({"b": MagicMock()}, "var1 = module0.function(var0)\n"),
        ({"c": MagicMock()}, "var1 = module0.function(*var0)\n"),
        ({"d": MagicMock()}, "var1 = module0.function(d=var0)\n"),
        ({"e": MagicMock()}, "var1 = module0.function(**var0)\n"),
        (
            {
                "a": MagicMock(),
                "b": MagicMock(),
                "c": MagicMock(),
                "d": MagicMock(),
                "e": MagicMock(),
            },
            "var5 = module0.function(var0, var1, *var2, d=var3, **var4)\n",
        ),
    ],
)
def test_statement_to_ast_function_args(
    statement_to_ast_visitor, test_case_mock, all_types_function, args, expected
):
    func_stmt = param_stmt.FunctionStatement(test_case_mock, all_types_function, args)
    statement_to_ast_visitor.visit_function_statement(func_stmt)
    assert astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes)) == expected


def test_statement_to_ast_with_wrap():
    var_names = NamingScope()
    module_aliases = NamingScope(prefix="module")
    statement_to_ast_visitor = stmt_to_ast.StatementToAstVisitor(
        module_aliases, var_names, True
    )
    int_stmt = MagicMock(stmt.Statement)
    int_stmt.value = 5
    statement_to_ast_visitor.visit_int_primitive_statement(int_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "try:\n    var0 = 5\nexcept BaseException:\n    pass\n"
    )


def test_statement_to_ast_list_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    list_stmt = coll_stmt.ListStatement(
        test_case_mock,
        List[int],
        [MagicMock(vr.VariableReference)],
    )
    statement_to_ast_visitor.visit_list_statement(list_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = [var1]\n"
    )


def test_statement_to_ast_list_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    list_stmt = coll_stmt.ListStatement(
        test_case_mock,
        List[int],
        [],
    )
    statement_to_ast_visitor.visit_list_statement(list_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = []\n"
    )


def test_statement_to_ast_set_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    set_stmt = coll_stmt.SetStatement(
        test_case_mock,
        Set[int],
        {MagicMock(vr.VariableReference)},
    )
    statement_to_ast_visitor.visit_set_statement(set_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var1 = {var0}\n"
    )


def test_statement_to_ast_set_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    set_stmt = coll_stmt.SetStatement(
        test_case_mock,
        Set[int],
        set(),
    )
    statement_to_ast_visitor.visit_set_statement(set_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = set()\n"
    )


def test_statement_to_ast_tuple_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    tuple_stmt = coll_stmt.TupleStatement(
        test_case_mock,
        Tuple[int],
        [MagicMock(vr.VariableReference)],
    )
    statement_to_ast_visitor.visit_tuple_statement(tuple_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1,\n"
    )


def test_statement_to_ast_tuple_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    tuple_stmt = coll_stmt.TupleStatement(
        test_case_mock,
        Tuple,
        [],
    )
    statement_to_ast_visitor.visit_tuple_statement(tuple_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = ()\n"
    )


def test_statement_to_ast_dict_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    dict_stmt = coll_stmt.DictStatement(
        test_case_mock,
        Dict[int, int],
        [(MagicMock(vr.VariableReference), MagicMock(vr.VariableReference))],
    )
    statement_to_ast_visitor.visit_dict_statement(dict_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = {var1: var2}\n"
    )


def test_statement_to_ast_dict_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    dict_stmt = coll_stmt.DictStatement(
        test_case_mock,
        Tuple,
        [],
    )
    statement_to_ast_visitor.visit_dict_statement(dict_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = {}\n"
    )
