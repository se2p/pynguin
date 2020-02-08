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
"""Provides an implementation for a test case."""
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import List, Type, Optional

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.testcasevisitor as tcv
from pynguin.utils.atomicinteger import AtomicInteger


class TestCase(metaclass=ABCMeta):
    """An abstract base implementation for a test case.

    Serves as an interface for test-case implementations
    """

    _id_generator = AtomicInteger()

    def __init__(self) -> None:
        self._statements: List[stmt.Statement] = []

    @property
    def statements(self) -> List[stmt.Statement]:
        """Provides the list of statements in this test case.

        :return: The list of statements in this test case
        """
        return self._statements

    @abstractmethod
    def accept(self, visitor: tcv.TestCaseVisitor) -> None:
        """Handles a test visitor.

        :param visitor: The test visitor to accept
        """

    @abstractmethod
    def add_statement(
        self, statement: stmt.Statement, position: int = -1
    ) -> vr.VariableReference:
        """Adds a new statement to the test case.

        The optional position parameter specifies the position.  If it is not given,
        the statement will be added to the end of the test case.

        :param statement: The new statement
        :param position: The optional position where to put the statement
        :return: The return value of the statement.  Notice that the test might
        choose to modify the statement you inserted.  You should use the returned
        variable reference and not use references.
        """

    @abstractmethod
    def add_statements(self, statements: List[stmt.Statement]) -> None:
        """Adds a list of statements to the end of the test case.

        :param statements: The list of statements to add
        """

    def append_test_case(self, test_case: TestCase) -> None:
        """Appends a test case to this test case.

        :param test_case: The test case to append
        """
        size = self.size()
        for statement in test_case.statements:
            self._statements.append(statement.clone(self, size))

    @abstractmethod
    def remove(self, position: int) -> None:
        """Removes a statement a the given position

        :param position: The position of the test case to be removed
        """

    @abstractmethod
    def chop(self, length: int) -> None:
        """Remove all statements after a given position.

        :param length: The length of the test case after chopping
        """

    @abstractmethod
    def contains(self, statement: stmt.Statement) -> bool:
        """Determines whether or not the test case contains a specific statement.

        :param statement: The statement to search in the test case
        :return: Whether or not the test case contains the statement
        """

    @abstractmethod
    def get_statement(self, position: int) -> stmt.Statement:
        """Provides access to a statement at a given position.

        :param position: The position of the statement in the test case
        :return: The statement at the position
        """

    @abstractmethod
    def has_statement(self, position: int) -> bool:
        """Check if there is a statement at the given position.

        :param position: The index of the statement
        :return: Whether or not there is a statement at the given position
        """

    @abstractmethod
    def clone(self) -> TestCase:
        """Provides a deep copy of the test case.

        :return: A deep copy of this test case
        """

    @abstractmethod
    def is_failing(self) -> bool:
        """Checks if the test case is a failing test or not

        :return: Whether or not the test case is failing
        """

    @abstractmethod
    def set_failing(self) -> None:
        """Marks the test case as a failing test."""

    @abstractmethod
    def size(self) -> int:
        """Provides the number of statements in the test case.

        :return: The number of statements in the test case
        """

    def get_objects(
        self, parameter_type: Optional[Type], position: int
    ) -> List[vr.VariableReference]:
        """Provides a list of variable references satisfying a certain type before a
        given position.

        If the position value is larger than the number of statements, only these
        statements will be considered.  Otherwise the first `position` statements of
        the test case will be considered.

        :param parameter_type: The type of the parameter we search references for
        :param position: The position in the statement list until we search
        :return: A list of variable references satisfying the parameter type
        """
        if not parameter_type:
            return []
        variables: List[vr.VariableReference] = []
        bound = min(len(self._statements), position)
        for i in range(bound):
            statement = self._statements[i]
            value = statement.return_value
            if value.variable_type == parameter_type:
                variables.append(value)

        return variables
