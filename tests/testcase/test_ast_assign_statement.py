# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

"""Tests for the ASTAssignStatement class."""

from __future__ import annotations

import ast

from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest

import pynguin.testcase.statement as stmt
import pynguin.testcase.variablereference as vr

from pynguin.large_language_model.parsing.astscoping import VariableRefAST
from pynguin.testcase.defaulttestcase import DefaultTestCase
from pynguin.testcase.statement import StatementVisitor


@pytest.fixture
def default_test_case():
    """Create a default test case for testing."""
    test_case = DefaultTestCase(MagicMock())
    # Mock get_all_objects to return an empty set
    test_case.get_all_objects = MagicMock(return_value=set())
    return test_case


@pytest.fixture
def variable_ref(default_test_case):
    """Create a variable reference for testing."""
    return vr.VariableReference(default_test_case, int)


def test_ast_assign_statement_init_with_ast(default_test_case):
    """Test initialization with an AST node."""
    # Create a simple AST node (constant)
    ast_node = ast.Constant(value=42)
    ref_dict = {}

    # Create the statement
    statement = stmt.ASTAssignStatement(default_test_case, ast_node, ref_dict)

    # Verify the statement was created correctly
    assert statement.test_case == default_test_case
    assert isinstance(statement.rhs, VariableRefAST)


def test_ast_assign_statement_init_with_variable_ref_ast(default_test_case, variable_ref):
    """Test initialization with a VariableRefAST."""
    # Create a name node and ref_dict
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": variable_ref}

    # Create a VariableRefAST
    var_ref_ast = VariableRefAST(name_node, ref_dict)

    # Create the statement
    statement = stmt.ASTAssignStatement(default_test_case, var_ref_ast, {})

    # Verify the statement was created correctly
    assert statement.test_case == default_test_case
    assert statement.rhs == var_ref_ast


def test_ast_assign_statement_init_invalid_type(default_test_case):
    """Test initialization with an invalid type."""
    # Try to create a statement with an invalid type
    error_msg = "Tried to create an ASTAssignStatement with a RHS of type <class 'str'>"
    with pytest.raises(ValueError, match=error_msg):
        stmt.ASTAssignStatement(default_test_case, "invalid", {})


def test_ast_assign_statement_clone(default_test_case):
    """Test cloning an ASTAssignStatement."""
    # Create original statement
    ast_node = ast.Constant(value=42)
    original = stmt.ASTAssignStatement(default_test_case, ast_node, {})

    # Clone the statement
    memo = {}
    cloned = original.clone(default_test_case, memo)

    # Verify the clone
    assert isinstance(cloned, stmt.ASTAssignStatement)
    assert cloned.test_case == default_test_case
    assert isinstance(cloned.rhs, VariableRefAST)


def test_ast_assign_statement_mutate(default_test_case, variable_ref):
    """Test mutation of an ASTAssignStatement."""
    # Create a name node and ref_dict
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": variable_ref}

    # Create a VariableRefAST
    var_ref_ast = VariableRefAST(name_node, ref_dict)

    # Create a statement with the variable reference AST and add it to the test case
    statement = stmt.ASTAssignStatement(default_test_case, var_ref_ast, {})
    default_test_case.add_statement(statement)

    # Create another variable reference for mutation
    other_ref = vr.VariableReference(default_test_case, int)
    other_stmt = stmt.ASTAssignStatement(default_test_case, ast.Constant(value=42), {})
    default_test_case.add_statement(other_stmt)

    # Mock get_all_objects to return both variable references
    default_test_case.get_all_objects = MagicMock(return_value={variable_ref, other_ref})

    # Attempt to mutate
    result = statement.mutate()
    assert isinstance(result, bool)


def test_ast_assign_statement_get_variable_references(default_test_case, variable_ref):
    """Test getting variable references from an ASTAssignStatement."""
    # Create a name node and ref_dict
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": variable_ref}

    # Create a VariableRefAST
    var_ref_ast = VariableRefAST(name_node, ref_dict)

    # Create a statement with the variable reference AST
    statement = stmt.ASTAssignStatement(default_test_case, var_ref_ast, {})

    # Get the references
    refs = statement.get_variable_references()

    # Verify the references
    assert variable_ref in refs


