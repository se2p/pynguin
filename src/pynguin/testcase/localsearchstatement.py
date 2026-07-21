#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies for the libcst test-case representation.

A statement is represented as an immutable CST node wrapped in
:class:`~pynguin.testcase.testcase.Statement`, so every mutation here builds a
fresh CST node and replaces the statement via
:meth:`~pynguin.testcase.testcase.TestCase.replace_statement`.

The following statement kinds are not generated, so their strategies are absent:

* ``ComplexLocalSearch`` -- complex-number primitives are not generated.
* ``ClassLocalSearch`` -- class-object primitives are not generated.
* ``FieldStatementLocalSearch`` -- field-access statements do not exist.

Collections are literal-only (no reference-carrying elements), so the collection
strategies mutate element literals in place via
:func:`pynguin.testcase.literalgen.mutate_literal` instead of picking existing
in-scope variables.

Parametrized-statement search (calls) is restricted to the public
:class:`~pynguin.testcase.testfactory.TestFactory` API (``change_random_call``,
``mutate_call``, ``insert_random_statement``) rather than the finer-grained
single-argument replacement the original implementation used.
"""

from __future__ import annotations

import abc
import enum
import logging
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast

import libcst as cst

import pynguin.configuration as config
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.statistics.stats as stat
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.testcase import literalgen
from pynguin.testcase.localsearchobjective import LocalSearchImprovement as LS_Imp
from pynguin.testcase.testcase import Statement
from pynguin.utils import randomness
from pynguin.utils.naming import get_module_alias
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.testcase.execution import ExecutionResult
    from pynguin.testcase.localsearchobjective import LocalSearchObjective
    from pynguin.testcase.localsearchtimer import LocalSearchTimer
    from pynguin.testcase.testcase import TestCase
    from pynguin.testcase.testfactory import TestFactory

_LOGGER = logging.getLogger(__name__)

# Local search never has access to the seeded constant pool (that lives behind
# TestFactory's private ``_constant_provider``), so randomisation during local
# search always uses an unseeded provider. This only affects exploration
# quality, not correctness.
_FALLBACK_CONSTANT_PROVIDER = EmptyConstantProvider()

_PRIMITIVE_TYPES = (bool, int, float, str, bytes)
_COLLECTION_TYPES = (list, set, tuple, dict)


# ---------------------------------------------------------------------------
# Value-access layer over CST literal statements
# ---------------------------------------------------------------------------


def _rhs_expression(stmt: Statement) -> cst.BaseExpression | None:
    """Extract the RHS expression of a simple ``var = <expr>`` statement.

    Args:
        stmt: The statement to inspect.

    Returns:
        The RHS expression, or ``None`` if ``stmt`` is not a simple assignment.
    """
    if not isinstance(stmt.node, cst.SimpleStatementLine):
        return None
    body = stmt.node.body
    if not body or not isinstance(body[0], cst.Assign) or len(body[0].targets) != 1:
        return None
    return body[0].value


def _replace_rhs(test_case: TestCase, position: int, new_expr: cst.BaseExpression) -> bool:
    """Replace the RHS of the assignment at *position*, keeping variable/type/assertions.

    Args:
        test_case: The test case to modify.
        position: The index of the statement to modify.
        new_expr: The new RHS expression.

    Returns:
        True if the replacement succeeded (the statement is a bound assignment).
    """
    stmt = test_case.get_statement(position)
    if stmt.bound_variable is None:
        return False
    new_node = cst.SimpleStatementLine(
        body=[
            cst.Assign(
                targets=[cst.AssignTarget(target=cst.Name(stmt.bound_variable))],
                value=new_expr,
            )
        ]
    )
    test_case.replace_statement(
        position,
        Statement(
            node=new_node,
            bound_variable=stmt.bound_variable,
            bound_type=stmt.bound_type,
            assertions=list(stmt.assertions),
            accessible=None,
            local_search_applied=stmt.local_search_applied,
        ),
    )
    return True


def get_literal_value(stmt: Statement, raw: type) -> object | None:
    """Read the current literal value of a statement, if any.

    Args:
        stmt: The statement to read.
        raw: The expected Python type.

    Returns:
        The parsed value, or ``None`` if the RHS is not a parseable literal.
    """
    expr = _rhs_expression(stmt)
    if expr is None:
        return None
    return literalgen.parse_literal(expr, raw)


def set_literal_value(test_case: TestCase, position: int, value: object) -> bool:
    """Overwrite the literal value of the statement at *position*.

    Args:
        test_case: The test case to modify.
        position: The index of the statement to modify.
        value: The new literal value.

    Returns:
        True if the value was written.
    """
    return _replace_rhs(test_case, position, literalgen.literal_to_cst(value))


def randomize_literal_value(test_case: TestCase, position: int) -> bool:
    """Overwrite the statement's value with a freshly generated literal of its type.

    Used to escape a local optimum before a same-datatype search is retried on
    the same statement.

    Args:
        test_case: The test case to modify.
        position: The index of the statement to randomize.

    Returns:
        True if the value was randomized.
    """
    stmt = test_case.get_statement(position)
    if stmt.bound_type is None:
        return False
    new_expr = literalgen.generate_literal(stmt.bound_type, _FALLBACK_CONSTANT_PROVIDER)
    return _replace_rhs(test_case, position, new_expr)


# ---------------------------------------------------------------------------
# Strategy base classes
# ---------------------------------------------------------------------------


class StatementLocalSearch(abc.ABC):
    """An abstract local search strategy for statements."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory,
        timer: LocalSearchTimer,
    ):
        """Initializes the local search strategy for a specific statement.

        Args:
            chromosome: The test case chromosome containing the statement.
            position: The position of the statement in the test case.
            objective: The objective to check for improvements.
            factory: The factory to create new statements.
            timer: The timer which limits the local search.
        """
        self._chromosome = chromosome
        self._objective = objective
        self._position = position
        self._factory = factory
        self._timer = timer
        self._old_statement: Statement | None = None
        self._last_execution_result: ExecutionResult | None = None
        self._old_changed: bool = False

    @abstractmethod
    def search(self) -> bool:
        """Applies local search to a specific statement of the chromosome.

        Returns:
            True, if the local search was successful and improved the fitness.
        """

    def _statement(self) -> Statement:
        return self._chromosome.test_case.get_statement(self._position)

    def _snapshot(self) -> None:
        """Take a transactional snapshot of the current statement/execution state."""
        self._old_statement = self._statement()
        self._last_execution_result = self._chromosome.get_last_execution_result()
        self._old_changed = self._chromosome.changed

    def _restore(self) -> None:
        """Restore the statement/execution state from the last snapshot."""
        assert self._old_statement is not None, "_restore() called before _snapshot()"
        self._chromosome.test_case.replace_statement(self._position, self._old_statement)
        if self._last_execution_result is not None:
            self._chromosome.set_last_execution_result(self._last_execution_result)
        self._chromosome.changed = self._old_changed


