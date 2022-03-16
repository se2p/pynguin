#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""The implementation of this module contains some code adopted from the ``darglint``
library (https://github.com/terrencepreilly/darglint), which was released by Terrence
Reilly under MIT license."""
import ast
import importlib
import inspect
from typing import Iterable

import pytest

from pynguin.analyses.module_bak.syntaxtree import (
    FunctionAnalysisVisitor,
    FunctionAndMethodVisitor,
    get_all_classes,
    get_all_functions,
    get_all_methods,
    get_docstring,
    get_function_descriptions,
    get_line_number_for_function,
    get_return_type,
    has_decorator,
)


@pytest.fixture(scope="module")
def comments_tree() -> ast.AST:
    module = importlib.import_module("tests.fixtures.cluster.comments")
    tree = ast.parse(
        inspect.getsource(module),
        filename="comments.py",
        type_comments=True,
        feature_version=(3, 8),
    )
    return tree


@pytest.fixture(scope="function")
def function_analysis() -> FunctionAnalysisVisitor:
    return FunctionAnalysisVisitor()


def __get_names_from_function_definitions(
    definitions: Iterable[ast.FunctionDef | ast.AsyncFunctionDef],
) -> set[str]:
    return {func.name for func in definitions}


def __parse_ast(code: str) -> ast.Module:
    tree = ast.parse(
        code, filename="dummy.py", type_comments=True, feature_version=(3, 8)
    )
    return tree


def test__get_all_functions(comments_tree):
    functions = {func.name for func in get_all_functions(comments_tree)}
    expected = {
        "public_function",
        "public_method",
        "__init__",
        "__private_method",
        "_protected_method",
        "asynchronous_method",
        "__twice",
        "b",
    }
    assert functions == expected


def test__get_all_classes(comments_tree):
    classes = {class_.name for class_ in get_all_classes(comments_tree)}
    expected = {"AClass"}
    assert classes == expected


def test__get_all_methods(comments_tree):
    methods = {method.name for method in get_all_methods(comments_tree)}
    expected = {
        "__init__",
        "__private_method",
        "_protected_method",
        "public_method",
        "asynchronous_method",
        "__twice",
        "b",
    }
    assert methods == expected


def test__get_docstring(comments_tree):
    functions = {func.name: func for func in get_all_functions(comments_tree)}
    docstring = get_docstring(functions["public_function"])
    expected = """A public function

Args:
    a: Argument description

Returns:
    Return description"""
    assert docstring == expected


def test__get_return_type():
    func = ast.FunctionDef(name="foo", returns=None)
    async_func = ast.AsyncFunctionDef(name="bar", returns=ast.Name(id="str"))
    assert get_return_type(func) is None
    assert get_return_type(async_func) == "str"


def test__get_line_number_for_function(comments_tree):
    functions = {func.name: func for func in get_all_functions(comments_tree)}
    assert get_line_number_for_function(functions["public_function"]) == 14
    assert get_line_number_for_function(ast.FunctionDef(lineno=42)) == 42


@pytest.mark.parametrize(
    "decorators, expected",
    [
        pytest.param("property", False),
        pytest.param(["property", "contextmanager"], True),
    ],
)
def test__has_decorator(comments_tree, decorators, expected):
    functions = {func.name: func for func in get_all_functions(comments_tree)}
    assert has_decorator(functions["public_function"], decorators) == expected


def test_function_and_method_visitor(comments_tree):
    visitor = FunctionAndMethodVisitor()
    visitor.visit(comments_tree)
    assert __get_names_from_function_definitions(visitor.properties) == {"b"}
    methods = {
        "__init__",
        "public_method",
        "_protected_method",
        "__private_method",
        "asynchronous_method",
        "__twice",
    }
    assert __get_names_from_function_definitions(visitor.methods) == methods
    assert __get_names_from_function_definitions(visitor.functions) == {
        "public_function"
    }


def test_get_function_descriptions(comments_tree):
    descriptions = get_function_descriptions(comments_tree)
    names = {desc.name for desc in descriptions}
    assert names == {
        "public_function",
        "__init__",
        "public_method",
        "b",
        "asynchronous_method",
        "_protected_method",
        "__private_method",
        "__twice",
    }


def __assert_found(program: str, *exceptions):
    func = ast.parse(program).body[0]
    visitor = FunctionAnalysisVisitor()
    visitor.visit(func)
    for exception in exceptions:
        assert exception in visitor.exceptions


def __assert_none_found(program: str):
    func = ast.parse(program).body[0]
    visitor = FunctionAnalysisVisitor()
    visitor.visit(func)
    assert visitor.exceptions == set()


def test_identifies_one_exception():
    program = """def f():
    raise Exception("Something")
"""
    __assert_found(program, "Exception")


def test_ignores_caught_exception():
    program = """def f():
    try:
        raise Exception("Something")
    except Exception as e:
        pass
"""
    __assert_none_found(program)


def test_ignores_caught_exception_unnamed():
    program = """def f():
    try:
        raise Exception("Something")
    except:
        pass
"""
    __assert_none_found(program)


def test_identifies_exception_in_catch():
    program = """def f():
    try:
        something_dangerous()
    except:
        raise Exception("Something")
"""
    __assert_found(program, "Exception")


def test_identifies_uncaught_in_try():
    program = """def f():
    try:
        raise SyntaxError("Problematic")
    except IOException:
        print("Not gonna happen.")
"""
    __assert_found(program, "SyntaxError")


def test_caught_in_outer_try():
    program = """def f():
    try:
        try:
            raise SyntaxError("Here!")
        except IOException:
            pass
    except SyntaxError as e:
        pass
"""
    __assert_none_found(program)


def test_uncaught_in_nested_try():
    program = """def f():
    try:
        try:
            raise InterruptedException()
        except MathError:
            pass
    except IOError:
        pass
"""
    __assert_found(program, "InterruptedException")


def test_caught_in_inner_catch():
    program = """def f():
    try:
        try:
            raise SyntaxError(">")
        except:
            pass
    except IOError:
        pass
"""
    __assert_none_found(program)


def test_caught_multiple_exceptions():
    program = """def f(x):
    try:
        y = int(x)
        return 2 / y
    except (ValueError, ZeroDivisionError) as e:
        pass
"""
    __assert_none_found(program)


def test_reraise_on_of_multiple_exceptions():
    program = """def f(x):
    try:
        y = int(x)
        return 2 / y
    except (ValueError, ZeroDivisionError) as e:
        raise e
"""
    __assert_found(program, "ValueError", "ZeroDivisionError")


def test_bare_reraise_with_as():
    program = """def f(x):
    try:
        return 1 / x
    except ZeroDivisionError as e:
        raise
"""
    __assert_found(program, "ZeroDivisionError")


def test_bare_reraise_single_exception():
    program = """def f(x):
    try:
        return 1 / x
    except ZeroDivisionError:
        raise
"""
    __assert_found(program, "ZeroDivisionError")


def test_bare_reraise_one_of_multiple_exceptions():
    program = """def f(x):
    try:
        y = int(x)
        return 2 / y
    except (ValueError, ZeroDivisionError):
        raise
"""
    __assert_found(program, "ValueError", "ZeroDivisionError")


def test_capture_tuple():
    program = """def f(x):
    try:
        risky()
    except (a.AError, b.BError):
        raise
"""
    __assert_found(program, "a.AError", "b.BError")


def test_bare_reraise_in_multiple_handlers():
    program = """def f(x):
    try:
        risky.attempt(x)
    except risky.Failed:
        raise
    except Exception:
        logger.log("Something else went wrong!")
"""
    __assert_found(program, "risky.Failed")


def test_reraise_any_exception_in_bare_handler():
    program = """def f(x):
    try:
        if x == "Racoon":
            raise Rabies()
        elif x == "Bird":
            raise H1N1()
    except:
        raise
"""
    __assert_found(program, "Rabies", "H1N1")


def test_reraise_any_exception_in_bare_handler_2():
    program = """def f(x):
    try:
        if x == "Racoon":
            raise Rabies()
        elif x == "Bird":
            raise H1N1()
    except Rabies:
        raise
    except H1N1:
        raise Unexpected()
"""
    __assert_found(program, "Rabies", "Unexpected")


def test_visits_finally_block():
    program = """def f():
    try:
        dangerous_operation()
    finally:
        raise AnException()
"""
    __assert_found(program, "AnException")


def test_visits_or_else_block():
    program = """def f():
    try:
        pass
    except Exception:
        pass
    else:
        raise MyException()
"""
    __assert_found(program, "MyException")


def test_detect_static_method():
    program = """class A:
    @staticmethod
    def f(x: int) -> int:
        return 2 * x
"""
    tree = __parse_ast(program)
    descriptions = get_function_descriptions(tree)
    assert len(descriptions) == 1
    assert descriptions[0].is_static


def test_detect_non_static_method():
    program = """class A:
    def f(self, x: int) -> int:
        self.y = 2 * x
"""
    tree = __parse_ast(program)
    descriptions = get_function_descriptions(tree)
    assert len(descriptions) == 1
    assert not descriptions[0].is_static


def test_detect_abstract_method_pass(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        pass
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.is_abstract


def test_detect_abstract_method_ellipsis(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        ...
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.is_abstract


def test_detect_abstract_method_NotImplementedError(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        raise NotImplementedError()
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.is_abstract


def test_detect_abstract_method_NotImplemented(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        return NotImplemented
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.is_abstract


def test_detect_abstract_method_docstring(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        '''description'''
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.is_abstract


def test_detect_abstract_method_with_implementation(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        x = foo()
        y = bar()
        return x + y
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert not function_analysis.is_abstract


def test_detect_abstract_method_with_two_statements(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        x = foo()
        return 2 + x
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert not function_analysis.is_abstract


def test_detect_abstract_method_with_docstring_and_statement(function_analysis):
    program = """class A:
    @abstractmethod
    def f():
        '''documentation'''
        pass
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.is_abstract


def test_visit_nested_async_functions(function_analysis):
    program = """async def foo():
    async def bar():
        pass

    return bar
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.in_function


def test_visit_nested_functions(function_analysis):
    program = """def foo():
    def bar():
        pass

    return bar
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.in_function


def test_visit_nested_lambdas(function_analysis):
    program = "lambda a = 2, b = 3: lambda c: a+b+c"
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.in_function


def test_yield_from(function_analysis):
    program = """def f(g):
    yield from g
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert len(function_analysis.yields) == 1
    assert isinstance(function_analysis.yields[0], ast.YieldFrom)
    assert function_analysis.yields[0].value.id == "g"


def test_visit_complex_function_definition(function_analysis):
    program = """def f(
    pos_1,
    pos_2,
    /,
    normal_1,
    normal_2,
    *,
    kw_1,
    kw_2,
):
    pass
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.arguments == [
        "pos_1",
        "pos_2",
        "normal_1",
        "normal_2",
        "kw_1",
        "kw_2",
    ]


def test_visit_function_args_kwargs(function_analysis):
    program = """def f(*args, **kwargs):
    pass
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert function_analysis.arguments == ["*args", "**kwargs"]


def test_visit_assert(function_analysis):
    program = """def f():
    assert True
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert len(function_analysis.asserts) == 1
