#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf

from pynguin.analyses.module import ModuleTestCluster
from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.ga.algorithms.randomalgorithm import RandomAlgorithm
from pynguin.ga.algorithms.randomsearchalgorithm import RandomTestSuiteSearchAlgorithm
from pynguin.ga.algorithms.wholesuitealgorithm import WholeSuiteAlgorithm
from pynguin.ga.stoppingcondition import CoveragePlateauStoppingCondition
from pynguin.ga.stoppingcondition import MaxCoverageStoppingCondition
from pynguin.ga.stoppingcondition import MaxIterationsStoppingCondition
from pynguin.ga.stoppingcondition import MaxMemoryStoppingCondition
from pynguin.ga.stoppingcondition import MaxSearchTimeStoppingCondition
from pynguin.ga.stoppingcondition import MaxStatementExecutionsStoppingCondition
from pynguin.ga.stoppingcondition import MaxTestExecutionsStoppingCondition
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.exceptions import ConfigurationException


@pytest.fixture
def algorithm_factory() -> gaf.TestSuiteGenerationAlgorithmFactory:
    return gaf.TestSuiteGenerationAlgorithmFactory(
        MagicMock(TestCaseExecutor), MagicMock(ModuleTestCluster)
    )


@pytest.mark.parametrize(
    "algorithm, cls",
    [
        pytest.param(config.Algorithm.MOSA, MOSAAlgorithm),
        pytest.param(config.Algorithm.RANDOM_TEST_SUITE_SEARCH, RandomTestSuiteSearchAlgorithm),
        pytest.param(config.Algorithm.RANDOM, RandomAlgorithm),
        pytest.param(config.Algorithm.WHOLE_SUITE, WholeSuiteAlgorithm),
    ],
)
def test_instantiate_strategy(algorithm, cls, algorithm_factory):
    config.configuration.algorithm = algorithm
    instance = algorithm_factory.get_search_algorithm()
    assert isinstance(instance, cls)


@pytest.mark.parametrize(
    "condition, cls",
    [
        pytest.param(
            "maximum_test_executions",
            MaxTestExecutionsStoppingCondition,
        ),
        pytest.param(
            "maximum_statement_executions",
            MaxStatementExecutionsStoppingCondition,
        ),
        pytest.param("maximum_search_time", MaxSearchTimeStoppingCondition),
        pytest.param("maximum_iterations", MaxIterationsStoppingCondition),
        pytest.param("maximum_coverage", MaxCoverageStoppingCondition),
        pytest.param("maximum_coverage_plateau", CoveragePlateauStoppingCondition),
    ],
)
def test_stopping_condition(condition, cls, algorithm_factory):
    setattr(config.configuration.stopping, condition, 5)
    strategy = algorithm_factory.get_search_algorithm()
    assert isinstance(strategy.stopping_conditions[0], cls)


def test_optional_stopping_condition(algorithm_factory):
    config.configuration.stopping.maximum_memory = 1000
    strategy = algorithm_factory.get_search_algorithm()
    assert isinstance(strategy.stopping_conditions[1], MaxMemoryStoppingCondition)


def test_stopping_condition_not_set(algorithm_factory):
    strategy = algorithm_factory.get_search_algorithm()
    assert isinstance(strategy.stopping_conditions[0], MaxSearchTimeStoppingCondition)
    assert (
        strategy.stopping_conditions[0].limit()
        == gaf.GenerationAlgorithmFactory._DEFAULT_MAX_SEARCH_TIME
    )


def test_unknown_strategy(algorithm_factory):
    config.configuration.algorithm = MagicMock()
    with pytest.raises(ConfigurationException):
        algorithm_factory.get_search_algorithm()
