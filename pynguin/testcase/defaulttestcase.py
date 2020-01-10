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
"""Provides a default implementation of a test case."""
import logging
from typing import List, Any

from pynguin.testcase.statements.statement import Statement
from pynguin.testcase.testcase import TestCase
from pynguin.testcase.variable.variablereference import VariableReference


class DefaultTestCase(TestCase):
    """A default implementation of a test case."""

    # pylint: disable=invalid-name
    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._statements: List[Statement] = []
        self._is_failing: bool = False
        self._id = self._id_generator.inc()

    @property
    def id(self) -> int:
        """Get an unique ID representing this test case.

        Mainly useful for debugging.

        :return: An unique ID representing this test case
        """
        return self._id

    def accept(self, visitor) -> None:
        pass

    def add_statement(
        self, statement: Statement, position: int = -1
    ) -> VariableReference:
        if position == -1:
            self._statements.append(statement)
        else:
            self._statements.insert(position, statement)
        return statement.return_value

    def add_statements(self, statements: List[Statement]) -> None:
        self._statements.extend(statements)

    def remove(self, position: int) -> None:
        self._logger.debug("Removing statement at position %d", position)
        if position >= self.size():
            return
        del self._statements[position]

    def chop(self, length: int) -> None:
        assert length >= 0
        while len(self._statements) > length:
            del self._statements[-1]

    def contains(self, statement: Statement) -> bool:
        return statement in self._statements

    def get_statement(self, position: int) -> Statement:
        assert 0 <= position < len(self._statements)
        return self._statements[position]

    def has_statement(self, position: int) -> bool:
        return 0 <= position < len(self._statements)

    def clone(self) -> "TestCase":
        test_case = DefaultTestCase()
        for statement in self._statements:
            copy = statement.clone()
            test_case._statements.append(copy)
            copy.return_value = statement.return_value.clone()
        test_case._is_failing = self._is_failing
        test_case._id = self._id_generator.inc()
        return test_case

    def is_failing(self) -> bool:
        return self._is_failing

    def set_failing(self) -> None:
        self._is_failing = True

    def size(self) -> int:
        return len(self._statements)

    # pylint: disable=too-many-return-statements
    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not other:
            return False
        if not isinstance(other, DefaultTestCase):
            return False

        if not self._statements:
            if other._statements:
                return False
        else:
            if len(self._statements) != len(other._statements):
                return False
            for i in range(len(self._statements)):
                if self._statements[i] != other._statements[i]:
                    return False
        return True

    def __hash__(self) -> int:
        return 31 + sum([17 * s.__hash__() for s in self._statements])
