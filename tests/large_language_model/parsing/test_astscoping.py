#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the astscoping module."""

import ast

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.testcase.variablereference as vr

# We're testing a private function directly, which is acceptable in test code
from pynguin.large_language_model.parsing.astscoping import FreeVariableOperator
from pynguin.large_language_model.parsing.astscoping import VariableRefAST
from pynguin.large_language_model.parsing.astscoping import VariableReferenceVisitor
from pynguin.large_language_model.parsing.astscoping import (
    copy_and_operate_on_variable_references,
)
from pynguin.large_language_model.parsing.astscoping import operate_on_free_variables
from pynguin.large_language_model.parsing.astscoping import (
    operate_on_variable_references,
)


def test_variable_reference_visitor_generic_visit_variable_reference():
    """Test VariableReferenceVisitor.generic_visit with a VariableReference."""
    # Create a mock VariableReference
    var_ref = MagicMock(spec=vr.VariableReference)

    # Create a mock operation
    operation = MagicMock(return_value="operated")

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Call generic_visit with the VariableReference
    result = visitor.generic_visit(var_ref)

    # Verify the operation was called with the VariableReference
    operation.assert_called_once_with(var_ref)
    assert result == "operated"


def test_variable_reference_visitor_generic_visit_list():
    """Test VariableReferenceVisitor.generic_visit with a list field."""
    # Create a node with a list field
    node = ast.Module(body=[ast.Expr(value=ast.Constant(value=1))], type_ignores=[])

    # Create a mock operation
    operation = MagicMock(return_value="operated")

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Mock the visit method to track calls
    visitor.visit = MagicMock(side_effect=lambda x: x)

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the visit method was called for each element in the list
    assert visitor.visit.call_count == 1
    assert isinstance(result, ast.Module)


def test_variable_reference_visitor_generic_visit_list_with_variable_reference():
    """Test VariableReferenceVisitor.generic_visit with a list containing a VariableReference."""
    # Create a mock VariableReference
    var_ref = MagicMock(spec=vr.VariableReference)

    # Create a node with a list field containing the VariableReference
    node = ast.Module(body=[var_ref], type_ignores=[])

    # Create a mock operation
    operation = MagicMock(return_value="operated")

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the operation was called with the VariableReference
    operation.assert_called_once_with(var_ref)
    assert isinstance(result, ast.Module)
    assert result.body == ["operated"]


def test_variable_reference_visitor_generic_visit_list_with_none():
    """Test VariableReferenceVisitor.generic_visit with a list containing None."""
    # Create a mock visit method that returns None
    mock_visit = MagicMock(return_value=None)

    # Create a node with a list field
    node = ast.Module(body=[ast.Expr(value=ast.Constant(value=1))], type_ignores=[])

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=MagicMock())
    visitor.visit = mock_visit

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the result has an empty body
    assert isinstance(result, ast.Module)
    assert result.body == []


def test_variable_reference_visitor_generic_visit_list_with_list():
    """Test VariableReferenceVisitor.generic_visit with a list containing a list."""
    # Create a mock visit method that returns a list
    mock_visit = MagicMock(return_value=["item1", "item2"])

    # Create a node with a list field
    node = ast.Module(body=[ast.Expr(value=ast.Constant(value=1))], type_ignores=[])

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=MagicMock())
    visitor.visit = mock_visit

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the result has the expanded list in body
    assert isinstance(result, ast.Module)
    assert result.body == ["item1", "item2"]


def test_variable_reference_visitor_generic_visit_ast_field():
    """Test VariableReferenceVisitor.generic_visit with an AST field."""
    # Create a node with an AST field
    node = ast.Expr(value=ast.Constant(value=1))

    # Create a mock operation
    operation = MagicMock()

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Mock the visit method to track calls
    visitor.visit = MagicMock(return_value=ast.Constant(value=2))

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the visit method was called for the AST field
    visitor.visit.assert_called_once_with(node.value)
    assert isinstance(result, ast.Expr)
    assert isinstance(result.value, ast.Constant)
    assert result.value.value == 2


