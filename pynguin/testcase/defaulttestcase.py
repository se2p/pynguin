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
from __future__ import annotations

import logging
from typing import Any, List, Optional

import pynguin.configuration as config
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.testcasevisitor as tcv
import pynguin.testcase.testfactory as tf
import pynguin.testcase.variable.variablereference as vr
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.utils import randomness


class DefaultTestCase(tc.TestCase):
    """A default implementation of a test case."""

    # pylint: disable=invalid-name
    def __init__(self, test_factory: Optional[tf.TestFactory] = None) -> None:
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._is_failing: bool = False
        self._id = self._id_generator.inc()
        self._changed = True
        self._test_factory = test_factory
        self._last_execution_result: Optional[ExecutionResult] = None

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
        self.set_changed(True)
        return statement.return_value

    def add_statements(self, statements: List[stmt.Statement]) -> None:
        self._statements.extend(statements)
        self.set_changed(True)

    def append_test_case(self, test_case: tc.TestCase) -> None:
        size = self.size()
        for statement in test_case.statements:
            self._statements.append(statement.clone(self, size))
        self.set_changed(True)

    def remove(self, position: int) -> None:
        self._logger.debug("Removing statement at position %d", position)
        if position >= self.size():
            return
        del self._statements[position]
        self.set_changed(True)

    def chop(self, pos: int) -> None:
        assert pos >= 0
        while len(self._statements) > pos + 1:
            del self._statements[-1]
            self.set_changed(True)

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
        self.set_changed(True)
        return statement.return_value

    def has_statement(self, position: int) -> bool:
        return 0 <= position < len(self._statements)

    def clone(self) -> tc.TestCase:
        test_case = DefaultTestCase()
        for statement in self._statements:
            test_case._statements.append(statement.clone(test_case))
        test_case._is_failing = self._is_failing
        test_case._id = self._id_generator.inc()
        test_case._test_factory = self._test_factory
        test_case._last_execution_result = self._last_execution_result
        test_case._changed = self._changed
        return test_case

    def is_failing(self) -> bool:
        return self._is_failing

    def set_failing(self) -> None:
        self._is_failing = True

    def size(self) -> int:
        return len(self._statements)

    def mutate(self) -> None:
        """Each statement is mutated with probability 1/l."""
        changed = False

        if (
            config.INSTANCE.chop_max_length
            and self.size() >= config.INSTANCE.chromosome_length
        ):
            last_mutatable_position = self._get_last_mutatable_statement()
            if last_mutatable_position is not None:
                self.chop(last_mutatable_position)
                changed = True

        if randomness.next_float() <= config.INSTANCE.test_delete_probability:
            if self._mutation_delete():
                changed = True

        if randomness.next_float() <= config.INSTANCE.test_change_probability:
            if self._mutation_change():
                changed = True

        if randomness.next_float() <= config.INSTANCE.test_insert_probability:
            if self._mutation_insert():
                changed = True

        if changed:
            self.set_changed(True)

    def _mutation_delete(self) -> bool:
        last_mutatable_statement = self._get_last_mutatable_statement()
        if last_mutatable_statement is None:
            return False

        changed = False
        p_per_statement = 1.0 / (last_mutatable_statement + 1)
        for idx in reversed(range(last_mutatable_statement + 1)):
            if idx >= self.size():
                continue
            if randomness.next_float() <= p_per_statement:
                changed |= self._delete_statement(idx)
        return changed

    def _delete_statement(self, idx: int) -> bool:
        assert self._test_factory, "Requires a test factory."
        modified = self._test_factory.delete_statement_gracefully(self, idx)
        return modified

    def _mutation_change(self) -> bool:
        last_mutatable_statement = self._get_last_mutatable_statement()
        if last_mutatable_statement is None:
            return False

        changed = False
        p_per_statement = 1.0 / (last_mutatable_statement + 1.0)
        position = 0
        while position <= last_mutatable_statement:
            if randomness.next_float() < p_per_statement:
                statement = self.get_statement(position)
                old_distance = statement.return_value.distance
                if statement.mutate():
                    changed = True
                else:
                    assert self._test_factory
                    if self._test_factory.change_random_call(self, statement):
                        changed = True
                statement.return_value.distance = old_distance
                position = statement.get_position()
            position += 1

        return changed

    def _mutation_insert(self) -> bool:
        """With exponentially decreasing probability, insert statements at
        random position.

        Returns:
            Whether or not the test case was changed
        """
        changed = False
        alpha = config.INSTANCE.statement_insertion_probability
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and self.size() < config.INSTANCE.chromosome_length
        ):
            assert self._test_factory
            max_position = self._get_last_mutatable_statement()
            if max_position is None:
                # No mutatable statement found, so start at the first position.
                max_position = 0
            else:
                # Also include the position after the last mutatable statement.
                max_position += 1

            position = self._test_factory.insert_random_statement(self, max_position)
            exponent += 1
            if 0 <= position < self.size():
                changed = True
        return changed

    def _get_last_mutatable_statement(self) -> Optional[int]:
        """Provides the index of the last mutatable statement.

        If there was an exception during the last execution, this includes all statement
        up to the one that caused the exception (included).

        Returns:
            The index of the last mutable statement, if any.
        """
        # We are empty, so there can't be a last mutatable statement.
        if self.size() == 0:
            return None

        result = self.get_last_execution_result()
        if result is not None and result.has_test_exceptions():
            position = result.get_first_position_of_thrown_exception()
            assert position is not None
            # The position might not be valid anymore.
            if position < self.size():
                return position
        # No exception, so the entire test case can be mutated.
        return self.size() - 1

    def has_changed(self) -> bool:
        return self._changed

    def set_changed(self, value: bool) -> None:
        self._changed = value

    def get_last_execution_result(self) -> Optional[ExecutionResult]:
        return self._last_execution_result

    def set_last_execution_result(self, result: ExecutionResult) -> None:
        self._last_execution_result = result

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
