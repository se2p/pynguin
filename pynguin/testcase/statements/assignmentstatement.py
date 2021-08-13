#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""
Provide a statement that performs assignments.
"""
from typing import Any, Dict, Optional, Set

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class AssignmentStatement(stmt.Statement):
    """A statement that assigns one variable to another."""

    def __init__(
        self,
        test_case: tc.TestCase,
        lhs: vr.VariableReference,
        rhs: vr.VariableReference,
    ):
        super().__init__(test_case, lhs)
        self._rhs = rhs

    @property
    def rhs(self) -> vr.VariableReference:
        """The variable that is used as the right hand side.

        Returns:
            The variable used as the right hand side
        """
        return self._rhs

    def clone(
        self,
        test_case: tc.TestCase,
        memo: Dict[vr.VariableReference, vr.VariableReference],
    ) -> stmt.Statement:
        return AssignmentStatement(
            test_case,
            self.ret_val.clone(memo),
            self._rhs.clone(memo),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_assignment_statement(self)

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return None

    def mutate(self) -> bool:
        raise Exception("Implement me")

    def get_variable_references(self) -> Set[vr.VariableReference]:
        return {self.ret_val, self._rhs}

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        if self._rhs == old:
            self._rhs = new

    def structural_hash(self) -> int:
        return (
            31 + 17 * self._ret_val.structural_hash() + 17 * self._rhs.structural_hash()
        )

    def structural_eq(
        self, other: Any, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, AssignmentStatement):
            return False
        return self._ret_val.structural_eq(
            other._ret_val, memo
        ) and self._rhs.structural_eq(other._rhs, memo)