class PrimitiveLocalSearch(StatementLocalSearch, ABC):
    """Abstract local search strategy for primitive-valued statements."""


class BooleanLocalSearch(PrimitiveLocalSearch):
    """A local search strategy for booleans."""

    def search(self) -> bool:  # noqa: D102
        current = get_literal_value(self._statement(), bool)
        if current is None:
            return False
        self._snapshot()
        set_literal_value(self._chromosome.test_case, self._position, not current)
        if not self._objective.has_improved(self._chromosome):
            self._restore()
            return False
        return True


class NumericalLocalSearch(PrimitiveLocalSearch, ABC):
    """An abstract AVM-style local search strategy for numerical primitives."""

    _raw: type

    def iterate(self, delta: float, increasing_factor: float) -> bool:
        """Applies increasing deltas to the value until it no longer improves.

        Args:
            delta: The initial delta to apply.
            increasing_factor: The factor the delta is multiplied by each round.

        Returns:
            True if at least one iteration improved the fitness.
        """
        current = get_literal_value(self._statement(), self._raw)
        if current is None:
            return False
        improved = False
        self._snapshot()
        current += delta
        set_literal_value(self._chromosome.test_case, self._position, current)
        while self._objective.has_improved(self._chromosome) and not self._timer.limit_reached():
            self._snapshot()
            improved = True
            delta *= increasing_factor
            current += delta
            set_literal_value(self._chromosome.test_case, self._position, current)
        self._restore()
        return improved

    def iterate_directions(self, delta: float, factor: float) -> bool:
        """Iterates positive and negative deltas until neither improves anymore.

        Args:
            delta: The initial delta to apply (used for both directions).
            factor: The factor the delta is multiplied by each round.

        Returns:
            True if at least one iteration improved the fitness.
        """
        done = False
        improved = False
        while not done and not self._timer.limit_reached():
            done = True
            if self.iterate(delta, factor) or self.iterate(-delta, factor):
                done = False
                improved = True
        if not improved:
            self._chromosome.changed = False
        return improved


