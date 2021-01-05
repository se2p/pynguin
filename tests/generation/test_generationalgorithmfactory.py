#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.generation.generationalgorithmfactory as gaf
from pynguin.generation.algorithms.mosa.mosastrategy import MOSATestStrategy
from pynguin.generation.algorithms.randomsearch.randomsearchstrategy import (
    RandomSearchStrategy,
)
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.wspy.wholesuiteteststrategy import (
    WholeSuiteTestStrategy,
)
from pynguin.generation.stoppingconditions.maxiterationsstoppingcondition import (
    MaxIterationsStoppingCondition,
)
from pynguin.generation.stoppingconditions.maxtestsstoppingcondition import (
    MaxTestsStoppingCondition,
)
from pynguin.generation.stoppingconditions.maxtimestoppingcondition import (
    MaxTimeStoppingCondition,
)
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.exceptions import ConfigurationException


@pytest.fixture
def algorithm_factory() -> gaf.TestSuiteGenerationAlgorithmFactory:
    return gaf.TestSuiteGenerationAlgorithmFactory(
        MagicMock(TestCaseExecutor), MagicMock(TestCluster)
    )


@pytest.mark.parametrize(
    "algorithm, cls",
    [
        pytest.param(config.Algorithm.MOSA, MOSATestStrategy),
        pytest.param(config.Algorithm.RANDOMSEARCH, RandomSearchStrategy),
        pytest.param(config.Algorithm.RANDOM, RandomTestStrategy),
        pytest.param(config.Algorithm.WHOLE_SUITE, WholeSuiteTestStrategy),
    ],
)
def test_instantiate_strategy(algorithm, cls, algorithm_factory):
    config.INSTANCE.algorithm = algorithm
    instance = algorithm_factory.get_search_algorithm()
    assert isinstance(instance, cls)


@pytest.mark.parametrize(
    "condition, cls",
    [
        pytest.param(config.StoppingCondition.MAX_TESTS, MaxTestsStoppingCondition),
        pytest.param(config.StoppingCondition.MAX_TIME, MaxTimeStoppingCondition),
        pytest.param(
            config.StoppingCondition.MAX_ITERATIONS, MaxIterationsStoppingCondition
        ),
        pytest.param("foo", MaxTimeStoppingCondition),
    ],
)
def test_stopping_condition(condition, cls, algorithm_factory):
    config.INSTANCE.stopping_condition = condition
    strategy = algorithm_factory.get_search_algorithm()
    assert isinstance(strategy.stopping_condition, cls)


def test_unknown_strategy(algorithm_factory):
    config.INSTANCE.algorithm = MagicMock()
    with pytest.raises(ConfigurationException):
        algorithm_factory.get_search_algorithm()
