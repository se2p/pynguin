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
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr


class AssignmentStatement(stmt.Statement):
    """
    A statement that assigns one variable to another.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        lhs: vr.VariableReference,
        rhs: vr.VariableReference,
    ):
        super().__init__(test_case, lhs)
        self._rhs = rhs

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return AssignmentStatement(
            test_case, self.return_value.clone(test_case), self._rhs.clone(test_case)
        )