class IntegerLocalSearch(NumericalLocalSearch):
    """A local search strategy for integers."""

    _raw = int

    def search(self) -> bool:  # noqa: D102
        increasing_factor = config.configuration.local_search.ls_int_delta_increasing_factor
        return self.iterate_directions(1, increasing_factor)


class FloatLocalSearch(NumericalLocalSearch):
    """A local search strategy for floats."""

    _raw = float

    def search(self) -> bool:  # noqa: D102
        improved = False
        increasing_factor = config.configuration.local_search.ls_int_delta_increasing_factor
        if self.iterate_directions(1, increasing_factor):
            improved = True

        precision = 1
        while precision <= sys.float_info.dig and not self._timer.limit_reached():
            value = get_literal_value(self._statement(), float)
            if value is None:
                break
            self._snapshot()
            set_literal_value(self._chromosome.test_case, self._position, round(value, precision))
            if self._objective.has_changed(self._chromosome) == LS_Imp.DETERIORATION:
                self._restore()
            if self.iterate_directions(10.0 ** (-precision), increasing_factor):
                improved = True
            precision += 1
        return improved


class EnumLocalSearch(StatementLocalSearch):
    """A local search strategy for enum-member accesses."""

    def search(self) -> bool:  # noqa: D102
        stmt = self._statement()
        accessible = stmt.accessible
        if not isinstance(accessible, gao.GenericEnum) or stmt.bound_variable is None:
            return False
        names = list(accessible.names)
        if not names:
            return False
        current = self._current_member(stmt)
        self._snapshot()
        for name in names:
            if self._timer.limit_reached():
                return False
            if name == current:
                continue
            self._set_member(stmt, name)
            if self._objective.has_improved(self._chromosome):
                return True
            self._restore()
        return False

    @staticmethod
    def _current_member(stmt: Statement) -> str | None:
        expr = _rhs_expression(stmt)
        if isinstance(expr, cst.Attribute) and isinstance(expr.attr, cst.Name):
            return expr.attr.value
        return None

    def _set_member(self, stmt: Statement, member_name: str) -> None:
        assert isinstance(stmt.accessible, gao.GenericEnum)
        owner = stmt.accessible.owner
        enum_name = owner.name if owner is not None else "Enum"
        module_alias = get_module_alias(config.configuration.module_name)
        assert stmt.bound_variable is not None
        new_node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(stmt.bound_variable))],
                    value=cst.Attribute(
                        value=cst.Attribute(value=cst.Name(module_alias), attr=cst.Name(enum_name)),
                        attr=cst.Name(member_name),
                    ),
                )
            ]
        )
        self._chromosome.test_case.replace_statement(
            self._position,
            Statement(
                node=new_node,
                bound_variable=stmt.bound_variable,
                bound_type=stmt.bound_type,
                assertions=list(stmt.assertions),
                accessible=stmt.accessible,
                local_search_applied=stmt.local_search_applied,
            ),
        )