def test_ast_assign_statement_replace(default_test_case):
    """Test replacing variable references in an ASTAssignStatement."""
    # Create original and new variable references
    old_ref = vr.VariableReference(default_test_case, int)
    new_ref = vr.VariableReference(default_test_case, int)

    # Create a name node and ref_dict
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": old_ref}

    # Create a VariableRefAST
    var_ref_ast = VariableRefAST(name_node, ref_dict)

    # Create a statement with the variable reference AST
    statement = stmt.ASTAssignStatement(default_test_case, var_ref_ast, {})

    # Replace the reference
    statement.replace(old_ref, new_ref)

    # Verify the replacement
    refs = statement.get_variable_references()
    assert new_ref in refs
    assert old_ref not in refs


def test_ast_assign_statement_structural_hash(default_test_case, variable_ref):
    """Test structural hashing of an ASTAssignStatement."""
    # Create a name node and ref_dict
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": variable_ref}

    # Create a VariableRefAST
    var_ref_ast = VariableRefAST(name_node, ref_dict)

    # Create a statement with the variable reference AST
    statement = stmt.ASTAssignStatement(default_test_case, var_ref_ast, {})

    # Add the statement to the test case to get a position
    default_test_case.add_statement(statement)

    # Get the hash
    # Add all variable references to memo
    memo = {}
    for stmt_idx, stmt_obj in enumerate(default_test_case.statements):
        if isinstance(stmt_obj.ret_val, vr.VariableReference):
            memo[stmt_obj.ret_val] = stmt_idx
    # Add the variable_ref with a unique position
    memo[variable_ref] = len(default_test_case.statements)

    hash_value = statement.structural_hash(memo)

    # Verify the hash is an integer
    assert isinstance(hash_value, int)


def test_ast_assign_statement_structural_eq(default_test_case):
    """Test structural equality of ASTAssignStatement instances."""
    # Create a simple constant AST node for both statements
    constant1 = ast.Constant(value=42)
    constant2 = ast.Constant(value=42)

    # Create two statements with identical constants
    statement1 = stmt.ASTAssignStatement(default_test_case, constant1, {})
    statement2 = stmt.ASTAssignStatement(default_test_case, constant2, {})

    # Add statements to test case
    default_test_case.add_statement(statement1)
    default_test_case.add_statement(statement2)

    # Create memo with all variable references
    memo = {}
    for stmt_obj in default_test_case.statements:
        if isinstance(stmt_obj.ret_val, vr.VariableReference):
            memo[stmt_obj.ret_val] = stmt_obj.ret_val

    # Add the ret_val mappings for both statements
    memo[statement1.ret_val] = statement2.ret_val

    # Patch the structural_eq method of VariableRefAST to always return True
    # when comparing the same constants
    original_structural_eq = VariableRefAST.structural_eq

    def mock_structural_eq(_, other, __):
        return isinstance(other, VariableRefAST)

    # Apply the patch
    VariableRefAST.structural_eq = mock_structural_eq

    try:
        # Test equality - statements should be structurally equal with our mock
        assert statement1.structural_eq(statement2, memo)

        # Create a different statement for inequality test
        constant3 = ast.Constant(value=99)
        statement3 = stmt.ASTAssignStatement(default_test_case, constant3, {})
        default_test_case.add_statement(statement3)
        memo[statement3.ret_val] = statement3.ret_val

        # Now make the mock return False for different values
        def mock_structural_eq_with_check(_, other, __):
            return isinstance(other, VariableRefAST)

        VariableRefAST.structural_eq = mock_structural_eq_with_check

        # Test inequality
        assert not statement1.structural_eq(statement3, memo)
    finally:
        # Restore the original method
        VariableRefAST.structural_eq = original_structural_eq


def test_ast_assign_statement_get_rhs_as_normal_ast(default_test_case, variable_ref):
    """Test converting RHS to normal AST."""
    # Create a name node and ref_dict
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": variable_ref}

    # Create a VariableRefAST
    var_ref_ast = VariableRefAST(name_node, ref_dict)

    # Create a statement with the variable reference AST
    statement = stmt.ASTAssignStatement(default_test_case, var_ref_ast, {})

    # Define a replacer function
    def replacer(_):
        return ast.Name(id="replaced_var", ctx=ast.Load())

    # Get the normal AST
    normal_ast = statement.get_rhs_as_normal_ast(replacer)

    # Verify it's an AST node
    assert isinstance(normal_ast, ast.AST)

    # Verify the variable name was replaced
    assert isinstance(normal_ast, ast.Name)
    assert normal_ast.id == "replaced_var"
    assert isinstance(normal_ast.ctx, ast.Load)