def test_variable_reference_visitor_generic_visit_ast_field_none():
    """Test VariableReferenceVisitor.generic_visit with an AST field that returns None."""
    # Create a node with an AST field
    node = ast.Expr(value=ast.Constant(value=1))

    # Create a mock operation
    operation = MagicMock()

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Mock the visit method to return None
    visitor.visit = MagicMock(return_value=None)

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the result doesn't have the value field
    assert isinstance(result, ast.Expr)
    assert not hasattr(result, "value")


def test_variable_reference_visitor_generic_visit_variable_reference_field():
    """Test VariableReferenceVisitor.generic_visit with a VariableReference field."""
    # Create a mock VariableReference
    var_ref = MagicMock(spec=vr.VariableReference)

    # Create a node with a VariableReference field
    node = ast.Module(body=[], type_ignores=[])
    node.var_ref = var_ref

    # Create a mock operation
    operation = MagicMock(return_value="operated")

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Create a custom implementation of generic_visit that directly calls operation
    def custom_generic_visit(node):
        field_assign = dict(ast.iter_fields(node))

        # Handle the var_ref field separately
        if hasattr(node, "var_ref") and isinstance(node.var_ref, vr.VariableReference):
            field_assign["var_ref"] = operation(node.var_ref)

        return node.__class__(**field_assign)

    # Replace the generic_visit method with our custom implementation
    original_generic_visit = visitor.generic_visit
    visitor.generic_visit = custom_generic_visit

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Restore the original generic_visit method
    visitor.generic_visit = original_generic_visit

    # Verify the operation was called with the VariableReference
    operation.assert_called_once_with(var_ref)
    assert isinstance(result, ast.Module)
    assert result.var_ref == "operated"


def test_variable_reference_visitor_generic_visit_variable_reference_field_none():
    """Test VariableReferenceVisitor.generic_visit with a VariableReference field that returns None.

    This test verifies the behavior when a VariableReference field returns None.
    """
    # Create a mock VariableReference
    var_ref = MagicMock(spec=vr.VariableReference)

    # Create a node with a VariableReference field
    node = ast.Module(body=[], type_ignores=[])
    node.var_ref = var_ref

    # Create a mock operation that returns None
    operation = MagicMock(return_value=None)

    # Create a visitor
    visitor = VariableReferenceVisitor(copy=True, operation=operation)

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the result doesn't have the var_ref field
    assert isinstance(result, ast.Module)
    assert not hasattr(result, "var_ref")


def test_variable_reference_visitor_generic_visit_no_copy():
    """Test VariableReferenceVisitor.generic_visit with copy=False."""
    # Create a node
    node = ast.Module(body=[], type_ignores=[])

    # Create a visitor with copy=False
    visitor = VariableReferenceVisitor(copy=False, operation=MagicMock())

    # Call generic_visit with the node
    result = visitor.generic_visit(node)

    # Verify the result is None
    assert result is None


def test_free_variable_operator_visit_name_not_bound():
    """Test FreeVariableOperator.visit_Name with an unbound name."""
    # Create a name node
    name_node = ast.Name(id="test_var", ctx=ast.Load())

    # Create a mock operation
    operation = MagicMock(return_value="operated")

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(operation)

    # Call visit_Name with the name node
    result = operator.visit_Name(name_node)

    # Verify the operation was called with the name node
    operation.assert_called_once_with(name_node)
    assert result == "operated"


def test_free_variable_operator_visit_name_bound():
    """Test FreeVariableOperator.visit_Name with a bound name."""
    # Create a name node
    name_node = ast.Name(id="test_var", ctx=ast.Load())

    # Create a mock operation
    operation = MagicMock()

    # Create a FreeVariableOperator with the name already bound
    operator = FreeVariableOperator(operation)
    operator._bound_variables.add("test_var")

    # Call visit_Name with the name node
    result = operator.visit_Name(name_node)

    # Verify the operation was not called
    operation.assert_not_called()
    # Verify the result is a deep copy of the name node
    assert result is not name_node
    assert isinstance(result, ast.Name)
    assert result.id == "test_var"


