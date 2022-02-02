#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
import importlib
from unittest.mock import MagicMock

import pytest

import pynguin.coverage.branchgoals as bg
import pynguin.generation.algorithms.dynamosastrategy as dyna
from pynguin.instrumentation.instrumentation import (
    BranchCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.testcase.execution import ExecutionTracer


@pytest.fixture
def known_data():
    nested_module = importlib.import_module("tests.fixtures.examples.nested")

    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(nested_module.test_me.__code__)
    return tracer.get_known_data()


@pytest.fixture
def known_data_nested():
    def testMe(y):  # pragma: no cover
        def inner(x):
            pass

    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(testMe.__code__)
    return tracer.get_known_data()


def test_fitness_graph_root_branches(known_data):
    pool = bg.BranchGoalPool(known_data)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, known_data)
    assert {br.goal for br in ffgraph.root_branches} == {
        bg.BranchGoal(0, 3, False),
        bg.BranchGoal(0, 3, True),
    }


def test_fitness_graph_structural_children(known_data):
    pool = bg.BranchGoalPool(known_data)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, known_data)
    target = [ff for ff in ffs if ff.goal == bg.BranchGoal(0, 2, True)][0]
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == {
        bg.BranchGoal(0, 0, False),
        bg.BranchGoal(0, 0, True),
    }


def test_fitness_graph_no_structural_children(known_data):
    pool = bg.BranchGoalPool(known_data)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, known_data)
    target = [ff for ff in ffs if ff.goal == bg.BranchGoal(0, 3, False)][0]
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == set()


def test_fitness_graph_nested(known_data_nested):
    pool = bg.BranchGoalPool(known_data_nested)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, known_data_nested)
    assert {ff.goal for ff in ffgraph.root_branches} == {
        bg.BranchlessCodeObjectGoal(0),
        bg.BranchlessCodeObjectGoal(1),
    }