class StringLocalSearch(PrimitiveLocalSearch):
    """A local search strategy for strings."""

    def search(self) -> bool:  # noqa: D102
        improved = False
        if self.apply_random_mutations():
            if self.remove_chars():
                improved = True
            if self.replace_chars():
                improved = True
            if self.add_chars():
                improved = True
        return improved

    def apply_random_mutations(self) -> bool:
        """Probes the fitness landscape with random values before committing to a search.

        Returns:
            True if any of the random probes changed the fitness in any way.
        """
        count = config.configuration.local_search.ls_string_random_mutation_count
        self._snapshot()
        while count > 0:
            randomize_literal_value(self._chromosome.test_case, self._position)
            improvement = self._objective.has_changed(self._chromosome)
            if improvement in {LS_Imp.DETERIORATION, LS_Imp.NONE}:
                self._restore()
            if improvement in {LS_Imp.DETERIORATION, LS_Imp.IMPROVEMENT}:
                stat.add_to_runtime_variable(
                    RuntimeVariable.LocalSearchSuccessfulExploratoryMoves, 1
                )
                return True
            count -= 1
        stat.add_to_runtime_variable(RuntimeVariable.LocalSearchUnsuccessfulExploratoryMoves, 1)
        return False

    def remove_chars(self) -> bool:
        """Tries removing each character of the string, keeping the removal if it helps.

        Returns:
            True if any removal improved the fitness.
        """
        value = get_literal_value(self._statement(), str)
        if value is None:
            return False
        self._snapshot()
        improved = False
        for i in range(len(value) - 1, -1, -1):
            if self._timer.limit_reached():
                return improved
            value = value[:i] + value[i + 1 :]
            set_literal_value(self._chromosome.test_case, self._position, value)
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._snapshot()
            else:
                self._restore()
                value = cast("str", get_literal_value(self._statement(), str))
        return improved

    def replace_chars(self) -> bool:
        """Tries an AVM search over every character's code point.

        Returns:
            True if any replacement improved the fitness.
        """
        value = get_literal_value(self._statement(), str)
        if not value:
            return False
        old_changed = self._chromosome.changed
        improved = False
        self._snapshot()
        for i in range(len(value) - 1, -1, -1):
            finished = False
            while not finished and not self._timer.limit_reached():
                finished = True
                if self.iterate_string(i, 1):
                    finished = False
                    improved = True
                if self.iterate_string(i, -1):
                    finished = False
                    improved = True
        if not improved:
            self._chromosome.changed = old_changed
        return improved

    def add_chars(self) -> bool:
        """Tries inserting a character at every position, AVM-searching the best one.

        Returns:
            True if any insertion improved the fitness.
        """
        value = get_literal_value(self._statement(), str)
        if value is None:
            return False
        self._snapshot()
        i = 0
        improved = False
        while i <= len(value) and not self._timer.limit_reached():
            candidate = value[:i] + "a" + value[i:]
            set_literal_value(self._chromosome.test_case, self._position, candidate)
            if self._objective.has_improved(self._chromosome):
                improved = True
                value = candidate
                self._snapshot()
                finished = False
                while not finished and not self._timer.limit_reached():
                    finished = True
                    if self.iterate_string(i, 1):
                        finished = False
                    if self.iterate_string(i, -1):
                        finished = False
                value = cast("str", get_literal_value(self._statement(), str))
            else:
                self._restore()
            i += 1
        return improved

    def iterate_string(self, char_position: int, delta: int) -> bool:
        """AVM-searches the code point of a single character in one direction.

        Args:
            char_position: The index of the character to mutate.
            delta: The initial code-point delta (positive or negative).

        Returns:
            True if at least one iteration improved the fitness.
        """
        value = get_literal_value(self._statement(), str)
        if value is None or not (0 <= ord(value[char_position]) + delta <= sys.maxunicode):
            return False
        self._snapshot()
        improved = False
        candidate = self._replace_single_char(value, char_position, delta)
        set_literal_value(self._chromosome.test_case, self._position, candidate)
        while self._objective.has_improved(self._chromosome):
            improved = True
            self._chromosome.changed = True
            self._snapshot()
            if self._timer.limit_reached():
                break
            delta *= config.configuration.local_search.ls_int_delta_increasing_factor
            if not (0 <= ord(candidate[char_position]) + delta <= sys.maxunicode):
                return improved
            candidate = self._replace_single_char(candidate, char_position, delta)
            set_literal_value(self._chromosome.test_case, self._position, candidate)
        self._restore()
        return improved

    @staticmethod
    def _replace_single_char(value: str, char_position: int, delta: float) -> str:
        new_char = chr(int(ord(value[char_position]) + delta))
        return value[:char_position] + new_char + value[char_position + 1 :]


