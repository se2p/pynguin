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
from typing import Any, Optional, Set

import pynguin.configuration as config
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericField,
)


class FieldStatement(stmt.Statement):
    """A statement which accesses a public field or a property of an object."""

    def __init__(
        self, test_case: tc.TestCase, field: GenericField, source: vr.VariableReference,
    ):
        super().__init__(
            test_case, vri.VariableReferenceImpl(test_case, field.generated_type())
        )
        self._field = field
        self._source = source

    @property
    def source(self) -> vr.VariableReference:
        """Provides the variable that is accessed.

        Returns:
            The variable that is accessed
        """
        return self._source

    @source.setter
    def source(self, new_source: vr.VariableReference) -> None:
        """Set new source.

        Args:
            new_source: The new variable to access
        """
        self._source = new_source

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return self._field

    def mutate(self) -> bool:
        if randomness.next_float() >= config.INSTANCE.change_parameter_probability:
            return False

        objects = self.test_case.get_objects(
            self.source.variable_type, self.get_position()
        )
        objects.remove(self.source)
        if len(objects) > 0:
            self.source = randomness.choice(objects)
            return True
        return False

    @property
    def field(self) -> GenericField:
        """The used field.

        Returns:
            The used field
        """
        return self._field

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return FieldStatement(
            test_case, self._field, self._source.clone(test_case, offset)
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_field_statement(self)

    def get_variable_references(self) -> Set[vr.VariableReference]:
        return {self.source}

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.source == old:
            self.source = new

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, FieldStatement):
            return False
        return self._field == other._field

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._field)
