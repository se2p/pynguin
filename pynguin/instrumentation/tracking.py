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
import logging
import numbers
from typing import Set, Dict
from math import inf
from bytecode import Compare  # type: ignore


class ExecutionTracer:
    """Tracks branch distances during execution."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._existing_predicates: Set[int] = set()
        self._existing_functions: Set[int] = set()
        self._init_tracking()

    def clear_tracking(self) -> None:
        """Remove gathered data. Does not delete known predicates or functions."""
        self._init_tracking()

    def _init_tracking(self) -> None:
        self._covered_functions: Set[int] = set()
        self._covered_predicates: Dict[int, int] = {}
        self._true_distances: Dict[int, float] = {}
        self._false_distances: Dict[int, float] = {}

    @property
    def existing_predicates(self) -> Set[int]:
        """Get existing predicates."""
        return self._existing_predicates

    @property
    def existing_functions(self) -> Set[int]:
        """Get existing functions."""
        return self._existing_functions

    @property
    def covered_functions(self) -> Set[int]:
        """Get covered functions."""
        return self._covered_functions

    @property
    def covered_predicates(self) -> Dict[int, int]:
        """Get covered predicates and how often they were executed."""
        return self._covered_predicates

    @property
    def true_distances(self) -> Dict[int, float]:
        """Get the minimum distances from "True" per predicate."""
        return self._true_distances

    @property
    def false_distances(self) -> Dict[int, float]:
        """Get the minimum distances from "False" per predicate."""
        return self._false_distances

    def get_fitness(self) -> float:
        """Get the fitness of a test suite that generated the tracked data."""
        fit: float = len(self._existing_functions) - len(self._covered_functions)
        assert fit >= 0.0, "Amount of non covered functions cannot be negative"
        for predicate in self._existing_predicates:
            fit += self._predicate_fitness(predicate, self._true_distances)
            fit += self._predicate_fitness(predicate, self._false_distances)
        assert fit >= 0.0, "Fitness cannot be negative"
        return fit

    def _predicate_fitness(
        self, predicate: int, branch_distances: Dict[int, float]
    ) -> float:
        if predicate in branch_distances and branch_distances[predicate] == 0.0:
            return 0.0
        if (
            predicate in self._covered_predicates
            and self._covered_predicates[predicate] >= 2
        ):
            return self._normalize_fitness(branch_distances[predicate])
        return 1.0

    @staticmethod
    def _normalize_fitness(normalize: float) -> float:
        assert normalize >= 0.0, "Can only normalize non negative values"
        return normalize / (normalize + 1.0)

    def function_exists(self, function_id: int) -> None:
        """Declare that a function exists."""
        assert function_id not in self._existing_functions, "Function is already known"
        self._existing_functions.add(function_id)

    def entered_function(self, function_id: int) -> None:
        """Mark a function as covered. This means, that the function was at least entered once."""
        assert function_id in self._existing_functions, "Cannot trace unknown function"
        self._covered_functions.add(function_id)

    def predicate_exists(self, predicate: int) -> None:
        """Declare that a predicate exists."""
        assert predicate not in self._existing_predicates, "Predicate is already known"
        self._existing_predicates.add(predicate)

    def passed_cmp_predicate(self, value1, value2, predicate: int, cmp_op: Compare):
        """A predicate that is based on a comparision was passed."""
        assert predicate in self._existing_predicates, "Cannot trace unknown predicate"
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

    def passed_bool_predicate(self, value, predicate: int):
        """A predicate that is based on a boolean value was passed."""
        assert predicate in self._existing_predicates, "Cannot trace unknown predicate"
        distance_true = 0.0
        distance_false = 0.0
        if value:
            distance_false = 1.0
        else:
            distance_true = 1.0

        self._update_metrics(distance_false, distance_true, predicate)

    def _update_metrics(
        self, distance_false: float, distance_true: float, predicate: int
    ):
        assert predicate in self._existing_predicates, "Cannot update unknown predicate"
        assert distance_true >= 0.0, "True distance cannot be negative"
        assert distance_false >= 0.0, "False distance cannot be negative"
        assert (distance_true == 0.0 and distance_false > 0.0) or (
            distance_false == 0.0 and distance_true > 0.0
        ), "Exactly one distance must be 0.0"
        self._covered_predicates[predicate] = (
            self._covered_predicates.get(predicate, 0) + 1
        )
        self._true_distances[predicate] = min(
            self._true_distances.get(predicate, inf), distance_true
        )
        self._false_distances[predicate] = min(
            self._false_distances.get(predicate, inf), distance_false
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
