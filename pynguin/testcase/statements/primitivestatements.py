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
"""Provides primitive statements."""
from abc import abstractmethod
from typing import Type, Any

from pynguin.testcase.statements.statement import Statement
from pynguin.testcase.testcase import TestCase


from pynguin.testcase.variable.variablereferenceimpl import VariableReferenceImpl


class PrimitiveStatement(Statement):
    # TODO(fk) add generic annotation of value type.
    """Abstract primitive statement which holds a value."""

    def __init__(self, test_case: TestCase, variable_type: Type, value: Any) -> None:
        super().__init__(test_case, VariableReferenceImpl(test_case, variable_type))
        self._value = value

    @property
    def value(self) -> Any:
        """Provides the primitive value of this statement"""
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        self._value = value

    @abstractmethod
    def randomize_value(self) -> None:
        """Randomize the primitive value of this statement."""
        # TODO(fk) move value generation for each primitive to the corresponding subclasses.


class IntPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates an int."""

    def __init__(self, test_case: TestCase, value: Any) -> None:
        super().__init__(test_case, int, value)

    def randomize_value(self) -> None:
        pass

    def clone(self, test_case: TestCase) -> Statement:
        return IntPrimitiveStatement(test_case, self._value)


class FloatPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates a float."""

    def __init__(self, test_case: TestCase, value: Any) -> None:
        super().__init__(test_case, float, value)

    def randomize_value(self) -> None:
        pass

    def clone(self, test_case: TestCase) -> Statement:
        return FloatPrimitiveStatement(test_case, self._value)


class StringPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates a String."""

    def __init__(self, test_case: TestCase, value: Any) -> None:
        super().__init__(test_case, str, value)

    def randomize_value(self) -> None:
        pass

    def clone(self, test_case: TestCase) -> Statement:
        return StringPrimitiveStatement(test_case, self._value)


class BooleanPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates a boolean."""

    def __init__(self, test_case: TestCase, value: Any) -> None:
        super().__init__(test_case, bool, value)

    def randomize_value(self) -> None:
        pass

    def clone(self, test_case: TestCase) -> Statement:
        return StringPrimitiveStatement(test_case, self._value)
