#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
import importlib

from unittest.mock import MagicMock

import pytest

import pynguin.ga.algorithms.dynamosaalgorithm as dyna
import pynguin.ga.coveragegoals as bg

from pynguin.instrumentation.instrumentation import BranchCoverageInstrumentation
from pynguin.instrumentation.instrumentation import InstrumentationTransformer
from pynguin.instrumentation.tracer import ExecutionTracer


@pytest.fixture
def subject_properties():
    nested_module = importlib.import_module("tests.fixtures.examples.nested")

    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(nested_module.test_me.__code__)
    return tracer.get_subject_properties()


@pytest.fixture
def subject_properties_nested():
    def testMe(_):  # pragma: no cover  # noqa: N802
        def inner(_):
            pass

    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(testMe.__code__)
    return tracer.get_subject_properties()


def test_fitness_graph_root_branches(subject_properties):
    pool = bg.BranchGoalPool(subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, subject_properties)
    assert {br.goal for br in ffgraph.root_branches} == {
        bg.BranchGoal(code_object_id=0, predicate_id=3, value=False),
        bg.BranchGoal(code_object_id=0, predicate_id=3, value=True),
    }


def test_fitness_graph_structural_children(subject_properties):
    pool = bg.BranchGoalPool(subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, subject_properties)
    target = next(
        ff for ff in ffs if ff.goal == bg.BranchGoal(code_object_id=0, predicate_id=2, value=True)
    )
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == {
        bg.BranchGoal(code_object_id=0, predicate_id=0, value=False),
        bg.BranchGoal(code_object_id=0, predicate_id=0, value=True),
    }


def test_fitness_graph_no_structural_children(subject_properties):
    pool = bg.BranchGoalPool(subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, subject_properties)
    target = next(
        ff for ff in ffs if ff.goal == bg.BranchGoal(code_object_id=0, predicate_id=3, value=False)
    )
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == set()


def test_fitness_graph_nested(subject_properties_nested):
    pool = bg.BranchGoalPool(subject_properties_nested)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, subject_properties_nested)
    assert {ff.goal for ff in ffgraph.root_branches} == {
        bg.BranchlessCodeObjectGoal(0),
        bg.BranchlessCodeObjectGoal(1),
    }
