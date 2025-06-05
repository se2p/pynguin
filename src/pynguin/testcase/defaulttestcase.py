#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a default implementation of a test case."""

from __future__ import annotations

import logging

from itertools import islice
from typing import TYPE_CHECKING

import pynguin.testcase.testcase as tc

from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.statement as stmt
    import pynguin.testcase.testcasevisitor as tcv
    import pynguin.testcase.variablereference as vr


class DefaultTestCase(tc.TestCase):  # noqa: PLR0904
    """A default implementation of a test case."""

    _logger = logging.getLogger(__name__)

    def accept(self, visitor: tcv.TestCaseVisitor) -> None:  # noqa: D102
        visitor.visit_default_test_case(self)

    def add_statement(  # noqa: D102
        self, statement: stmt.Statement, position: int = -1
    ) -> vr.VariableReference | None:
        if position == -1:
            self._statements.append(statement)
        else:
            self._statements.insert(position, statement)
        return statement.ret_val

    def add_variable_creating_statement(  # noqa: D102
        self, statement: stmt.VariableCreatingStatement, position: int = -1
    ) -> vr.VariableReference:
        if position == -1:
            self._statements.append(statement)
        else:
            self._statements.insert(position, statement)
        return statement.ret_val

    def add_statements(self, statements: list[stmt.Statement]) -> None:  # noqa: D102
        self._statements.extend(statements)

    def append_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        memo: dict[vr.VariableReference, vr.VariableReference] = {}
        for statement in test_case.statements:
            clone = statement.clone(self, memo)
            if statement.ret_val is not None:
                # If the original statement created a variable, then so does the clone
                # Thus we know that clone.ret_val is not None
                memo[statement.ret_val] = clone.ret_val  # type: ignore[assignment]
            self._statements.append(clone)

    def remove(self, position: int) -> None:  # noqa: D102
        self._logger.debug("Removing statement at position %d", position)
        if position >= self.size():
            return
        del self._statements[position]

    def remove_statement(self, statement: stmt.Statement) -> None:  # noqa: D102
        self._statements.remove(statement)

    def remove_with_forward_dependencies(self, position: int) -> list[int]:  # noqa: D102
        if position >= self.size():
            raise ValueError(
                f"Position {position} is out of bounds for test case of size {self.size()}."
            )
        statement = self.get_statement(position)
        return self.remove_statement_with_forward_dependencies(statement)

    def remove_statement_with_forward_dependencies(self, statement: stmt.Statement) -> list[int]:  # noqa: D102
        if not self.contains(statement):
            raise ValueError(f"Statement {statement} not found in test case.")
        ret_val = statement.ret_val
        forward_dependencies = []
        if ret_val is not None:
            forward_dependencies = list(self.get_forward_dependencies(ret_val))
        positions_to_remove = tc.TestCase.positions_to_remove(statement, forward_dependencies)
        for pos in positions_to_remove:
            self.remove(pos)
        return positions_to_remove

    def chop(self, pos: int) -> None:  # noqa: D102
        assert pos >= 0
        while len(self._statements) > pos + 1:
            del self._statements[-1]

    def contains(self, statement: stmt.Statement) -> bool:  # noqa: D102
        return statement in self._statements

    def get_statement(self, position: int) -> stmt.Statement:  # noqa: D102
        assert 0 <= position < len(self._statements)
        return self._statements[position]

    def set_statement(  # noqa: D102
        self, statement: stmt.Statement, position: int
    ) -> vr.VariableReference | None:
        assert 0 <= position < len(self._statements)
        self._statements[position] = statement
        return statement.ret_val

    def has_statement(self, position: int) -> bool:  # noqa: D102
        return 0 <= position < len(self._statements)

    def clone(self, limit: int | None = None) -> tc.TestCase:  # noqa: D102
        test_case = DefaultTestCase(self.test_cluster)
        memo: dict[vr.VariableReference, vr.VariableReference] = {}
        for statement in islice(self._statements, limit):
            copy = statement.clone(test_case, memo)
            if statement.ret_val is not None:
                # If the original statement created a variable, then so does the clone
                # Thus we know that clone.ret_val is not None
                memo[statement.ret_val] = copy.ret_val  # type: ignore[assignment]
            test_case._statements.append(copy)
            copy.assertions = statement.copy_assertions(memo)
        return test_case

    def get_dependencies(  # noqa: D102
        self, var: vr.VariableReference
    ) -> OrderedSet[vr.VariableReference]:
        dependencies: OrderedSet[vr.VariableReference] = OrderedSet()

        # TODO(fk) a variable will be a dependency of itself?!
        dependent_stmts = {self.get_statement(var.get_statement_position())}
        for idx in range(var.get_statement_position(), -1, -1):
            new_stmts: OrderedSet[stmt.Statement] = OrderedSet()
            for statement in dependent_stmts:
                if (
                    ret_val := self.get_statement(idx).ret_val
                ) is not None and statement.references(ret_val):
                    new_stmts.add(self.get_statement(idx))
                    dependencies.add(ret_val)
                    break
            dependent_stmts.update(new_stmts)

        return dependencies

    def get_forward_dependencies(  # noqa: D102
        self, var: vr.VariableReference
    ) -> OrderedSet[vr.VariableReference]:
        dependencies: OrderedSet[vr.VariableReference] = OrderedSet()

        # Start with the variable itself
        dependencies.add(var)

        # Iterate forward from the variable's statement position
        for idx in range(var.get_statement_position() + 1, self.size()):
            statement = self.get_statement(idx)
            # Check if this statement references any of the dependencies we've found so far
            if (
                any(statement.references(dep) for dep in dependencies)
                and statement.ret_val is not None
            ):
                dependencies.add(statement.ret_val)

        # Remove the original variable from the dependencies
        dependencies.remove(var)

        return dependencies

    def get_assertions(self) -> list[ass.Assertion]:  # noqa: D102
        assertions: list[ass.Assertion] = []
        for statement in self._statements:
            assertions.extend(statement.assertions)
        return assertions

    def size_with_assertions(self) -> int:  # noqa: D102
        return self.size() + len(self.get_assertions())

    def size(self) -> int:  # noqa: D102
        return len(self._statements)

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, DefaultTestCase):
            return False

        if not self._statements:
            if other._statements:
                return False
        else:
            if len(self._statements) != len(other._statements):
                return False
            memo: dict[vr.VariableReference, vr.VariableReference] = {}
            for left, right in zip(self._statements, other._statements, strict=True):
                if ((lret := left.ret_val) is None) ^ ((rret := right.ret_val) is None):
                    # One is None but the other isn't, i.e., one creates a variable
                    # but the other doesn't -> they are different.
                    return False
                if lret is not None:
                    # lret is not None, so rret is also not None, otherwise we would be
                    # in the above case.
                    memo[lret] = rret  # type: ignore[assignment]
                if not left.structural_eq(right, memo):
                    return False
        return True

    def __hash__(self) -> int:
        memo: dict[vr.VariableReference, int] = {
            statement.ret_val: idx
            for idx, statement in enumerate(self._statements)
            if statement.ret_val is not None
        }
        return hash(tuple(s.structural_hash(memo) for s in self._statements))
