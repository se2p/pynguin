#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the TestCaseReferenceCopier class."""

import ast
import math

from unittest.mock import MagicMock

import pytest

import pynguin.large_language_model.helpers.testcasereferencecopier as trc
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr

from pynguin.assertion.assertion import FloatAssertion
from pynguin.assertion.assertion import IsInstanceAssertion
from pynguin.utils.generic.genericaccessibleobject import GenericField


@pytest.fixture
def original_test_case():
    """Create a mock original test case."""
    return MagicMock(tc.TestCase)


@pytest.fixture
def target_test_case():
    """Create a mock target test case."""
    return MagicMock(tc.TestCase)


@pytest.fixture
def refs_replacement_dict():
    """Create a mock replacement dictionary."""
    return {}


@pytest.fixture
def reference_copier(original_test_case, target_test_case, refs_replacement_dict):
    """Create a TestCaseReferenceCopier instance."""
    return trc.TestCaseReferenceCopier(original_test_case, target_test_case, refs_replacement_dict)


def test_get_target_source_field_reference(reference_copier):
    """Test _get_target_source with a FieldReference instance."""
    # Create a variable reference
    var_ref = MagicMock(vr.VariableReference)
    var_ref.get_variable_reference.return_value = var_ref

    # Create a field reference that uses the variable reference
    field = MagicMock(GenericField)
    field_ref = MagicMock(vr.FieldReference)
    field_ref.get_variable_reference.return_value = var_ref
    field_ref.field = field

    # Add the variable reference to the replacement dictionary
    new_var_ref = MagicMock(vr.VariableReference)
    reference_copier.refs_replacement_dict[var_ref] = new_var_ref

    # Call _get_target_source
    reference_copier._get_target_source(field_ref)

    # Verify that a new FieldReference was created with the replaced variable reference
    # We can't directly check the implementation details, but we can verify that the
    # method was called
    field_ref.get_variable_reference.assert_called_once()
    # The test passes if it reaches this point without errors


def test_get_target_source_field_reference_not_in_dict(reference_copier):
    """Test _get_target_source with a FieldReference where the variable reference is not in dict.

    Tests behavior when variable reference is not found in the replacement dict.
    """
    # Create a variable reference
    var_ref = MagicMock(vr.VariableReference)

    # Create a field reference that uses the variable reference
    field = MagicMock(GenericField)
    field_ref = vr.FieldReference(var_ref, field)

    # Call _get_target_source
    result = reference_copier._get_target_source(field_ref)

    # Verify that the original field reference is returned
    assert result == field_ref


def test_handle_callee_not_in_dict(reference_copier):
    """Test _handle_callee when the target callee is not in the replacement dictionary."""
    # Create mock statements
    target_stmt = MagicMock()
    original_stmt = MagicMock()

    # Set up callees
    target_callee = MagicMock(vr.VariableReference)
    original_callee = MagicMock(vr.VariableReference)
    target_stmt.callee = target_callee
    original_stmt.callee = original_callee

    # Call _handle_callee
    reference_copier._handle_callee(target_stmt, original_stmt)

    # Verify that the target callee was replaced with the original callee
    assert reference_copier.refs_replacement_dict[target_callee] == original_callee
    assert target_stmt.callee == original_callee


def test_handle_args_not_in_dict(reference_copier):
    """Test _handle_args when the target argument is not in the replacement dictionary."""
    # Create mock statements
    target_stmt = MagicMock()
    original_stmt = MagicMock()

    # Set up args
    target_arg = MagicMock(vr.VariableReference)
    original_arg = MagicMock(vr.VariableReference)
    target_stmt.args = {"arg1": target_arg}
    original_stmt.args = {"arg1": original_arg}

    # Call _handle_args
    reference_copier._handle_args(target_stmt, original_stmt)

    # Verify that the target arg was replaced with the original arg
    assert reference_copier.refs_replacement_dict[target_arg] == original_arg
    assert target_stmt.args["arg1"] == original_arg


def test_handle_assertions_no_assertions(reference_copier):
    """Test _handle_assertions when the target statement doesn't have assertions."""
    # Create a mock statement without assertions
    target_stmt = MagicMock(spec=[])

    # Call _handle_assertions
    reference_copier._handle_assertions(target_stmt)

    # No assertions to verify, just make sure it doesn't raise an exception


def test_create_new_assertion_float_assertion():
    """Test create_new_assertion with a FloatAssertion."""
    # Create a mock source
    source = MagicMock(vr.VariableReference)

    # Create a FloatAssertion
    original_assertion = FloatAssertion(source, math.pi)

    # Call create_new_assertion
    new_assertion = trc.create_new_assertion(original_assertion, source)

    # Verify that a new FloatAssertion was created with the same value
    assert isinstance(new_assertion, FloatAssertion)
    assert new_assertion.source == source
    assert new_assertion.value == math.pi


def test_create_new_assertion_isinstance_assertion():
    """Test create_new_assertion with an IsInstanceAssertion."""
    # Create a mock source
    source = MagicMock(vr.VariableReference)

    # Create an IsInstanceAssertion
    expected_type = ast.Name(id="int", ctx=ast.Load())
    original_assertion = IsInstanceAssertion(source, expected_type)

    # Call create_new_assertion
    new_assertion = trc.create_new_assertion(original_assertion, source)

    # Verify that a new IsInstanceAssertion was created with the same expected type
    assert isinstance(new_assertion, IsInstanceAssertion)
    assert new_assertion.source == source
    assert new_assertion.expected_type == expected_type


def test_create_new_assertion_fallback():
    """Test create_new_assertion with an unsupported assertion type."""
    # Create a mock source and assertion
    source = MagicMock(vr.VariableReference)
    original_assertion = MagicMock()

    # Call create_new_assertion
    new_assertion = trc.create_new_assertion(original_assertion, source)

    # Verify that the original assertion is returned
    assert new_assertion == original_assertion
