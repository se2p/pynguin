#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

from pynguin.testcase.execution import ExecutionTrace


def test_merge():
    trace0 = ExecutionTrace()
    trace1 = ExecutionTrace()
    trace0.merge(trace1)
    assert trace0 == ExecutionTrace()


def test_merge_full():
    trace0 = ExecutionTrace()
    trace0.executed_code_objects.add(0)
    trace0.executed_code_objects.add(1)
    trace0.executed_predicates[0] = 9
    trace0.executed_predicates[1] = 7
    trace0.true_distances[0] = 6
    trace0.true_distances[1] = 3
    trace0.false_distances[0] = 0
    trace0.false_distances[1] = 1
    trace0.covered_line_ids = {0}

    trace1 = ExecutionTrace()
    trace1.executed_code_objects.add(1)
    trace1.executed_code_objects.add(2)
    trace1.executed_predicates[1] = 5
    trace1.executed_predicates[2] = 8
    trace1.true_distances[1] = 19
    trace1.true_distances[2] = 3
    trace1.false_distances[1] = 234
    trace1.false_distances[2] = 0
    trace1.covered_line_ids = {1}

    result = ExecutionTrace()
    result.executed_code_objects.add(0)
    result.executed_code_objects.add(1)
    result.executed_code_objects.add(2)
    result.executed_predicates[0] = 9
    result.executed_predicates[1] = 12
    result.executed_predicates[2] = 8
    result.true_distances[0] = 6
    result.true_distances[1] = 3
    result.true_distances[2] = 3
    result.false_distances[0] = 0
    result.false_distances[1] = 1
    result.false_distances[2] = 0
    result.covered_line_ids = {0, 1}

    trace0.merge(trace1)
    assert trace0 == result


def test_merge_min():
    dict0 = {0: 0.5, 1: 0.2}
    dict1 = {0: 0.3, 1: 0.6}
    ExecutionTrace._merge_min(dict0, dict1)
    assert dict0 == {0: 0.3, 1: 0.2}
