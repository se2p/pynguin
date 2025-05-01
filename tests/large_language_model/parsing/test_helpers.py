#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the helpers module."""

import ast

from unittest.mock import MagicMock
from unittest.mock import patch

import pynguin.testcase.testcase as tc

from pynguin.large_language_model.parsing.helpers import has_bound_variables
from pynguin.large_language_model.parsing.helpers import has_call
from pynguin.large_language_model.parsing.helpers import is_expr_or_stmt
from pynguin.large_language_model.parsing.helpers import key_in_dict
from pynguin.large_language_model.parsing.helpers import unparse_test_case


# Copy of the private function for testing purposes
def count_all_statements(node) -> int:
    """Counts statements.

    Counts the number of statements in node and all blocks, not including `node`

    Args:
        node: node to count statements for.

    Returns:
        the number of child statements to node.
    """
    num_non_assert_statements = 0
    for _, value in ast.iter_fields(node):
        # For all blocks
        if isinstance(value, list) and all(isinstance(elem, ast.stmt) for elem in value):
            for elem in value:
                if isinstance(elem, ast.Assert):
                    continue
                num_non_assert_statements += 1
                num_non_assert_statements += count_all_statements(elem)
    return num_non_assert_statements


def test_count_all_statements_with_assert():
    """Test count_all_statements with an assert statement."""
    # Create a node with an assert statement
    node = ast.Module(body=[ast.Assert(test=ast.Constant(value=True), msg=None)], type_ignores=[])

    # Call count_all_statements
    result = count_all_statements(node)

    # Verify the result is 0 (assert statements are skipped)
    assert result == 0


def test_count_all_statements_with_non_assert():
    """Test count_all_statements with a non-assert statement."""
    # Create a node with a non-assert statement
    node = ast.Module(body=[ast.Expr(value=ast.Constant(value=1))], type_ignores=[])

    # Call count_all_statements
    result = count_all_statements(node)

    # Verify the result is 1
    assert result == 1


def test_count_all_statements_with_nested_statements():
    """Test count_all_statements with nested statements."""
    # Create a node with nested statements
    node = ast.Module(
        body=[
            ast.If(
                test=ast.Constant(value=True),
                body=[
                    ast.Expr(value=ast.Constant(value=1)),
                    ast.Assert(test=ast.Constant(value=True), msg=None),
                    ast.Expr(value=ast.Constant(value=2)),
                ],
                orelse=[],
            )
        ],
        type_ignores=[],
    )

    # Call count_all_statements
    result = count_all_statements(node)

    # Verify the result is 3 (1 for the if statement + 2 for the non-assert expressions)
    assert result == 3


def test_key_in_dict_with_boolean_true():
    """Test key_in_dict with a boolean True key."""
    # Create a dictionary with True as a key
    d = {True: "value"}

    # Call key_in_dict with True
    result = key_in_dict(value=True, d=d)

    # Verify the result is True
    assert result is True


def test_key_in_dict_with_boolean_false():
    """Test key_in_dict with a boolean False key."""
    # Create a dictionary with False as a key
    d = {False: "value"}

    # Call key_in_dict with False
    result = key_in_dict(value=False, d=d)

    # Verify the result is True
    assert result is True


def test_key_in_dict_with_non_boolean():
    """Test key_in_dict with a non-boolean key."""
    # Create a dictionary with a non-boolean key
    d = {"key": "value"}

    # Call key_in_dict with "key"
    result = key_in_dict("key", d)

    # Verify the result is True
    assert result is True


def test_key_in_dict_with_missing_key():
    """Test key_in_dict with a missing key."""
    # Create a dictionary
    d = {"key": "value"}

    # Call key_in_dict with a missing key
    result = key_in_dict("missing", d)

    # Verify the result is False
    assert result is False


def test_has_bound_variables_with_bound_variable():
    """Test has_bound_variables with a bound variable."""
    # Create a node with a reference to a bound variable
    node = ast.Name(id="bound_var", ctx=ast.Load())

    # Call has_bound_variables with the node and a set containing the bound variable
    result = has_bound_variables(node, {"bound_var"})

    # Verify the result is True
    assert result is True


def test_has_bound_variables_with_unbound_variable():
    """Test has_bound_variables with an unbound variable."""
    # Create a node with a reference to an unbound variable
    node = ast.Name(id="unbound_var", ctx=ast.Load())

    # Call has_bound_variables with the node and an empty set
    result = has_bound_variables(node, set())

    # Verify the result is False
    assert result is False


def test_has_bound_variables_with_complex_node():
    """Test has_bound_variables with a complex node."""
    # Create a complex node with a reference to a bound variable
    node = ast.BinOp(
        left=ast.Name(id="bound_var", ctx=ast.Load()),
        op=ast.Add(),
        right=ast.Name(id="unbound_var", ctx=ast.Load()),
    )

    # Call has_bound_variables with the node and a set containing the bound variable
    result = has_bound_variables(node, {"bound_var"})

    # Verify the result is True
    assert result is True


