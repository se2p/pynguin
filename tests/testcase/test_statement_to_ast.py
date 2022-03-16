#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
import inspect
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statement as stmt
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
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


def __create_source_from_ast(module_body: list[ast.stmt]) -> str:
    return ast.unparse(
        ast.fix_missing_locations(ast.Module(body=module_body, type_ignores=[]))
    )


def test_statement_to_ast_int(statement_to_ast_visitor, test_case_mock):
    int_stmt = stmt.IntPrimitiveStatement(test_case_mock, 5)
    statement_to_ast_visitor.visit_int_primitive_statement(int_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = 5"


def test_statement_to_ast_float(statement_to_ast_visitor, test_case_mock):
    float_stmt = stmt.FloatPrimitiveStatement(test_case_mock, 5.5)
    statement_to_ast_visitor.visit_float_primitive_statement(float_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = 5.5"


def test_statement_to_ast_str(statement_to_ast_visitor, test_case_mock):
    str_stmt = stmt.StringPrimitiveStatement(test_case_mock, "TestMe")
    statement_to_ast_visitor.visit_string_primitive_statement(str_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = 'TestMe'"
    )


def test_statement_to_ast_bytes(statement_to_ast_visitor, test_case_mock):
    bytes_stmt = stmt.BytesPrimitiveStatement(test_case_mock, b"TestMe")
    statement_to_ast_visitor.visit_bytes_primitive_statement(bytes_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = b'TestMe'"
    )


def test_statement_to_ast_bool(statement_to_ast_visitor, test_case_mock):
    bool_stmt = stmt.BooleanPrimitiveStatement(test_case_mock, True)
    statement_to_ast_visitor.visit_boolean_primitive_statement(bool_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = True"
    )


def test_statement_to_ast_none(statement_to_ast_visitor, test_case_mock):
    none_stmt = stmt.NoneStatement(test_case_mock, int)
    statement_to_ast_visitor.visit_none_statement(none_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = None"
    )


def test_statement_to_ast_enum(statement_to_ast_visitor, test_case_mock):
    enum_stmt = stmt.EnumPrimitiveStatement(
        test_case_mock, MagicMock(owner=MagicMock(__name__="Foo"), names=["BAR"]), 0
    )
    statement_to_ast_visitor.visit_enum_statement(enum_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = module_0.Foo.BAR"
    )


def test_statement_to_ast_assignment(
    variable_reference_mock, statement_to_ast_visitor, test_case_mock
):
    string = stmt.StringPrimitiveStatement(test_case_mock, "foo")
    field = gao.GenericField(str, "foo", None)
    int_0 = stmt.IntPrimitiveStatement(test_case_mock, 42)
    assign_stmt = stmt.AssignmentStatement(
        test_case_mock, vr.FieldReference(string.ret_val, field), int_0.ret_val
    )
    statement_to_ast_visitor.visit_assignment_statement(assign_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0.foo = var_1"
    )


def test_statement_to_ast_field(statement_to_ast_visitor, test_case_mock):
    string = stmt.StringPrimitiveStatement(test_case_mock, "foo")
    field = gao.GenericField(str, "foo", None)
    field_stmt = stmt.FieldStatement(test_case_mock, field, string.ret_val)
    statement_to_ast_visitor.visit_field_statement(field_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = var_1.foo"
    )


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
        ({}, "var_0 = module_0.Constructor()"),
        (
            {"a": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_0 = module_0.Constructor(var_1)",
        ),
        (
            {"b": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_0 = module_0.Constructor(var_1)",
        ),
        (
            {"c": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_0 = module_0.Constructor(*var_1)",
        ),
        (
            {"d": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_0 = module_0.Constructor(d=var_1)",
        ),
        (
            {"e": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_0 = module_0.Constructor(**var_1)",
        ),
        (
            {
                "a": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "b": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "c": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "d": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "e": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
            },
            "var_0 = module_0.Constructor(var_1, var_2, *var_3, d=var_4, **var_5)",
        ),
    ],
)
def test_statement_to_ast_constructor_args(
    statement_to_ast_visitor, test_case_mock, all_types_constructor, args, expected
):
    constr_stmt = stmt.ConstructorStatement(test_case_mock, all_types_constructor, args)
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ({}, "var_1 = var_0.method()"),
        (
            {"a": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_2 = var_0.method(var_1)",
        ),
        (
            {"b": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_2 = var_0.method(var_1)",
        ),
        (
            {"c": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_2 = var_0.method(*var_1)",
        ),
        (
            {"d": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_2 = var_0.method(d=var_1)",
        ),
        (
            {"e": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_2 = var_0.method(**var_1)",
        ),
        (
            {
                "a": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "b": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "c": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "d": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "e": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
            },
            "var_6 = var_0.method(var_1, var_2, *var_3, d=var_4, **var_5)",
        ),
    ],
)
def test_statement_to_ast_method_args(
    statement_to_ast_visitor, test_case_mock, all_types_method, args, expected
):
    method_stmt = stmt.MethodStatement(
        test_case_mock,
        all_types_method,
        stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
        args,
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ({}, "var_0 = module_0.function()"),
        (
            {"a": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_1 = module_0.function(var_0)",
        ),
        (
            {"b": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_1 = module_0.function(var_0)",
        ),
        (
            {"c": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_1 = module_0.function(*var_0)",
        ),
        (
            {"d": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_1 = module_0.function(d=var_0)",
        ),
        (
            {"e": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val},
            "var_1 = module_0.function(**var_0)",
        ),
        (
            {
                "a": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "b": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "c": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "d": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
                "e": stmt.IntPrimitiveStatement(MagicMock(), 3).ret_val,
            },
            "var_5 = module_0.function(var_0, var_1, *var_2, d=var_3, **var_4)",
        ),
    ],
)
def test_statement_to_ast_function_args(
    statement_to_ast_visitor, test_case_mock, all_types_function, args, expected
):
    func_stmt = stmt.FunctionStatement(test_case_mock, all_types_function, args)
    statement_to_ast_visitor.visit_function_statement(func_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == expected


def test_statement_to_ast_with_wrap(test_case_mock):
    var_names = NamingScope()
    module_aliases = NamingScope(prefix="module")
    statement_to_ast_visitor = stmt_to_ast.StatementToAstVisitor(
        module_aliases, var_names, True
    )
    int_stmt = stmt.IntPrimitiveStatement(test_case_mock, 5)
    statement_to_ast_visitor.visit_int_primitive_statement(int_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "try:\n    var_0 = 5\nexcept BaseException:\n    pass"
    )


def test_statement_to_ast_list_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    list_stmt = stmt.ListStatement(
        test_case_mock,
        list[int],
        [stmt.IntPrimitiveStatement(test_case_mock, 5).ret_val],
    )
    statement_to_ast_visitor.visit_list_statement(list_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = [var_1]"
    )


def test_statement_to_ast_list_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    list_stmt = stmt.ListStatement(
        test_case_mock,
        list[int],
        [],
    )
    statement_to_ast_visitor.visit_list_statement(list_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = []"


def test_statement_to_ast_set_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    set_stmt = stmt.SetStatement(
        test_case_mock,
        set[int],
        [stmt.IntPrimitiveStatement(test_case_mock, 5).ret_val],
    )
    statement_to_ast_visitor.visit_set_statement(set_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_1 = {var_0}"
    )


def test_statement_to_ast_set_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    set_stmt = stmt.SetStatement(test_case_mock, set[int], [])
    statement_to_ast_visitor.visit_set_statement(set_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = set()"
    )


def test_statement_to_ast_tuple_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    tuple_stmt = stmt.TupleStatement(
        test_case_mock,
        tuple[int],
        [stmt.IntPrimitiveStatement(test_case_mock, 5).ret_val],
    )
    statement_to_ast_visitor.visit_tuple_statement(tuple_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = (var_1,)"
    )


def test_statement_to_ast_tuple_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    tuple_stmt = stmt.TupleStatement(
        test_case_mock,
        tuple,
        [],
    )
    statement_to_ast_visitor.visit_tuple_statement(tuple_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = ()"


def test_statement_to_ast_dict_single(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    dict_stmt = stmt.DictStatement(
        test_case_mock,
        dict[int, int],
        [
            (
                stmt.IntPrimitiveStatement(test_case_mock, 5).ret_val,
                stmt.IntPrimitiveStatement(test_case_mock, 5).ret_val,
            )
        ],
    )
    statement_to_ast_visitor.visit_dict_statement(dict_stmt)
    assert (
        __create_source_from_ast(statement_to_ast_visitor.ast_nodes)
        == "var_0 = {var_1: var_2}"
    )


def test_statement_to_ast_dict_empty(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    dict_stmt = stmt.DictStatement(
        test_case_mock,
        tuple,
        [],
    )
    statement_to_ast_visitor.visit_dict_statement(dict_stmt)
    assert __create_source_from_ast(statement_to_ast_visitor.ast_nodes) == "var_0 = {}"