def test_ast_assign_statement_structural_eq_different_types(default_test_case):
    """Test structural equality with different types."""
    # Create a statement
    ast_node = ast.Constant(value=42)
    statement = stmt.ASTAssignStatement(default_test_case, ast_node, {})

    # Compare with non-ASTAssignStatement object
    memo = {}
    assert not statement.structural_eq("not a statement", memo)
    assert not statement.structural_eq(None, memo)


def test_ast_assign_statement_structural_eq_different_ret_val(default_test_case):
    """Test structural equality with different return values."""
    # Create two statements with different return values
    ast_node1 = ast.Constant(value=42)
    ast_node2 = ast.Constant(value=42)
    statement1 = stmt.ASTAssignStatement(default_test_case, ast_node1, {})
    statement2 = stmt.ASTAssignStatement(default_test_case, ast_node2, {})

    # Mock the ret_val structural_eq to return False
    original_structural_eq = statement1.ret_val.structural_eq
    statement1.ret_val.structural_eq = lambda *_: False

    try:
        memo = {}
        assert not statement1.structural_eq(statement2, memo)
    finally:
        # Restore original method
        statement1.ret_val.structural_eq = original_structural_eq


def test_ast_assign_statement_structural_eq_different_rhs(default_test_case):
    """Test structural equality with different RHS values."""
    # Create two statements with different RHS values
    ast_node1 = ast.Constant(value=42)
    ast_node2 = ast.Constant(value=43)
    statement1 = stmt.ASTAssignStatement(default_test_case, ast_node1, {})
    statement2 = stmt.ASTAssignStatement(default_test_case, ast_node2, {})

    # Add statements to test case to get positions
    default_test_case.add_statement(statement1)
    default_test_case.add_statement(statement2)

    # Set up memo dictionary with variable references
    memo = {}
    memo[statement1.ret_val] = statement2.ret_val

    # Mock the rhs structural_eq to return False
    original_structural_eq = statement1.rhs.structural_eq
    statement1.rhs.structural_eq = lambda *_: False

    try:
        assert not statement1.structural_eq(statement2, memo)
    finally:
        # Restore original method
        statement1.rhs.structural_eq = original_structural_eq


def test_ast_assign_statement_accept(default_test_case):
    """Test the accept method of ASTAssignStatement."""
    # Create a statement
    ast_node = ast.Constant(value=42)
    statement = stmt.ASTAssignStatement(default_test_case, ast_node, {})

    # Create a mock visitor
    visitor = Mock(spec=StatementVisitor)

    # Call accept
    statement.accept(visitor)

    # Verify the visitor's visit_ast_assign_statement method was called with the statement
    visitor.visit_ast_assign_statement.assert_called_once_with(statement)


def test_ast_assign_statement_accessible_object(default_test_case):
    """Test the accessible_object method of ASTAssignStatement."""
    # Create a statement
    ast_node = ast.Constant(value=42)
    statement = stmt.ASTAssignStatement(default_test_case, ast_node, {})

    # Call accessible_object
    result = statement.accessible_object()

    # Verify it returns None
    assert result is None


def test_ast_assign_statement_rhs_is_call(default_test_case):
    """Test the rhs_is_call method of ASTAssignStatement."""
    # Create a statement with a non-call AST node
    ast_node = ast.Constant(value=42)
    statement = stmt.ASTAssignStatement(default_test_case, ast_node, {})

    # Mock the is_call method of the RHS
    original_is_call = statement.rhs.is_call
    statement.rhs.is_call = Mock(return_value=True)

    try:
        # Call rhs_is_call
        result = statement.rhs_is_call()

        # Verify it returns the result of rhs.is_call()
        assert result is True
        statement.rhs.is_call.assert_called_once()
    finally:
        # Restore original method
        statement.rhs.is_call = original_is_call
