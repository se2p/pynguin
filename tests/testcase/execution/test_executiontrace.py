#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

from pynguin.instrumentation.tracer import ExecutedAssertion
from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.slicer.executedinstruction import ExecutedInstruction


def test_merge():
    trace0 = ExecutionTrace()
    trace1 = ExecutionTrace()
    trace0.merge(trace1)
    assert trace0 == ExecutionTrace()


def test_merge_full():
    instr0 = ExecutedInstruction("foo", 0, 1, 2, 3, 4, 5)
    stmt0 = MagicMock()
    assert0 = ExecutedAssertion(0, 1, 2, stmt0)

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
    trace0.executed_instructions = [instr0]
    trace0.executed_assertions = [assert0]

    instr1 = ExecutedInstruction("bar", 1, 2, 3, 4, 5, 6)
    stmt1 = MagicMock()
    assert1 = ExecutedAssertion(1, 2, 3, stmt1)
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
    trace1.executed_instructions = [instr0, instr1]
    trace1.executed_assertions = [assert1]

    # Shifted by one
    assert2 = ExecutedAssertion(1, 2, 4, stmt1)

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
    # instr0 is prepended
    result.executed_instructions = [instr0, instr0, instr1]
    result.executed_assertions = [assert0, assert2]

    trace0.merge(trace1)
    assert trace0 == result


def test_merge_min():
    dict0 = {0: 0.5, 1: 0.2}
    dict1 = {0: 0.3, 1: 0.6}
    ExecutionTrace._merge_min(dict0, dict1)
    assert dict0 == {0: 0.3, 1: 0.2}
