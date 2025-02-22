#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosomefactory as cf

from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.ga.operators.crossover import CrossOverFunction
from pynguin.ga.operators.ranking import RankingFunction
from pynguin.ga.operators.selection import SelectionFunction
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import TestCaseExecutor


@pytest.fixture
def mosa_strategy():
    return MOSAAlgorithm()


def test_property_chromosome_factory(mosa_strategy):
    factory = MagicMock(cf.ChromosomeFactory)
    mosa_strategy.chromosome_factory = factory
    assert mosa_strategy.chromosome_factory == factory


def test_property_executor(mosa_strategy):
    executor = TestCaseExecutor(MagicMock(ExecutionTracer))
    mosa_strategy.executor = executor
    assert mosa_strategy.executor == executor


def test_property_selection_function(mosa_strategy):
    selection_function = MagicMock(SelectionFunction())
    mosa_strategy.selection_function = selection_function
    assert mosa_strategy.selection_function == selection_function


def test_property_crossover_function(mosa_strategy):
    crossover_function = MagicMock(CrossOverFunction)
    mosa_strategy.crossover_function = crossover_function
    assert mosa_strategy.crossover_function == crossover_function


def test_property_ranking_function(mosa_strategy):
    ranking_function = MagicMock(RankingFunction)
    mosa_strategy.ranking_function = ranking_function
    assert mosa_strategy.ranking_function == ranking_function