def test_has_call_with_call():
    """Test has_call with a node containing a call."""
    # Create a node with a call
    node = ast.Call(func=ast.Name(id="func", ctx=ast.Load()), args=[], keywords=[])

    # Call has_call with the node
    result = has_call(node)

    # Verify the result is True
    assert result is True


def test_has_call_with_nested_call():
    """Test has_call with a node containing a nested call."""
    # Create a node with a nested call
    node = ast.BinOp(
        left=ast.Name(id="var", ctx=ast.Load()),
        op=ast.Add(),
        right=ast.Call(func=ast.Name(id="func", ctx=ast.Load()), args=[], keywords=[]),
    )

    # Call has_call with the node
    result = has_call(node)

    # Verify the result is True
    assert result is True


def test_has_call_without_call():
    """Test has_call with a node not containing a call."""
    # Create a node without a call
    node = ast.BinOp(
        left=ast.Name(id="var1", ctx=ast.Load()),
        op=ast.Add(),
        right=ast.Name(id="var2", ctx=ast.Load()),
    )

    # Call has_call with the node
    result = has_call(node)

    # Verify the result is False
    assert result is False


def test_is_expr_or_stmt_with_expr():
    """Test is_expr_or_stmt with an expression."""
    # Create an expression node
    node = ast.Name(id="var", ctx=ast.Load())

    # Call is_expr_or_stmt with the node
    result = is_expr_or_stmt(node)

    # Verify the result is True
    assert result is True


def test_is_expr_or_stmt_with_stmt():
    """Test is_expr_or_stmt with a statement."""
    # Create a statement node
    node = ast.Expr(value=ast.Constant(value=1))

    # Call is_expr_or_stmt with the node
    result = is_expr_or_stmt(node)

    # Verify the result is True
    assert result is True


def test_is_expr_or_stmt_with_non_expr_or_stmt():
    """Test is_expr_or_stmt with a non-expression and non-statement."""
    # Create a non-expression and non-statement node
    node = ast.Load()

    # Call is_expr_or_stmt with the node
    result = is_expr_or_stmt(node)

    # Verify the result is False
    assert result is False


def test_unparse_test_case_success():
    """Test unparse_test_case with a valid test case."""
    # Create a mock test case
    test_case = MagicMock(spec=tc.TestCase)

    # Mock the TestCaseToAstVisitor
    mock_visitor = MagicMock()
    mock_visitor.test_case_ast = [ast.Expr(value=ast.Constant(value=1))]

    # Patch the TestCaseToAstVisitor constructor
    with patch("pynguin.testcase.testcase_to_ast.TestCaseToAstVisitor", return_value=mock_visitor):
        # Call unparse_test_case
        result = unparse_test_case(test_case)

        # Verify the result is a string
        assert isinstance(result, str)
        assert "test_generated_function" in result


def test_unparse_test_case_invalid_module():
    """Test unparse_test_case with an invalid module."""
    # Create a mock test case
    test_case = MagicMock(spec=tc.TestCase)

    # Mock the TestCaseToAstVisitor
    mock_visitor = MagicMock()
    mock_visitor.test_case_ast = [ast.Expr(value=ast.Constant(value=1))]

    # Patch the TestCaseToAstVisitor constructor and ast.Module
    with (
        patch("pynguin.testcase.testcase_to_ast.TestCaseToAstVisitor", return_value=mock_visitor),
        patch("ast.Module", return_value="not_a_module"),
    ):
        # Call unparse_test_case and expect it to return None
        result = unparse_test_case(test_case)
        assert result is None


def test_unparse_test_case_invalid_module_type():
    """Test unparse_test_case with an invalid module type."""
    # Create a mock test case
    test_case = MagicMock(spec=tc.TestCase)

    # Mock the TestCaseToAstVisitor
    mock_visitor = MagicMock()
    mock_visitor.test_case_ast = [ast.Expr(value=ast.Constant(value=1))]

    # Create a custom module class that will fail the isinstance check
    class FakeModule:
        pass

    # Patch the TestCaseToAstVisitor constructor and other dependencies
    with (
        patch("pynguin.testcase.testcase_to_ast.TestCaseToAstVisitor", return_value=mock_visitor),
        patch("ast.Module", return_value=FakeModule()),
        patch("ast.fix_missing_locations"),
        patch("pynguin.large_language_model.parsing.helpers.logger.error") as mock_logger,
    ):
        # Call unparse_test_case
        result = unparse_test_case(test_case)

        # Verify the result is None
        assert result is None

        # Verify the logger was called with an error message
        mock_logger.assert_called_once()


def test_unparse_test_case_exception():
    """Test unparse_test_case with an exception."""
    # Create a mock test case
    test_case = MagicMock(spec=tc.TestCase)

    # Create a mock visitor that raises an exception when accept is called
    test_case.accept.side_effect = Exception("Test exception")

    # Call unparse_test_case
    result = unparse_test_case(test_case)

    # Verify the result is None
    assert result is None
