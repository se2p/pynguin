# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.generation.algorithms.randoopy.randomtestmonkeytypestrategy import (
    RandomTestMonkeyTypeStrategy,
)
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor
from pynguin.utils.statistics.statistics import StatisticsTracker, RuntimeVariable


@pytest.fixture
def strategy():
    strategy = RandomTestMonkeyTypeStrategy(MagicMock(AbstractExecutor))
    strategy.execute_test_case_monkey_type = lambda t, c: None
    strategy.execute_test_suite_monkey_type = lambda t, c: None
    return strategy


@pytest.mark.parametrize(
    "number_of_test_cases,execution_counter,test_cases",
    [
        pytest.param(0, 1, []),
        pytest.param(0, 0, [MagicMock(tc.TestCase)]),
        pytest.param(0, 0, [MagicMock(tc.TestCase), MagicMock(tc.TestCase)]),
    ],
)
def test_call_monkey_type(
    number_of_test_cases, execution_counter, test_cases, strategy
):
    config.INSTANCE.monkey_type_execution = 2
    strategy._call_monkey_type(
        number_of_test_cases, execution_counter, test_cases, MagicMock(TestCluster)
    )


def test_send_statistics(strategy):
    strategy.send_statistics()
    tracker = StatisticsTracker()
    statistics = [
        v
        for k, v in tracker.variables_generator
        if k == RuntimeVariable.monkey_type_executions
    ]
    assert len(statistics) == 1
    assert statistics[0] == 0
