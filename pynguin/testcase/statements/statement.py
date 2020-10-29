#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a base implementation of a statement representation."""
# pylint: disable=cyclic-import
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Optional, Set

import pynguin.assertion.assertion as ass
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class Statement(metaclass=ABCMeta):
    """An abstract base class of a statement representation."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self, test_case: tc.TestCase, return_value: vr.VariableReference
    ) -> None:
        self._test_case = test_case
        self._return_value = return_value
        self._assertions: Set[ass.Assertion] = set()

    @property
    def return_value(self) -> vr.VariableReference:
        """Provides the return value of this statement.

        Returns:
            The return value of the statement execution
        """
        return self._return_value

    @return_value.setter
    def return_value(self, reference: vr.VariableReference) -> None:
        """Updates the return value of this statement.

        Args:
            reference: The new return value
        """
        self._return_value = reference

    @property
    def test_case(self) -> tc.TestCase:
        """Provides the test case in which this statement is used.

        Returns:
            The containing test case
        """
        return self._test_case

    @abstractmethod
    def clone(self, test_case: tc.TestCase, offset: int = 0) -> Statement:
        """Provides a deep clone of this statement.

        Args:
            test_case: the new test case in which the clone will be used.
            offset: Offset when cloning into a non empty test case.

        Returns:
            A deep clone of this statement  # noqa: DAR202
        """

    @abstractmethod
    def accept(self, visitor: sv.StatementVisitor) -> None:
        """Accepts a visitor to visit this statement.

        Args:
            visitor: the statement visitor
        """

    @abstractmethod
    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        """Provides the accessible which is used in this statement.

        Returns:
            The accessible used in the statement  # noqa: DAR202
        """

    @abstractmethod
    def mutate(self) -> bool:
        """Mutate this statement.

        Returns:
            True, if a mutation happened.  # noqa: DAR202
        """

    @abstractmethod
    def get_variable_references(self) -> Set[vr.VariableReference]:
        """Get all references that are used in this statement.

        Including return values.

        Returns:
            A set of references that are used in this statements  # noqa: DAR202
        """

    def references(self, var: vr.VariableReference) -> bool:
        """Check if this statement makes use of the given variable.

        Args:
            var: the given variable

        Returns:
            Whether or not this statement makes use of the given variable
        """
        return var in self.get_variable_references()

    @abstractmethod
    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        """Replace the old variable with the new variable.

        Args:
            old: the old variable
            new: the new variable
        """

    def get_position(self) -> int:
        """Provides the position of this statement in the test case.

        Returns:
            The position of this statement
        """
        return self._return_value.get_statement_position()

    def add_assertion(self, assertion: ass.Assertion) -> None:
        """Add the given assertion to this statement."""
        self._assertions.add(assertion)

    def copy_assertions(
        self, new_test_case: tc.TestCase, offset: int
    ) -> Set[ass.Assertion]:
        """Returns a copy of the assertions of this statement."""
        copy = set()
        for assertion in self._assertions:
            copy.add(assertion.clone(new_test_case, offset))
        return copy

    @property
    def assertions(self) -> Set[ass.Assertion]:
        """Provides the assertions of this statement, which are expected
        to hold after the execution of this statement."""
        return self._assertions

    @assertions.setter
    def assertions(self, assertions: Set[ass.Assertion]) -> None:
        self._assertions = assertions

    def __eq__(self, other: Any) -> bool:
        raise NotImplementedError("You need to override __eq__ for your statement type")

    def __hash__(self) -> int:
        raise NotImplementedError(
            "You need to override __hash__ for your statement type"
        )
