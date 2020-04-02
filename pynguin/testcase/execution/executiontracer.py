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
"""Provides capabilities to track branch distances."""
import dataclasses
import logging
import numbers
from typing import Set
from math import inf
from bytecode import Compare

from pynguin.testcase.execution.executiontrace import ExecutionTrace


@dataclasses.dataclass
class KnownData:
    """Contains known functions, predicates and for loops.
    FIXME(fk) better class name...
    """

    existing_functions: Set[int] = dataclasses.field(default_factory=set)
    existing_predicates: Set[int] = dataclasses.field(default_factory=set)
    existing_for_loops: Set[int] = dataclasses.field(default_factory=set)


class ExecutionTracer:
    """Tracks branch distances during execution.
    The results are stored in an execution trace."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._known_data = KnownData()
        self._init_trace()
        self._enabled = True

    def get_known_data(self) -> KnownData:
        """Provide known data."""
        return self._known_data

    def _init_trace(self) -> None:
        """Create a new trace without any information."""
        self._trace = ExecutionTrace()

    def _is_disabled(self) -> bool:
        """Should we track anything?
        We might have to disable tracing, e.g. when calling __eq__ ourselves.
        Otherwise we create an endless recursion."""
        return not self._enabled

    def _enable(self) -> None:
        """Enable tracing."""
        self._enabled = True

    def _disable(self) -> None:
        """Disable tracing."""
        self._enabled = False

    def get_trace(self) -> ExecutionTrace:
        """Get the trace with the current information."""
        return self._trace

    def clear_trace(self) -> None:
        """Clear trace. Does not delete known predicates/functions/for-loops."""
        self._init_trace()

    def function_exists(self, function_id: int) -> None:
        """Declare that a function exists."""
        assert (
            function_id not in self._known_data.existing_functions
        ), "Function is already known"
        self._known_data.existing_functions.add(function_id)

    def entered_function(self, function_id: int) -> None:
        """Mark a function as covered. This means, that the function was at least entered once."""
        assert (
            function_id in self._known_data.existing_functions
        ), "Cannot trace unknown function"
        self._trace.covered_functions.add(function_id)

    def for_loop_exists(self, for_loop_id: int) -> None:
        """Declare that a for loop exists."""
        assert (
            for_loop_id not in self._known_data.existing_for_loops
        ), "for loop already known"
        self._known_data.existing_for_loops.add(for_loop_id)

    def entered_for_loop(self, for_loop_id: int) -> None:
        """Marks a for loop as covered. This means, that the for loop was at least entered once."""
        assert (
            for_loop_id in self._known_data.existing_for_loops
        ), "Cannot tracer unknown for loop"
        self._trace.covered_for_loops.add(for_loop_id)

    def predicate_exists(self, predicate: int) -> None:
        """Declare that a predicate exists."""
        assert (
            predicate not in self._known_data.existing_predicates
        ), "Predicate is already known"
        self._known_data.existing_predicates.add(predicate)

    # pylint: disable=too-many-branches
    def passed_cmp_predicate(
        self, value1, value2, predicate: int, cmp_op: Compare
    ) -> None:
        """A predicate that is based on a comparision was passed."""
        if self._is_disabled():
            return

        try:
            self._disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            if cmp_op == Compare.EQ:
                distance_true, distance_false = (
                    self._eq(value1, value2),
                    self._neq(value1, value2),
                )
            elif cmp_op == Compare.NE:
                distance_true, distance_false = (
                    self._neq(value1, value2),
                    self._eq(value1, value2),
                )
            elif cmp_op == Compare.LT:
                distance_true, distance_false = (
                    self._lt(value1, value2),
                    self._le(value2, value1),
                )
            elif cmp_op == Compare.LE:
                distance_true, distance_false = (
                    self._le(value1, value2),
                    self._lt(value2, value1),
                )
            elif cmp_op == Compare.GT:
                distance_true, distance_false = (
                    self._lt(value2, value1),
                    self._le(value1, value2),
                )
            elif cmp_op == Compare.GE:
                distance_true, distance_false = (
                    self._le(value2, value1),
                    self._lt(value1, value2),
                )
            elif cmp_op == Compare.IN:
                distance_true, distance_false = (
                    self._in(value1, value2),
                    self._nin(value1, value2),
                )
            elif cmp_op == Compare.NOT_IN:
                distance_true, distance_false = (
                    self._nin(value1, value2),
                    self._in(value1, value2),
                )
            elif cmp_op == Compare.IS:
                distance_true, distance_false = (
                    self._is(value1, value2),
                    self._isn(value1, value2),
                )
            elif cmp_op == Compare.IS_NOT:
                distance_true, distance_false = (
                    self._isn(value1, value2),
                    self._is(value1, value2),
                )
            else:
                raise Exception(
                    "Unknown cmp_op {0}, value1={1}, value2={2}".format(
                        str(cmp_op), str(value1), str(value2)
                    )
                )

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self._enable()

    def passed_bool_predicate(self, value, predicate: int):
        """A predicate that is based on a boolean value was passed."""
        if self._is_disabled():
            return

        try:
            self._disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            distance_true = 0.0
            distance_false = 0.0
            if value:
                distance_false = 1.0
            else:
                distance_true = 1.0

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self._enable()

    def _update_metrics(
        self, distance_false: float, distance_true: float, predicate: int
    ):
        assert (
            predicate in self._known_data.existing_predicates
        ), "Cannot update unknown predicate"
        assert distance_true >= 0.0, "True distance cannot be negative"
        assert distance_false >= 0.0, "False distance cannot be negative"
        assert (distance_true == 0.0 and distance_false > 0.0) or (
            distance_false == 0.0 and distance_true > 0.0
        ), "Exactly one distance must be 0.0"
        self._trace.covered_predicates[predicate] = (
            self._trace.covered_predicates.get(predicate, 0) + 1
        )
        self._trace.true_distances[predicate] = min(
            self._trace.true_distances.get(predicate, inf), distance_true
        )
        self._trace.false_distances[predicate] = min(
            self._trace.false_distances.get(predicate, inf), distance_false
        )

    @staticmethod
    def _is_numeric(value):
        return isinstance(value, numbers.Number)

    @staticmethod
    def _eq(val1, val2):
        if val1 == val2:
            return 0.0
        if ExecutionTracer._is_numeric(val1) and ExecutionTracer._is_numeric(val2):
            return abs(val1 - val2)
        return 1.0

    @staticmethod
    def _neq(val1, val2):
        if val1 != val2:
            return 0.0
        return 1.0

    @staticmethod
    def _lt(val1, val2):
        if val1 < val2:
            return 0.0
        return (val1 - val2) + 1.0

    @staticmethod
    def _le(val1, val2):
        if val1 <= val2:
            return 0.0
        return (val1 - val2) + 1.0

    @staticmethod
    def _in(val1, val2):
        if val1 in val2:
            return 0.0
        return 1.0

    @staticmethod
    def _nin(val1, val2):
        if val1 not in val2:
            return 0.0
        return 1.0

    @staticmethod
    def _is(val1, val2):
        if val1 is val2:
            return 0.0
        return 1.0

    @staticmethod
    def _isn(val1, val2):
        if val1 is not val2:
            return 0.0
        return 1.0
