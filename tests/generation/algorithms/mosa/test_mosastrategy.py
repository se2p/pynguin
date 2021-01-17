#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosomefactory as cf
import pynguin.ga.fitnessfunction as ff
from pynguin.ga.operators.crossover.crossover import CrossOverFunction
from pynguin.ga.operators.ranking.rankingfunction import RankingFunction
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.generation.algorithms.mosa.mosastrategy import MOSATestStrategy
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.fixture
def mosa_strategy():
    return MOSATestStrategy()


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


def test_property_fitness_functions(mosa_strategy):
    fitness_1 = MagicMock(ff.FitnessFunction)
    fitness_2 = MagicMock(ff.FitnessFunction)
    mosa_strategy.add_fitness_function(fitness_1)
    mosa_strategy.add_fitness_functions([fitness_2])
    assert mosa_strategy.fitness_functions == [fitness_1, fitness_2]

    assert mosa_strategy.remove_fitness_function(fitness_2)
    assert not mosa_strategy.remove_fitness_function(MagicMock(ff.FitnessFunction))
