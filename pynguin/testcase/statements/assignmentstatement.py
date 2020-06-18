# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""
Provide a statement that performs assignments.
"""
from typing import Any, Optional, Set

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

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return AssignmentStatement(
            test_case,
            self.return_value.clone(test_case, offset),
            self._rhs.clone(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_assignment_statement(self)

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return None

    def mutate(self) -> bool:
        raise Exception("Implement me")

    def get_variable_references(self) -> Set[vr.VariableReference]:
        return {self.return_value, self._rhs}

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.return_value == old:
            self.return_value = new
        if self._rhs == old:
            self._rhs = new

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._return_value) + 17 * hash(self._rhs)

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, AssignmentStatement):
            return False
        return self._return_value == other._return_value and self._rhs == other._rhs
