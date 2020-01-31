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
import random
from abc import abstractmethod
from typing import Type, Any, Optional

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.testcase.statements.statementvisitor as sv
from pynguin.testcase.statements.statement import Statement
from pynguin.utils import randomness


class PrimitiveStatement(stmt.Statement):
    # TODO(fk) add generic annotation of value type.
    """Abstract primitive statement which holds a value."""

    def __init__(
        self, test_case: tc.TestCase, variable_type: Type, value: Optional[Any] = None
    ) -> None:
        super().__init__(test_case, vri.VariableReferenceImpl(test_case, variable_type))
        self._value = value
        if not value:
            self.randomize_value()

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

    def __repr__(self) -> str:
        return (
            f"PrimitiveStatement({self._test_case}, {self._return_value}, "
            f"{self._value})"
        )

    def __str__(self) -> str:
        return f"{self._value}: {self._return_value}"

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, PrimitiveStatement):
            return False
        return self._return_value == other._return_value and self._value == other._value

    def __hash__(self) -> int:
        return (
            31
            + 17 * hash(self._test_case)
            + hash(self._return_value)
            + hash(self._value)
        )


class IntPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates an int."""

    def __init__(self, test_case: tc.TestCase, value: Optional[int] = None) -> None:
        super().__init__(test_case, int, value)

    def randomize_value(self) -> None:
        self._value = random.randint(-100, 100)

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return IntPrimitiveStatement(test_case, self._value)

    def __repr__(self) -> str:
        return f"IntPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: int"

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_int_primitive_statement(self)


class FloatPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates a float."""

    def __init__(self, test_case: tc.TestCase, value: Optional[float] = None) -> None:
        super().__init__(test_case, float, value)

    def randomize_value(self) -> None:
        self._value = random.uniform(-100, 100)

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return FloatPrimitiveStatement(test_case, self._value)

    def __repr__(self) -> str:
        return f"FloatPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: float"

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_float_primitive_statement(self)


class StringPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates a String."""

    def __init__(self, test_case: tc.TestCase, value: Optional[str] = None) -> None:
        super().__init__(test_case, str, value)

    def randomize_value(self) -> None:
        length = randomness.next_int(lower_bound=1)
        self._value = randomness.next_string(length)

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return StringPrimitiveStatement(test_case, self._value)

    def __repr__(self) -> str:
        return f"StringPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: str"

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_string_primitive_statement(self)


class BooleanPrimitiveStatement(PrimitiveStatement):
    """Primitive Statement that creates a boolean."""

    def __init__(self, test_case: tc.TestCase, value: Optional[bool] = None) -> None:
        super().__init__(test_case, bool, value)

    def randomize_value(self) -> None:
        self._value = bool(random.getrandbits(1))

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return BooleanPrimitiveStatement(test_case, self._value)

    def __repr__(self) -> str:
        return f"BooleanPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: bool"

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_boolean_primitive_statement(self)


class NoneStatement(PrimitiveStatement):
    """A statement serving as a None reference."""

    def clone(self, test_case: tc.TestCase) -> Statement:
        raise Exception("Cloning is not supported for NoneStatement")

    def accept(self, visitor: sv.StatementVisitor) -> None:
        pass

    def randomize_value(self) -> None:
        raise Exception("Cannot randomize value for NoneStatement")

    def __repr__(self) -> str:
        return f"NoneStatement({self._test_case})"

    def __str__(self) -> str:
        return "None"