class BytesLocalSearch(PrimitiveLocalSearch):
    """A local search strategy for bytes."""

    def search(self) -> bool:  # noqa: D102
        improved = False
        if self._apply_random_mutations():
            if self.remove_values():
                improved = True
            if self.replace_values():
                improved = True
            if self.add_values():
                improved = True
        return improved

    def _apply_random_mutations(self) -> bool:
        count = config.configuration.local_search.ls_string_random_mutation_count
        self._snapshot()
        while count > 0:
            randomize_literal_value(self._chromosome.test_case, self._position)
            changed = self._objective.has_changed(self._chromosome)
            if changed in {LS_Imp.DETERIORATION, LS_Imp.NONE}:
                self._restore()
            if changed in {LS_Imp.DETERIORATION, LS_Imp.IMPROVEMENT}:
                stat.add_to_runtime_variable(
                    RuntimeVariable.LocalSearchSuccessfulExploratoryMoves, 1
                )
                return True
            count -= 1
        stat.add_to_runtime_variable(RuntimeVariable.LocalSearchUnsuccessfulExploratoryMoves, 1)
        return False

    def add_values(self) -> bool:
        """Tries inserting a byte at every position, AVM-searching the best one.

        Returns:
            True if any insertion improved the fitness.
        """
        value = get_literal_value(self._statement(), bytes)
        if value is None:
            return False
        self._snapshot()
        i = 0
        improved = False
        while i <= len(value) and not self._timer.limit_reached():
            candidate = value[:i] + bytes([97]) + value[i:]
            set_literal_value(self._chromosome.test_case, self._position, candidate)
            if self._objective.has_improved(self._chromosome):
                improved = True
                value = candidate
                self._snapshot()
                finished = False
                while not finished and not self._timer.limit_reached():
                    finished = True
                    if self._iterate_bytes(i, 1):
                        finished = False
                    if self._iterate_bytes(i, -1):
                        finished = False
                value = cast("bytes", get_literal_value(self._statement(), bytes))
            else:
                self._restore()
            i += 1
        return improved

    def replace_values(self) -> bool:
        """Tries an AVM search over every byte value.

        Returns:
            True if any replacement improved the fitness.
        """
        value = get_literal_value(self._statement(), bytes)
        if not value:
            return False
        old_changed = self._chromosome.changed
        improved = False
        self._snapshot()
        for i in range(len(value) - 1, -1, -1):
            finished = False
            while not finished and not self._timer.limit_reached():
                finished = True
                if self._iterate_bytes(i, 1):
                    finished = False
                    improved = True
                if self._iterate_bytes(i, -1):
                    finished = False
                    improved = True
        if not improved:
            self._chromosome.changed = old_changed
        return improved

    def remove_values(self) -> bool:
        """Tries removing each byte, keeping the removal if it helps.

        Returns:
            True if any removal improved the fitness.
        """
        value = get_literal_value(self._statement(), bytes)
        if value is None:
            return False
        self._snapshot()
        improved = False
        for i in range(len(value) - 1, -1, -1):
            if self._timer.limit_reached():
                return improved
            value = value[:i] + value[i + 1 :]
            set_literal_value(self._chromosome.test_case, self._position, value)
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._snapshot()
            else:
                self._restore()
                value = cast("bytes", get_literal_value(self._statement(), bytes))
        return improved

    def _iterate_bytes(self, pos: int, delta: int) -> bool:
        value = get_literal_value(self._statement(), bytes)
        if value is None or value[pos] + delta not in range(256):
            return False
        self._snapshot()
        candidate = value[:pos] + bytes([value[pos] + delta]) + value[pos + 1 :]
        set_literal_value(self._chromosome.test_case, self._position, candidate)
        improved = False
        while self._objective.has_improved(self._chromosome) and not self._timer.limit_reached():
            improved = True
            self._chromosome.changed = True
            self._snapshot()
            delta *= config.configuration.local_search.ls_int_delta_increasing_factor
            if candidate[pos] + delta not in range(256):
                return improved
            candidate = candidate[:pos] + bytes([candidate[pos] + delta]) + candidate[pos + 1 :]
            set_literal_value(self._chromosome.test_case, self._position, candidate)
        self._restore()
        return improved


class CollectionLocalSearch(StatementLocalSearch):
    """A local search strategy for literal-only list/set/tuple/dict statements.

    Collections carry no variable references, so, unlike the original per-element
    remove/replace/add strategies, this repeatedly applies
    :func:`pynguin.testcase.literalgen.mutate_literal` (which itself
    adds/removes a random element) and keeps the mutation whenever it improves fitness,
    an AVM-style hill climb bounded by ``ls_dict_max_insertions`` consecutive failures.
    """

    def search(self) -> bool:  # noqa: D102
        stmt = self._statement()
        if stmt.bound_type not in _COLLECTION_TYPES:
            return False
        improved = False
        failures = 0
        max_failures = config.configuration.local_search.ls_dict_max_insertions
        self._snapshot()
        while failures < max_failures and not self._timer.limit_reached():
            expr = _rhs_expression(self._statement())
            if expr is None:
                break
            new_expr = literalgen.mutate_literal(expr, stmt.bound_type, _FALLBACK_CONSTANT_PROVIDER)
            _replace_rhs(self._chromosome.test_case, self._position, new_expr)
            if self._objective.has_improved(self._chromosome):
                improved = True
                failures = 0
                self._snapshot()
            else:
                self._restore()
                failures += 1
        return improved


class _ParametrizedOp(enum.Enum):
    """The different operations for parametrized-statement local search."""

    REPLACE = 0
    RANDOM_CALL = 1
    PARAMETER = 2


