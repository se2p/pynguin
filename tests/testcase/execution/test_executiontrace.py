#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from pynguin.testcase.execution import ExecutionTrace, FileStatementData


def test_merge():
    trace0 = ExecutionTrace()
    trace1 = ExecutionTrace()
    trace0.merge(trace1)
    assert trace0 == ExecutionTrace()


def test_merge_full():
    foo_tracker_1 = FileStatementData("foo")
    foo_tracker_1.statements.add(0)
    foo_tracker_1.statements.add(1)
    foo_tracker_1.visited_statements[0] = 1
    bar_tracker_1 = FileStatementData("bar")
    bar_tracker_1.statements.add(0)
    bar_tracker_1.statements.add(1)
    trace0 = ExecutionTrace()
    trace0.executed_code_objects.add(0)
    trace0.executed_code_objects.add(1)
    trace0.executed_predicates[0] = 9
    trace0.executed_predicates[1] = 7
    trace0.true_distances[0] = 6
    trace0.true_distances[1] = 3
    trace0.false_distances[0] = 0
    trace0.false_distances[1] = 1
    trace0.file_trackers["foo"] = foo_tracker_1
    trace0.file_trackers["bar"] = bar_tracker_1

    foo_tracker_2 = FileStatementData("foo")
    foo_tracker_2.statements.add(0)
    foo_tracker_2.statements.add(1)
    foo_tracker_2.visited_statements[0] = 3
    foo_tracker_2.visited_statements[1] = 3
    trace1 = ExecutionTrace()
    trace1.executed_code_objects.add(1)
    trace1.executed_code_objects.add(2)
    trace1.executed_predicates[1] = 5
    trace1.executed_predicates[2] = 8
    trace1.true_distances[1] = 19
    trace1.true_distances[2] = 3
    trace1.false_distances[1] = 234
    trace1.false_distances[2] = 0
    trace1.file_trackers["foo"] = foo_tracker_2

    result = ExecutionTrace()
    foo_tracker_3 = FileStatementData("foo")
    foo_tracker_3.statements.add(0)
    foo_tracker_3.statements.add(1)
    foo_tracker_3.visited_statements[0] = 4
    foo_tracker_3.visited_statements[1] = 3
    bar_tracker_2 = FileStatementData("bar")
    bar_tracker_2.statements.add(0)
    bar_tracker_2.statements.add(1)
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
    result.file_trackers["foo"] = foo_tracker_3
    result.file_trackers["bar"] = bar_tracker_2

    trace0.merge(trace1)
    assert trace0 == result


def test_merge_min():
    dict0 = {0: 0.5, 1: 0.2}
    dict1 = {0: 0.3, 1: 0.6}
    ExecutionTrace._merge_min(dict0, dict1)
    assert dict0 == {0: 0.3, 1: 0.2}


def test_merge_max():
    dict0 = {0: 0.5, 1: 0.2}
    dict1 = {0: 0.3, 1: 0.6}
    ExecutionTrace._merge_max(dict0, dict1)
    assert dict0 == {0: 0.5, 1: 0.6}
