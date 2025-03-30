#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Helper for copying references from one test case to another."""

from __future__ import annotations

import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr

from pynguin.assertion.assertion import FloatAssertion
from pynguin.assertion.assertion import IsInstanceAssertion
from pynguin.assertion.assertion import ObjectAssertion
from pynguin.utils.orderedset import OrderedSet


class TestCaseReferenceCopier:
    """Handles copying references from one test case to another."""

    def __init__(
        self,
        original: tc.TestCase,
        target: tc.TestCase,
        refs_replacement_dict: dict,
    ):
        """Initialize the copier with original and target test cases.

        Args:
            original (tc.TestCase): The original test case with correct references.
            target (tc.TestCase): The target test case to update.
            refs_replacement_dict (dict): A dictionary mapping new to old references.
        """
        self.original = original
        self.target = target
        self.refs_replacement_dict = refs_replacement_dict

    def _get_target_source(
        self, source: vr.VariableReference
    ) -> vr.FieldReference | vr.VariableReference:
        """Get the corresponding variable or field reference from the replacement dict.

        Args:
            source: The original source reference from the assertion.

        Returns:
            The updated reference if found in the replacement dict; otherwise, the original.
        """
        if isinstance(source, vr.VariableReference):
            return self.refs_replacement_dict.get(source, source)

        if isinstance(source, vr.FieldReference):
            var_ref = source.get_variable_reference()
            if var_ref in self.refs_replacement_dict:
                return vr.FieldReference(
                    self.refs_replacement_dict[var_ref],
                    source.field,
                )
        return source

    def copy(self):
        """Perform the copy operation for all statements in the target test case."""
        for target_stmt in self.target.statements:
            original_stmt = self.original.statements[target_stmt.get_position()]
            self._handle_ret_val(target_stmt, original_stmt)
            self._handle_callee(target_stmt, original_stmt)
            self._handle_args(target_stmt, original_stmt)
            self._handle_assertions(target_stmt)

    def _handle_ret_val(self, target_stmt, original_stmt):
        """Replace the return value in the target statement with the original's.

        Args:
            target_stmt: The statement in the target test case.
            original_stmt: The corresponding statement in the original test case.
        """
        if hasattr(target_stmt, "ret_val") and hasattr(original_stmt, "ret_val"):
            self.refs_replacement_dict[target_stmt.ret_val] = original_stmt.ret_val
            target_stmt.ret_val = original_stmt.ret_val

    def _handle_callee(self, target_stmt, original_stmt):
        """Replace the callee reference in the target with the original's.

        Args:
            target_stmt: The statement in the target test case.
            original_stmt: The corresponding statement in the original test case.
        """
        if hasattr(target_stmt, "callee") and hasattr(original_stmt, "callee"):
            target_callee = target_stmt.callee
            original_callee = original_stmt.callee
            if target_callee in self.refs_replacement_dict:
                target_stmt.callee = self.refs_replacement_dict[target_callee]
            else:
                self.refs_replacement_dict[target_callee] = original_callee
                target_stmt.callee = original_callee

    def _handle_args(self, target_stmt, original_stmt):
        """Replace argument references in the target with those from the original.

        Args:
            target_stmt: The statement in the target test case.
            original_stmt: The corresponding statement in the original test case.
        """
        if hasattr(target_stmt, "args") and hasattr(original_stmt, "args"):
            for arg_key, target_arg in target_stmt.args.items():
                original_arg = original_stmt.args.get(arg_key)
                if target_arg in self.refs_replacement_dict:
                    target_stmt.args[arg_key] = self.refs_replacement_dict[target_arg]
                else:
                    self.refs_replacement_dict[target_arg] = original_arg
                    target_stmt.args[arg_key] = original_arg

    def _handle_assertions(self, target_stmt):
        """Copy and update assertion references in the target statement."""
        if not hasattr(target_stmt, "assertions"):
            return

        new_assertions: OrderedSet = OrderedSet()
        for target_assertion in target_stmt.assertions:
            source = target_assertion.source
            target_source = self._get_target_source(source)

            new_assertion = create_new_assertion(target_assertion, target_source)
            new_assertions.add(new_assertion)

        target_stmt.assertions = new_assertions


def create_new_assertion(target_assertion, target_source):
    """Create a new assertion object with the updated source reference.

    Args:
        target_assertion: The original assertion from the target statement.
        target_source: The updated source reference.

    Returns:
        A new assertion object or the original if the type is unsupported.
    """
    if isinstance(target_assertion, FloatAssertion):
        return FloatAssertion(target_source, target_assertion.value)
    if isinstance(target_assertion, IsInstanceAssertion):
        return IsInstanceAssertion(target_source, target_assertion.expected_type)
    if isinstance(target_assertion, ObjectAssertion):
        return ObjectAssertion(target_source, target_assertion.object)
    return target_assertion  # fallback if unknown type
