#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Analyses for the syntax tree.

The implementation of this module contains some code adopted from the ``darglint``
library (https://github.com/terrencepreilly/darglint), which was released by Terrence
Reilly under MIT license.
"""

import ast
import importlib
import inspect

import astroid
import pytest

from pynguin.analyses.syntaxtree import FunctionAnalysisVisitor
from pynguin.analyses.syntaxtree import astroid_to_ast
from pynguin.analyses.syntaxtree import get_class_node_from_ast
from pynguin.analyses.syntaxtree import get_function_description
from pynguin.analyses.syntaxtree import get_function_node_from_ast
from pynguin.analyses.syntaxtree import has_decorator


@pytest.fixture(scope="module")
def comments_tree() -> astroid.Module:
    module = importlib.import_module("tests.fixtures.cluster.comments")
    return astroid.parse(inspect.getsource(module), path="comments.py")


@pytest.fixture
def function_analysis() -> FunctionAnalysisVisitor:
    return FunctionAnalysisVisitor()


def __parse_ast(code: str) -> ast.Module:
    return ast.parse(code, filename="dummy.py", type_comments=True, feature_version=(3, 8))


@pytest.mark.parametrize(
    "decorators, expected",
    [
        pytest.param("property", False),
        pytest.param(["property", "contextmanager"], True),
    ],
)
def test__has_decorator(comments_tree, decorators, expected):
    public_function = get_function_node_from_ast(comments_tree, "public_function")
    assert has_decorator(astroid_to_ast(public_function), decorators) == expected


@pytest.mark.parametrize(
    "function",
    [
        "public_function",
    ],
)
def test_get_function_description(comments_tree, function):
    descriptions = get_function_description(get_function_node_from_ast(comments_tree, function))
    assert descriptions.name == function


@pytest.mark.parametrize(
    "function",
    [
        "__init__",
        "public_method",
        "b",
        "asynchronous_method",
        "_protected_method",
        "__private_method",
        "__twice",
    ],
)
def test_get_method_description(comments_tree, function):
    descriptions = get_function_description(
        get_function_node_from_ast(get_class_node_from_ast(comments_tree, "AClass"), function)
    )
    assert descriptions.name == function


def test_get_function_description_nested():
    module = astroid.parse(
        """
def foo():
    def bar():
        return False
    yield 5"""
    )
    description = get_function_description(get_function_node_from_ast(module, "foo"))
    assert description.has_return is False
    assert description.has_yield is True


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


def test_visit_assert(function_analysis):
    program = """def f():
    assert True
"""
    tree = __parse_ast(program)
    function_analysis.visit(tree.body[0])
    assert len(function_analysis.asserts) == 1
    assert function_analysis.exceptions.pop() == "AssertionError"
