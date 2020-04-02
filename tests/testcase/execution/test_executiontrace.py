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
from pynguin.testcase.execution.executiontrace import ExecutionTrace


def test_merge():
    trace0 = ExecutionTrace()
    trace1 = ExecutionTrace()
    trace0.merge(trace1)
    assert trace0 == ExecutionTrace()


def test_merge_full():
    trace0 = ExecutionTrace()
    trace0.covered_for_loops.add(0)
    trace0.covered_for_loops.add(1)
    trace0.covered_functions.add(0)
    trace0.covered_functions.add(1)
    trace0.covered_predicates[0] = 9
    trace0.covered_predicates[1] = 7
    trace0.true_distances[0] = 6
    trace0.true_distances[1] = 3
    trace0.false_distances[0] = 0
    trace0.false_distances[1] = 1

    trace1 = ExecutionTrace()
    trace1.covered_for_loops.add(1)
    trace1.covered_for_loops.add(2)
    trace1.covered_functions.add(1)
    trace1.covered_functions.add(2)
    trace1.covered_predicates[1] = 5
    trace1.covered_predicates[2] = 8
    trace1.true_distances[1] = 19
    trace1.true_distances[2] = 3
    trace1.false_distances[1] = 234
    trace1.false_distances[2] = 0

    result = ExecutionTrace()
    result.covered_for_loops.add(0)
    result.covered_for_loops.add(1)
    result.covered_for_loops.add(2)
    result.covered_functions.add(0)
    result.covered_functions.add(1)
    result.covered_functions.add(2)
    result.covered_predicates[0] = 9
    result.covered_predicates[1] = 12
    result.covered_predicates[2] = 8
    result.true_distances[0] = 6
    result.true_distances[1] = 3
    result.true_distances[2] = 3
    result.false_distances[0] = 0
    result.false_distances[1] = 1
    result.false_distances[2] = 0

    trace0.merge(trace1)
    assert trace0 == result


def test_merge_min():
    dict0 = {0: 0.5, 1: 0.2}
    dict1 = {0: 0.3, 1: 0.6}
    ExecutionTrace._merge_min(dict0, dict1)
    assert dict0 == {0: 0.3, 1: 0.2}
