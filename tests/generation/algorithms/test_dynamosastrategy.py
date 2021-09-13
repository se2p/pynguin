#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
from unittest.mock import MagicMock

import pytest

import pynguin.coverage.branchgoals as bg
import pynguin.generation.algorithms.dynamosastrategy as dyna
from pynguin.instrumentation.instrumentation import BranchCoverageInstrumentation
from pynguin.testcase.execution.executiontracer import ExecutionTracer


@pytest.fixture
def known_data():
    def testMe(x, y):  # pragma: no cover
        if x <= y:
            if x == y:
                print("Some output")
            if x > 0:
                if y == 17:
                    return True
        return False

    tracer = ExecutionTracer()
    instr = BranchCoverageInstrumentation(tracer)
    instr.instrument_module(testMe.__code__)
    return tracer.get_known_data()


@pytest.fixture
def known_data_nested():
    def testMe(y):  # pragma: no cover
        def inner(x):
            pass

    tracer = ExecutionTracer()
    instr = BranchCoverageInstrumentation(tracer)
    instr.instrument_module(testMe.__code__)
    return tracer.get_known_data()


def test_fitness_graph_root_branches(known_data):
    pool = bg.BranchGoalPool(known_data)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna.BranchFitnessGraph(ffs, known_data)
    assert {br.goal for br in ffgraph.root_branches} == {
        bg.BranchGoal(0, 3, False),
        bg.BranchGoal(0, 3, True),
    }


def test_fitness_graph_structural_children(known_data):
    pool = bg.BranchGoalPool(known_data)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna.BranchFitnessGraph(ffs, known_data)
    target = [ff for ff in ffs if ff.goal == bg.BranchGoal(0, 2, True)][0]
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == {
        bg.BranchGoal(0, 0, False),
        bg.BranchGoal(0, 0, True),
    }


def test_fitness_graph_no_structural_children(known_data):
    pool = bg.BranchGoalPool(known_data)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna.BranchFitnessGraph(ffs, known_data)
    target = [ff for ff in ffs if ff.goal == bg.BranchGoal(0, 3, False)][0]
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == set()


def test_fitness_graph_nested(known_data_nested):
    pool = bg.BranchGoalPool(known_data_nested)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna.BranchFitnessGraph(ffs, known_data_nested)
    assert {ff.goal for ff in ffgraph.root_branches} == {
        bg.BranchlessCodeObjectGoal(0),
        bg.BranchlessCodeObjectGoal(1),
    }