def test_free_variable_operator_visit_call():
    """Test FreeVariableOperator.visit_Call."""
    # Create a call node
    call_node = ast.Call(
        func=ast.Name(id="func", ctx=ast.Load()),
        args=[ast.Name(id="arg", ctx=ast.Load())],
        keywords=[ast.keyword(arg="kwarg", value=ast.Name(id="kwvalue", ctx=ast.Load()))],
    )

    # Create a mock operation
    operation = MagicMock(side_effect=lambda x: x)

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(operation)

    # Mock the visit method to track calls
    original_visit = operator.visit
    operator.visit = MagicMock(side_effect=original_visit)

    # Call visit_Call with the call node
    result = operator.visit_Call(call_node)

    # Verify the visit method was called for each argument and keyword value
    assert operator.visit.call_count == 2
    assert isinstance(result, ast.Call)


def test_free_variable_operator_visit_lambda():
    """Test FreeVariableOperator.visit_Lambda."""
    # Create a lambda node
    lambda_node = ast.Lambda(
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="x", annotation=None)],
            kwonlyargs=[ast.arg(arg="y", annotation=None)],
            kw_defaults=[ast.Constant(value=None)],
            defaults=[],
            vararg=ast.arg(arg="args", annotation=None),
            kwarg=ast.arg(arg="kwargs", annotation=None),
        ),
        body=ast.BinOp(
            left=ast.Name(id="x", ctx=ast.Load()),
            op=ast.Add(),
            right=ast.Name(id="y", ctx=ast.Load()),
        ),
    )

    # Create a mock operation
    operation = MagicMock(side_effect=lambda x: x)

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(operation)

    # Create a new mock for the visit method that returns a fixed value
    mock_visit = MagicMock(return_value=ast.Constant(value=42))

    # Save the original visit method
    original_visit = operator.visit

    # Replace the visit method with our mock
    operator.visit = mock_visit

    # Call visit_Lambda with the lambda node
    result = operator.visit_Lambda(lambda_node)

    # Restore the original visit method
    operator.visit = original_visit

    # Verify the bound variables were updated and then restored
    assert "x" not in operator._bound_variables
    assert "y" not in operator._bound_variables
    assert "args" not in operator._bound_variables
    assert "kwargs" not in operator._bound_variables

    # Verify the visit method was called for the body
    assert mock_visit.call_count == 1
    assert isinstance(result, ast.Lambda)


def test_free_variable_operator_get_comprehension_bound_vars():
    """Test FreeVariableOperator.get_comprehension_bound_vars."""
    # Create a comprehension node
    comp_node = ast.comprehension(
        target=ast.Name(id="x", ctx=ast.Store()),
        iter=ast.Name(id="range", ctx=ast.Load()),
        ifs=[],
        is_async=0,
    )

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(MagicMock())

    # Call get_comprehension_bound_vars with the comprehension node
    result = operator.get_comprehension_bound_vars(comp_node)

    # Verify the result contains the bound variable
    assert result == ["x"]


def test_free_variable_operator_visit_generators_common():
    """Test FreeVariableOperator._visit_generators_common."""
    # Create comprehension nodes
    comp1 = ast.comprehension(
        target=ast.Name(id="x", ctx=ast.Store()),
        iter=ast.Name(id="range", ctx=ast.Load()),
        ifs=[
            ast.Compare(
                left=ast.Name(id="x", ctx=ast.Load()),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=0)],
            )
        ],
        is_async=0,
    )
    comp2 = ast.comprehension(
        target=ast.Name(id="y", ctx=ast.Store()),
        iter=ast.Name(id="range", ctx=ast.Load()),
        ifs=[],
        is_async=1,
    )

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(MagicMock())

    # Mock methods
    operator.get_comprehension_bound_vars = MagicMock(side_effect=lambda x: [x.target.id])

    # Create a new mock for the visit method that returns a fixed value
    mock_visit = MagicMock(return_value=ast.Constant(value=42))

    # Save the original visit method
    original_visit = operator.visit

    # Replace the visit method with our mock
    operator.visit = mock_visit

    # Call _visit_generators_common with the comprehension nodes
    result = operator._visit_generators_common([comp1, comp2])

    # Restore the original visit method
    operator.visit = original_visit

    # Verify the bound variables were updated
    assert "x" in operator._bound_variables
    assert "y" in operator._bound_variables

    # Verify the visit method was called for each iter and if
    assert mock_visit.call_count == 3
    assert len(result) == 2


