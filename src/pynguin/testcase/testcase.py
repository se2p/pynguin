#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an implementation for a test case."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException


if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.statement as stmt
    import pynguin.testcase.testcasevisitor as tcv
    import pynguin.testcase.variablereference as vr

    from pynguin.analyses.module import TestCluster
    from pynguin.analyses.typesystem import ProperType
    from pynguin.utils.orderedset import OrderedSet


class TestCase(ABC):  # noqa: PLR0904
    """An abstract base implementation for a test case.

    Serves as an interface for test-case implementations
    """

    def __init__(self, test_cluster: TestCluster) -> None:
        """Create a new test case.

        Args:
            test_cluster: The used test cluster. We need this cluster to have access
                to the typesystem, in order to search through the statements of this
                test case which provide values of certain (sub)types.
        """
        self._statements: list[stmt.Statement] = []
        self.test_cluster: TestCluster = test_cluster

    @property
    def statements(self) -> list[stmt.Statement]:
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
    ) -> vr.VariableReference | None:
        """Adds a new statement to the test case.

        The optional position parameter specifies the position.  If it is not given,
        the statement will be added to the end of the test case.

        Args:
            statement: The new statement
            position: The optional position where to put the statement

        Returns:  # noqa: DAR202
            The return value of the statement.  Notice that the test might
            choose to modify the statement you inserted.  You should use the returned
            variable reference and not use references. Can be None, if this statement
            does not create a variable.
        """

    @abstractmethod
    def add_variable_creating_statement(
        self, statement: stmt.VariableCreatingStatement, position: int = -1
    ) -> vr.VariableReference:
        """Overloaded version of add_statement that adds a statement.

        Args:
            statement: The new statement
            position: The optional position where to put the statement

        Returns:  # noqa: DAR202
            The return value of the statement.  Notice that the test might
            choose to modify the statement you inserted.  You should use the returned
            variable reference and not use references.
        """

    @abstractmethod
    def add_statements(self, statements: list[stmt.Statement]) -> None:
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
        """Removes a statement a the given position.

        Args:
            position: The position of the test case to be removed
        """

    @abstractmethod
    def remove_statement(self, statement: stmt.Statement) -> None:
        """Remove the given statement from this test case.

        Args:
            statement: The statement to remove.
        """

    @abstractmethod
    def remove_with_forward_dependencies(self, position: int) -> list[int]:
        """Removes a statement at the given position along with all its forward dependencies.

        Args:
            position: The position of the statement to remove

        Returns:
            A list of positions of statements that have been deleted

        Raises:
            ValueError: If the position is out of bounds for this test case
        """

    @abstractmethod
    def remove_statement_with_forward_dependencies(self, statement: stmt.Statement) -> list[int]:
        """Removes the given statement along with all its forward dependencies.

        Args:
            statement: The statement to remove

        Returns:
            A list of positions of statements that have been deleted

        Raises:
            ValueError: If the statement is not contained in the test case
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
    ) -> vr.VariableReference | None:
        """Set new statement at position.

        Args:
            statement: the new statement
            position: the position for the new statement

        Returns:
            A variable reference to the statements return value, if any  # noqa: DAR202
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
    def clone(self, limit: int | None = None) -> TestCase:
        """Provides a deep copy of the test case.

        Args:
            limit: Clone this test case only up to the given number of statements.

        Returns:
            A deep copy of this test case  # noqa: DAR202
        """

    @abstractmethod
    def size(self) -> int:
        """Provides the number of statements in the test case.

        Returns:
            The number of statements in the test case  # noqa: DAR202
        """

    @abstractmethod
    def size_with_assertions(self) -> int:
        """Provides the number of statements and assertions in the test case.

        Returns:
            The number of statements and assertions in the test case # noqa: DAR202
        """

    @abstractmethod
    def get_assertions(self) -> list[ass.Assertion]:
        """Get all assertions that exist for this test case."""

    @abstractmethod
    def get_dependencies(self, var: vr.VariableReference) -> OrderedSet[vr.VariableReference]:
        """Provides all variables on which var depends.

        Args:
            var: the variable whose dependencies we are looking for.

        Returns:
            a set of variables on which var depends on. # noqa: DAR202
        """

    @abstractmethod
    def get_forward_dependencies(
        self, var: vr.VariableReference
    ) -> OrderedSet[vr.VariableReference]:
        """Provides all variables that depend on var.

        Args:
            var: the variable for which we look for all dependent statements of

        Returns:
            a set of variables that depend on var. # noqa: DAR202
        """

    def get_objects(self, parameter_type: ProperType, position: int) -> list[vr.VariableReference]:
        """Provides a list of variable references satisfying a certain type.

        If the position value is larger than the number of statements, only these
        statements will be considered.  Otherwise, the first `position` statements of
        the test case will be considered.

        If the type for which we search is not specified, all objects up to the given
        position are returned.

        Args:
            parameter_type: The type of the parameter we search references for
            position: The position in the statement list until we search

        Returns:
            A list of variable references satisfying the parameter type
        """
        variables: list[vr.VariableReference] = []
        bound = min(len(self._statements), position)
        for i in range(bound):
            statement = self._statements[i]
            var = statement.ret_val
            if var is None:
                continue
            if self.test_cluster.type_system.is_maybe_subtype(var.type, parameter_type):
                variables.append(var)

        return variables

    def get_all_objects(self, position: int) -> list[vr.VariableReference]:
        """Get all objects that are defined up to the given position (exclusive).

        Args:
            position: the position

        Returns:
            A list of all objects defined up to the given position
        """
        variables: list[vr.VariableReference] = []
        bound = min(len(self._statements), position)
        for i in range(bound):
            var = self.get_statement(i).ret_val
            if var is None:
                continue
            if not var.is_none_type():
                variables.append(var)
        return variables

    def get_random_object(self, parameter_type: ProperType, position: int) -> vr.VariableReference:
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

    @staticmethod
    def positions_to_remove(
        statement: stmt.Statement, dependencies: list[vr.VariableReference]
    ) -> list[int]:
        """Get the positions to remove and its forward dependencies in reverse order.

        This is done to avoid index issues when removing multiple statements.

        Args:
            statement: The statement to remove
            dependencies: The forward dependencies of the statement

        Returns:
            A list of positions to remove
        """
        positions = {dep.get_statement_position() for dep in dependencies}
        positions.add(statement.get_position())
        return sorted(positions, reverse=True)
