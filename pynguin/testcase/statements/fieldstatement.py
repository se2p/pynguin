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
Provides a statement that accesses public fields/properties.
"""
from typing import Type

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.testcase.statements.statementvisitor as sv


class FieldStatement(stmt.Statement):
    """
    A statement which accesses a public field or a property of an object.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        field: str,
        field_type: Type,
        source: vr.VariableReference,
    ):
        super().__init__(test_case, vri.VariableReferenceImpl(test_case, field_type))
        self._field = field
        self._source = source

    @property
    def source(self) -> vr.VariableReference:
        """
        Provides the variable that is accessed.
        """
        return self._source

    @property
    def field(self) -> str:
        """
        Provides the field name that is accessed.
        """
        return self._field

    @field.setter
    def field(self, field: str) -> None:
        self._field = field

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return FieldStatement(
            test_case,
            self._field,
            self.return_value.variable_type,
            self._source.clone(test_case),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_field_statement(self)