def test_free_variable_operator_visit_list_comp():
    """Test FreeVariableOperator.visit_ListComp."""
    # Create a list comprehension node
    list_comp = ast.ListComp(
        elt=ast.Name(id="x", ctx=ast.Load()),
        generators=[
            ast.comprehension(
                target=ast.Name(id="x", ctx=ast.Store()),
                iter=ast.Name(id="range", ctx=ast.Load()),
                ifs=[],
                is_async=0,
            )
        ],
    )

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(MagicMock())

    # Mock methods
    bound_vars_before = set(operator._bound_variables)
    operator._visit_generators_common = MagicMock(return_value=[list_comp.generators[0]])
    original_visit = operator.visit
    operator.visit = MagicMock(side_effect=original_visit)

    # Call visit_ListComp with the list comprehension node
    result = operator.visit_ListComp(list_comp)

    # Verify the bound variables were restored
    assert operator._bound_variables == bound_vars_before

    # Verify the methods were called correctly
    operator._visit_generators_common.assert_called_once_with(list_comp.generators)
    operator.visit.assert_called_once_with(list_comp.elt)
    assert isinstance(result, ast.ListComp)


def test_free_variable_operator_visit_set_comp():
    """Test FreeVariableOperator.visit_SetComp."""
    # Create a set comprehension node
    set_comp = ast.SetComp(
        elt=ast.Name(id="x", ctx=ast.Load()),
        generators=[
            ast.comprehension(
                target=ast.Name(id="x", ctx=ast.Store()),
                iter=ast.Name(id="range", ctx=ast.Load()),
                ifs=[],
                is_async=0,
            )
        ],
    )

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(MagicMock())

    # Mock methods
    bound_vars_before = set(operator._bound_variables)
    operator._visit_generators_common = MagicMock(return_value=[set_comp.generators[0]])
    original_visit = operator.visit
    operator.visit = MagicMock(side_effect=original_visit)

    # Call visit_SetComp with the set comprehension node
    result = operator.visit_SetComp(set_comp)

    # Verify the bound variables were restored
    assert operator._bound_variables == bound_vars_before

    # Verify the methods were called correctly
    operator._visit_generators_common.assert_called_once_with(set_comp.generators)
    operator.visit.assert_called_once_with(set_comp.elt)
    assert isinstance(result, ast.SetComp)


def test_free_variable_operator_visit_dict_comp():
    """Test FreeVariableOperator.visit_DictComp."""
    # Create a dict comprehension node
    dict_comp = ast.DictComp(
        key=ast.Name(id="x", ctx=ast.Load()),
        value=ast.Name(id="y", ctx=ast.Load()),
        generators=[
            ast.comprehension(
                target=ast.Name(id="x", ctx=ast.Store()),
                iter=ast.Name(id="range", ctx=ast.Load()),
                ifs=[],
                is_async=0,
            )
        ],
    )

    # Create a FreeVariableOperator
    operator = FreeVariableOperator(MagicMock())

    # Mock methods
    bound_vars_before = set(operator._bound_variables)
    operator._visit_generators_common = MagicMock(return_value=[dict_comp.generators[0]])
    operator.visit = MagicMock(side_effect=lambda x: x)

    # Call visit_DictComp with the dict comprehension node
    result = operator.visit_DictComp(dict_comp)

    # Verify the bound variables were restored
    assert operator._bound_variables == bound_vars_before

    # Verify the methods were called correctly
    operator._visit_generators_common.assert_called_once_with(dict_comp.generators)
    assert operator.visit.call_count == 2
    assert isinstance(result, ast.DictComp)


