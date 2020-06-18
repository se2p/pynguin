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
from typing import List, Optional, Type

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcasevisitor as tcv
import pynguin.testcase.variable.variablereference as vr
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.utils import randomness
from pynguin.utils.atomicinteger import AtomicInteger
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.type_utils import is_assignable_to


# pylint: disable=too-many-public-methods
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

        Returns:
            The list of statements in this test case
        """
        return self._statements

    @abstractmethod
    def accept(self, visitor: tcv.TestCaseVisitor) -> None:
        """Handles a test visitor.

        Args:
            visitor: The test visitor to accept
        """

    @abstractmethod
    def add_statement(
        self, statement: stmt.Statement, position: int = -1
    ) -> vr.VariableReference:
        """Adds a new statement to the test case.

        The optional position parameter specifies the position.  If it is not given,
        the statement will be added to the end of the test case.

        Args:
            statement: The new statement
            position: The optional position where to put the statement

        Returns:  # noqa: DAR202
            The return value of the statement.  Notice that the test might
            choose to modify the statement you inserted.  You should use the returned
            variable reference and not use references.
        """

    @abstractmethod
    def add_statements(self, statements: List[stmt.Statement]) -> None:
        """Adds a list of statements to the end of the test case.

        Args:
            statements: The list of statements to add
        """

    @abstractmethod
    def append_test_case(self, test_case: TestCase) -> None:
        """Appends a test case to this test case.

        Args:
            test_case: The test case to append
        """

    @abstractmethod
    def remove(self, position: int) -> None:
        """Removes a statement a the given position

        Args:
            position: The position of the test case to be removed
        """

    @abstractmethod
    def chop(self, pos: int) -> None:
        """Remove all statements after a given position.

        Args:
            pos: The length of the test case after chopping
        """

    @abstractmethod
    def contains(self, statement: stmt.Statement) -> bool:
        """Determines whether or not the test case contains a specific statement.

        Args:
            statement: The statement to search in the test case

        Returns:
            Whether or not the test case contains the statement  # noqa: DAR202
        """

    @abstractmethod
    def get_statement(self, position: int) -> stmt.Statement:
        """Provides access to a statement at a given position.

        Args:
            position: The position of the statement in the test case

        Returns:
            The statement at the position  # noqa: DAR202
        """

    @abstractmethod
    def set_statement(
        self, statement: stmt.Statement, position: int
    ) -> vr.VariableReference:
        """Set new statement at position.

        Args:
            statement: the new statement
            position: the position for the new statement

        Returns:
            A variable reference to the statements return value  # noqa: DAR202
        """

    @abstractmethod
    def has_statement(self, position: int) -> bool:
        """Check if there is a statement at the given position.

        Args:
            position: The index of the statement

        Returns:
            Whether or not there is a statement at the given position  # noqa: DAR202
        """

    @abstractmethod
    def clone(self) -> TestCase:
        """Provides a deep copy of the test case.

        Returns:
            A deep copy of this test case  # noqa: DAR202
        """

    @abstractmethod
    def is_failing(self) -> bool:
        """Checks if the test case is a failing test or not

        Returns:
            Whether or not the test case is failing  # noqa: DAR202
        """

    @abstractmethod
    def set_failing(self) -> None:
        """Marks the test case as a failing test."""

    @abstractmethod
    def size(self) -> int:
        """Provides the number of statements in the test case.

        Returns:
            The number of statements in the test case  # noqa: DAR202
        """

    def get_objects(
        self, parameter_type: Optional[Type], position: int
    ) -> List[vr.VariableReference]:
        """Provides a list of variable references satisfying a certain type before a
        given position.

        If the position value is larger than the number of statements, only these
        statements will be considered.  Otherwise the first `position` statements of
        the test case will be considered.

        Args:
            parameter_type: The type of the parameter we search references for
            position: The position in the statement list until we search

        Returns:
            A list of variable references satisfying the parameter type
        """
        if not parameter_type:
            return []
        variables: List[vr.VariableReference] = []
        bound = min(len(self._statements), position)
        for i in range(bound):
            statement = self._statements[i]
            var = statement.return_value
            if not var.is_none_type() and is_assignable_to(
                var.variable_type, parameter_type
            ):
                variables.append(var)

        return variables

    def get_all_objects(self, position: int) -> List[vr.VariableReference]:
        """Get all objects that are defined up to the given position (exclusive).

        Args:
            position: the position

        Returns:
            A list of all objects defined up to the given positon
        """
        variables: List[vr.VariableReference] = []
        bound = min(len(self._statements), position)
        for i in range(bound):
            var = self.get_statement(i).return_value
            if not var.is_none_type():
                variables.append(var)
        return variables

    def get_random_object(
        self, parameter_type: Type, position: int
    ) -> vr.VariableReference:
        """Get a random object of the given type up to the given position (exclusive).

        Args:
            parameter_type: the parameter type
            position: the position

        Returns:
            A random object of given type up to the given position

        Raises:
            ConstructionFailedException: if no object could be found
        """
        variables = self.get_objects(parameter_type, position)
        if len(variables) == 0:
            raise ConstructionFailedException(
                f"Found no variables of type {parameter_type} at position {position}"
            )
        return randomness.choice(variables)

    @abstractmethod
    def mutate(self) -> None:
        """Mutate this test case."""

    @abstractmethod
    def has_changed(self) -> bool:
        """Has this test case changed since the last execution?

        Returns:  # noqa: DAR202
            Whether or not this test case changed since the last execution
        """

    @abstractmethod
    def set_changed(self, value: bool) -> None:
        """Mark this test case as changed.

        Args:
            value: the new change value
        """

    @abstractmethod
    def get_last_execution_result(self) -> Optional[ExecutionResult]:
        """Get the last execution result.

        Returns:
            The last execution result if any  # noqa: DAR202
        """

    @abstractmethod
    def set_last_execution_result(self, result: ExecutionResult) -> None:
        """Set the last execution result.

        Args:
            result: The last execution result
        """
