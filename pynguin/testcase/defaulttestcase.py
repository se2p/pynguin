#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a default implementation of a test case."""
from __future__ import annotations

import logging
from typing import Any, List, Set

import pynguin.assertion.assertion as ass
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.testcasevisitor as tcv
import pynguin.testcase.variable.variablereference as vr


# pylint:disable=too-many-public-methods
class DefaultTestCase(tc.TestCase):
    """A default implementation of a test case."""

    _logger = logging.getLogger(__name__)

    # pylint: disable=invalid-name
    def __init__(self) -> None:
        super().__init__()
        self._id = self._id_generator.inc()

    @property
    def id(self) -> int:
        """Get an unique ID representing this test case.

        Mainly useful for debugging.

        Returns:
            An unique ID representing this test case
        """
        return self._id

    def accept(self, visitor: tcv.TestCaseVisitor) -> None:
        visitor.visit_default_test_case(self)

    def add_statement(
        self, statement: stmt.Statement, position: int = -1
    ) -> vr.VariableReference:
        if position == -1:
            self._statements.append(statement)
        else:
            self._statements.insert(position, statement)
        return statement.return_value

    def add_statements(self, statements: List[stmt.Statement]) -> None:
        self._statements.extend(statements)

    def append_test_case(self, test_case: tc.TestCase) -> None:
        size = self.size()
        for statement in test_case.statements:
            self._statements.append(statement.clone(self, size))

    def remove(self, position: int) -> None:
        self._logger.debug("Removing statement at position %d", position)
        if position >= self.size():
            return
        del self._statements[position]

    def chop(self, pos: int) -> None:
        assert pos >= 0
        while len(self._statements) > pos + 1:
            del self._statements[-1]

    def contains(self, statement: stmt.Statement) -> bool:
        return statement in self._statements

    def get_statement(self, position: int) -> stmt.Statement:
        assert 0 <= position < len(self._statements)
        return self._statements[position]

    def set_statement(
        self, statement: stmt.Statement, position: int
    ) -> vr.VariableReference:
        assert 0 <= position < len(self._statements)
        self._statements[position] = statement
        return statement.return_value

    def has_statement(self, position: int) -> bool:
        return 0 <= position < len(self._statements)

    def clone(self) -> tc.TestCase:
        test_case = DefaultTestCase()
        for statement in self._statements:
            copy = statement.clone(test_case)
            test_case._statements.append(copy)
            copy.assertions = statement.copy_assertions(test_case, 0)
        test_case._id = self._id_generator.inc()
        return test_case

    def get_dependencies(self, var: vr.VariableReference) -> Set[vr.VariableReference]:
        dependencies = set()

        # TODO(fk) a variable will be a dependency of itself?!
        dependent_stmts = {self.get_statement(var.get_statement_position())}
        for idx in range(var.get_statement_position(), -1, -1):
            new_stmts = set()
            for statement in dependent_stmts:
                if statement.references(self.get_statement(idx).return_value):
                    new_stmts.add(self.get_statement(idx))
                    dependencies.add(self.get_statement(idx).return_value)
                    break
            dependent_stmts.update(new_stmts)

        return dependencies

    def get_assertions(self) -> List[ass.Assertion]:
        assertions: List[ass.Assertion] = []
        for statement in self._statements:
            assertions.extend(statement.assertions)
        return assertions

    def size_with_assertions(self) -> int:
        return self.size() + len(self.get_assertions())

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