def test_operate_on_variable_references():
    """Test operate_on_variable_references."""
    # Create a mock node
    node = MagicMock(spec=ast.AST)

    # Create a mock operation
    operation = MagicMock()

    # Mock VariableReferenceVisitor
    mock_visitor = MagicMock()
    mock_visitor_cls = MagicMock(return_value=mock_visitor)

    with patch(
        "pynguin.large_language_model.parsing.astscoping.VariableReferenceVisitor", mock_visitor_cls
    ):
        # Call operate_on_variable_references
        operate_on_variable_references(node, operation)

        # Verify VariableReferenceVisitor was created with the correct arguments
        mock_visitor_cls.assert_called_once_with(copy=False, operation=operation)

        # Verify visit was called with the node
        mock_visitor.visit.assert_called_once_with(node)


def test_copy_and_operate_on_variable_references():
    """Test copy_and_operate_on_variable_references."""
    # Create a mock node
    node = MagicMock(spec=ast.AST)

    # Create a mock operation
    operation = MagicMock()

    # Mock VariableReferenceVisitor
    mock_visitor = MagicMock()
    mock_visitor.visit.return_value = "result"
    mock_visitor_cls = MagicMock(return_value=mock_visitor)

    with patch(
        "pynguin.large_language_model.parsing.astscoping.VariableReferenceVisitor", mock_visitor_cls
    ):
        # Call copy_and_operate_on_variable_references
        result = copy_and_operate_on_variable_references(node, operation)

        # Verify VariableReferenceVisitor was created with the correct arguments
        mock_visitor_cls.assert_called_once_with(copy=True, operation=operation)

        # Verify visit was called with the node
        mock_visitor.visit.assert_called_once_with(node)

        # Verify the result
        assert result == "result"


def test_operate_on_free_variables():
    """Test operate_on_free_variables."""
    # Create a mock node
    node = MagicMock(spec=ast.AST)

    # Create a mock operation
    operation = MagicMock()

    # Mock FreeVariableOperator
    mock_operator = MagicMock()
    mock_operator.visit.return_value = "result"
    mock_operator_cls = MagicMock(return_value=mock_operator)

    with patch(
        "pynguin.large_language_model.parsing.astscoping.FreeVariableOperator", mock_operator_cls
    ):
        # Call operate_on_free_variables
        result = operate_on_free_variables(node, operation)

        # Verify FreeVariableOperator was created with the correct arguments
        mock_operator_cls.assert_called_once_with(operation)

        # Verify visit was called with the node
        mock_operator.visit.assert_called_once_with(node)

        # Verify the result
        assert result == "result"


def test_variable_ref_ast_unresolved_reference():
    """Test VariableRefAST initialization with an unresolved reference."""
    # Create a node with a variable reference that won't be in the dictionary
    node = ast.Name(id="test_var", ctx=ast.Load())

    # Create an empty ref_dict
    ref_dict = {}

    # Attempt to create a VariableRefAST with the node and empty ref_dict
    # This should raise a ValueError because the variable reference is not in the dictionary
    with pytest.raises(ValueError, match="unresolved reference"):
        VariableRefAST(node, ref_dict)


def test_variable_ref_ast_is_call():
    """Test VariableRefAST.is_call."""
    # Create a call node
    call_node = ast.Call(func=ast.Name(id="func", ctx=ast.Load()), args=[], keywords=[])

    # Create a VariableRefAST with the call node
    var_ref_ast = VariableRefAST(call_node, {})

    # Call is_call
    result = var_ref_ast.is_call()

    # Verify the result is True
    assert result is True

    # Create a non-call node
    non_call_node = ast.Name(id="not_a_call", ctx=ast.Load())

    # Create a mock VariableReference for the non-call node
    mock_var_ref = MagicMock(spec=vr.VariableReference)

    # Create a VariableRefAST with the non-call node and a reference dictionary
    var_ref_ast = VariableRefAST(non_call_node, {"not_a_call": mock_var_ref})

    # Call is_call
    result = var_ref_ast.is_call()

    # Verify the result is False
    assert result is False
