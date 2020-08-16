#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.execution.testcaseexecutor as executor
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.generation.algorithms.randoopy.randomtestmonkeytypestrategy import (
    RandomTestMonkeyTypeStrategy,
)
from pynguin.setup.testcluster import TestCluster
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker


@pytest.fixture
def strategy():
    strategy = RandomTestMonkeyTypeStrategy(
        MagicMock(executor.TestCaseExecutor), MagicMock(TestCluster)
    )
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
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_tests(test_cases)
    strategy._call_monkey_type(number_of_test_cases, execution_counter, test_suite)


def test_send_statistics(strategy):
    strategy.send_statistics()
    tracker = StatisticsTracker()
    statistics = [
        v
        for k, v in tracker.variables_generator
        if k == RuntimeVariable.MonkeyTypeExecutions
    ]
    assert len(statistics) == 1
    assert statistics[0] == 0
