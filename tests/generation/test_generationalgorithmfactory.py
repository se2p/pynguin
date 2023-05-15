#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.generation.generationalgorithmfactory as gaf

from pynguin.analyses.module import ModuleTestCluster
from pynguin.ga.algorithms.mosastrategy import MOSATestStrategy
from pynguin.ga.algorithms.randomsearchstrategy import RandomTestSuiteSearchStrategy
from pynguin.ga.algorithms.randomteststrategy import RandomTestStrategy
from pynguin.ga.algorithms.wholesuiteteststrategy import WholeSuiteTestStrategy
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxIterationsStoppingCondition,
)
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxSearchTimeStoppingCondition,
)
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxStatementExecutionsStoppingCondition,
)
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxTestExecutionsStoppingCondition,
)
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
        pytest.param(config.Algorithm.MOSA, MOSATestStrategy),
        pytest.param(
            config.Algorithm.RANDOM_TEST_SUITE_SEARCH, RandomTestSuiteSearchStrategy
        ),
        pytest.param(config.Algorithm.RANDOM, RandomTestStrategy),
        pytest.param(config.Algorithm.WHOLE_SUITE, WholeSuiteTestStrategy),
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
    ],
)
def test_stopping_condition(condition, cls, algorithm_factory):
    setattr(config.configuration.stopping, condition, 5)
    strategy = algorithm_factory.get_search_algorithm()
    assert isinstance(strategy.stopping_conditions[0], cls)


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
