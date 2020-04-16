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
from typing import Set, Any, Callable, Dict, Tuple
from math import inf
from bytecode import Compare
from jellyfish import levenshtein_distance

from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.utils.type_utils import is_numeric, is_string


@dataclasses.dataclass
class KnownData:
    """Contains known code objects and predicates.
    FIXME(fk) better class name...
    """

    existing_code_objects: Set[int] = dataclasses.field(default_factory=set)
    existing_predicates: Set[int] = dataclasses.field(default_factory=set)

    # Some information to make debugging easier.
    code_object_names: Dict[int, str] = dataclasses.field(default_factory=dict)


class ExecutionTracer:
    """Tracks branch distances during execution.
    The results are stored in an execution trace."""

    _logger = logging.getLogger(__name__)

    # Contains static information about how branch distances
    # for certain op codes should be computed.
    # The returned tuple for each computation is (true distance, false distance).
    # pylint: disable=arguments-out-of-order
    _DISTANCE_COMPUTATIONS: Dict[Compare, Callable[[Any, Any], Tuple[float, float]]] = {
        Compare.EQ: lambda val1, val2: (_eq(val1, val2), _neq(val1, val2),),
        Compare.NE: lambda val1, val2: (_neq(val1, val2), _eq(val1, val2),),
        Compare.LT: lambda val1, val2: (_lt(val1, val2), _le(val2, val1),),
        Compare.LE: lambda val1, val2: (_le(val1, val2), _lt(val2, val1),),
        Compare.GT: lambda val1, val2: (_lt(val2, val1), _le(val1, val2),),
        Compare.GE: lambda val1, val2: (_le(val2, val1), _lt(val1, val2),),
        Compare.IN: lambda val1, val2: (_in(val1, val2), _nin(val1, val2),),
        Compare.NOT_IN: lambda val1, val2: (_nin(val1, val2), _in(val1, val2),),
        Compare.IS: lambda val1, val2: (_is(val1, val2), _isn(val1, val2),),
        Compare.IS_NOT: lambda val1, val2: (_isn(val1, val2), _is(val1, val2),),
    }

    def __init__(self) -> None:
        self._known_data = KnownData()

        # Contains the trace information that is generated when a module is imported
        self._import_trace = ExecutionTrace()

        self._init_trace()
        self._enabled = True

    def get_known_data(self) -> KnownData:
        """Provide known data."""
        return self._known_data

    def store_import_trace(self) -> None:
        """Stores the current trace as the import trace.
        Should only be done once, after a module was loaded.
        The import trace will be merged into every subsequently recorded trace."""
        self._import_trace = self._trace
        self._init_trace()

    def _init_trace(self) -> None:
        """Create a new trace that only contains the trace data from the import."""
        new_trace = ExecutionTrace()
        new_trace.merge(self._import_trace)
        self._trace = new_trace

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
        """Clear trace."""
        self._init_trace()

    def code_object_exists(self, code_object_id: int, name: str = "") -> None:
        """Declare that a code object exists."""
        assert (
            code_object_id not in self._known_data.existing_code_objects
        ), "Code object is already known"
        self._known_data.existing_code_objects.add(code_object_id)
        self._known_data.code_object_names[code_object_id] = name

    def entered_code_object(self, code_object_id: int) -> None:
        """Mark a code object as covered. This means, that the code object
        was at least entered once."""
        assert (
            code_object_id in self._known_data.existing_code_objects
        ), "Cannot trace unknown code object"
        self._trace.covered_code_objects.add(code_object_id)

    def predicate_exists(self, predicate: int) -> None:
        """Declare that a predicate exists."""
        assert (
            predicate not in self._known_data.existing_predicates
        ), "Predicate is already known"
        self._known_data.existing_predicates.add(predicate)

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
            distance_true, distance_false = ExecutionTracer._DISTANCE_COMPUTATIONS[
                cmp_op
            ](value1, value2)

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
        assert (distance_true == 0.0) ^ (
            distance_false == 0.0
        ), "Exactly one distance must be 0.0, i.e., one branch must be taken."
        self._trace.covered_predicates[predicate] = (
            self._trace.covered_predicates.get(predicate, 0) + 1
        )
        self._trace.true_distances[predicate] = min(
            self._trace.true_distances.get(predicate, inf), distance_true
        )
        self._trace.false_distances[predicate] = min(
            self._trace.false_distances.get(predicate, inf), distance_false
        )


def _eq(val1, val2) -> float:
    """Distance computation for '=='"""
    if val1 == val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return abs(val1 - val2)
    if is_string(val1) and is_string(val2):
        return levenshtein_distance(val1, val2)
    return inf


def _neq(val1, val2) -> float:
    """Distance computation for '!='"""
    if val1 != val2:
        return 0.0
    return 1.0


def _lt(val1, val2) -> float:
    """Distance computation for '<'"""
    if val1 < val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return (val1 - val2) + 1.0
    return inf


def _le(val1, val2) -> float:
    """Distance computation for '<='"""
    if val1 <= val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return (val1 - val2) + 1.0
    return inf


def _in(val1, val2) -> float:
    """Distance computation for 'in'"""
    # TODO(fk) iterate over elements and return smallest distance?
    if val1 in val2:
        return 0.0
    return 1.0


def _nin(val1, val2) -> float:
    """Distance computation for 'not in'"""
    if val1 not in val2:
        return 0.0
    return 1.0


def _is(val1, val2) -> float:
    """Distance computation for 'is'"""
    if val1 is val2:
        return 0.0
    return 1.0


def _isn(val1, val2) -> float:
    """Distance computation for 'is not'"""
    if val1 is not val2:
        return 0.0
    return 1.0