class ParametrizedStatementLocalSearch(StatementLocalSearch):
    """A local search strategy for calls (constructor/method/function statements).

    Restricted to :class:`~pynguin.testcase.testfactory.TestFactory`'s public API:
    ``REPLACE`` picks a different callable of the same return type
    (``change_random_call``), ``PARAMETER`` regenerates all argument values
    (``mutate_call`` -- coarser than the original single-argument replacement, see
    module docstring), and ``RANDOM_CALL`` inserts an unrelated random statement after
    this one (``insert_random_statement``).
    """

    def search(self) -> bool:  # noqa: D102
        stmt = self._statement()
        if not isinstance(stmt.accessible, gao.GenericCallableAccessibleObject):
            return False

        max_mutations = (
            config.configuration.local_search.ls_random_parametrized_statement_call_count
        )
        mutations = 0
        total_iterations = 0
        improved = False
        last_execution_result = self._chromosome.get_last_execution_result()
        old_test_case = self._chromosome.test_case.clone()

        while not self._timer.limit_reached() and mutations < max_mutations:
            total_iterations += 1
            op = randomness.choice(list(_ParametrizedOp))
            old_size = self._chromosome.test_case.size()
            changed = self._apply(op)

            if changed and self._objective.has_improved(self._chromosome):
                improved = True
                last_execution_result = self._chromosome.get_last_execution_result()
                old_test_case = self._chromosome.test_case.clone()
                mutations = 0
                self._position += self._chromosome.test_case.size() - old_size
            else:
                self._chromosome.test_case = old_test_case.clone()
                if last_execution_result is not None:
                    self._chromosome.set_last_execution_result(last_execution_result)
                mutations += 1

        if total_iterations >= max_mutations:
            stat.add_to_runtime_variable(RuntimeVariable.LocalSearchUnsuccessfulExploratoryMoves, 1)
        else:
            stat.add_to_runtime_variable(RuntimeVariable.LocalSearchSuccessfulExploratoryMoves, 1)
        return improved

    def _apply(self, op: _ParametrizedOp) -> bool:
        test_case = self._chromosome.test_case
        if op is _ParametrizedOp.RANDOM_CALL:
            return self._factory.insert_random_statement(test_case, self._position + 1) >= 0
        if op is _ParametrizedOp.PARAMETER:
            return self._factory.mutate_call(test_case, self._position)
        return self._factory.change_random_call(test_case, self._position)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def choose_local_search_statement(
    chromosome: TestCaseChromosome,
    position: int,
    objective: LocalSearchObjective,
    factory: TestFactory,
    timer: LocalSearchTimer,
) -> StatementLocalSearch | None:
    """Chooses the local search strategy for the statement at the position.

    Dispatch is by ``bound_type``/``accessible`` (there are no per-type
    statement classes). ``bool`` is checked before ``int`` explicitly since
    both are plain ``type`` objects here (no ``isinstance`` subclass ambiguity, but
    kept in this order to mirror the original dispatch intent).

    Args:
        chromosome: The test case which should be changed.
        position: The position of the statement in the test case.
        objective: The objective which checks if improvements are made.
        factory: The test factory which modifies the test case.
        timer: The timer which limits the local search.

    Returns:
        A strategy instance, or ``None`` if no strategy applies to this statement.
    """
    stmt = chromosome.test_case.get_statement(position)
    args = (chromosome, position, objective, factory, timer)

    if stmt.bound_type is bool:
        return BooleanLocalSearch(*args) if get_literal_value(stmt, bool) is not None else None
    if stmt.bound_type is int:
        return IntegerLocalSearch(*args) if get_literal_value(stmt, int) is not None else None
    if stmt.bound_type is float:
        return FloatLocalSearch(*args) if get_literal_value(stmt, float) is not None else None
    if stmt.bound_type is str:
        return StringLocalSearch(*args) if get_literal_value(stmt, str) is not None else None
    if stmt.bound_type is bytes:
        return BytesLocalSearch(*args) if get_literal_value(stmt, bytes) is not None else None
    if stmt.bound_type in _COLLECTION_TYPES:
        return CollectionLocalSearch(*args)
    if isinstance(stmt.accessible, gao.GenericEnum):
        return EnumLocalSearch(*args)
    if isinstance(stmt.accessible, gao.GenericCallableAccessibleObject):
        return ParametrizedStatementLocalSearch(*args)
    return None
