#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericCallableAccessibleObject,
)


@pytest.fixture
def executor():
    return MagicMock(TestCaseExecutor)


def test_generate_sequences(executor):
    config.INSTANCE.budget = 1
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor, MagicMock(TestCluster))
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm.generate_sequence = lambda t, f, e: None
    test_cases, failing_test_cases = algorithm.generate_sequences()
    assert test_cases.size() == 0
    assert failing_test_cases.size() == 0
    assert len(logger.method_calls) == 1


def test_generate_sequences_exception(executor):
    def raise_exception(*args):
        raise GenerationException("Exception Test")

    def _combine_current_individual(*args):
        chromosome = MagicMock(tsc.TestSuiteChromosome)
        chromosome.get_fitness.return_value = 1.0
        return chromosome

    config.INSTANCE.budget = 1
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor, MagicMock(TestCluster))
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm._combine_current_individual = _combine_current_individual
    algorithm.generate_sequence = raise_exception
    algorithm.generate_sequences()
    assert "Generate test case failed with exception" in logger.method_calls[3].args[0]


def test_random_test_cases_no_bounds(executor):
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor, MagicMock(TestCluster))
    algorithm._logger = logger
    config.INSTANCE.max_sequences_combined = 0
    config.INSTANCE.max_sequence_length = 0
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    result = algorithm._random_test_cases([tc_1, tc_2])
    assert 0 <= len(result) <= 2


def test_random_test_cases_with_bounds(executor):
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor, MagicMock(TestCluster))
    algorithm._logger = logger
    config.INSTANCE.max_sequences_combined = 2
    config.INSTANCE.max_sequence_length = 2
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    result = algorithm._random_test_cases([tc_1, tc_2])
    assert 0 <= len(result) <= 1


def test_random_public_method(executor):
    algorithm = RandomTestStrategy(executor, MagicMock(TestCluster))
    out_0 = MagicMock(GenericCallableAccessibleObject)
    out_1 = MagicMock(GenericAccessibleObject)
    out_2 = MagicMock(GenericCallableAccessibleObject)
    outs = {out_0, out_1, out_2}
    result = algorithm._random_public_method(outs)
    assert result == out_0 or result == out_2


@pytest.mark.parametrize("has_exceptions", [pytest.param(True), pytest.param(False)])
def test_generate_sequence(has_exceptions, executor):
    exec_result = MagicMock(ExecutionResult)
    exec_result.has_test_exceptions.return_value = has_exceptions
    executor.execute.return_value = exec_result
    test_cluster = MagicMock(TestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm = RandomTestStrategy(executor, test_cluster)
    algorithm._random_public_method = lambda x: None
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(MagicMock(stmt.Statement))
    algorithm._random_test_cases = lambda x: [test_case]
    with pytest.raises(GenerationException):
        algorithm.generate_sequence(
            tsc.TestSuiteChromosome(), tsc.TestSuiteChromosome(), 0,
        )


def test_generate_sequence_duplicate(executor):
    test_cluster = MagicMock(TestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm = RandomTestStrategy(executor, test_cluster)
    algorithm._random_public_method = lambda x: None
    test_case = dtc.DefaultTestCase()
    algorithm._random_test_cases = lambda x: [test_case]
    with pytest.raises(GenerationException):
        algorithm.generate_sequence(
            tsc.TestSuiteChromosome(), tsc.TestSuiteChromosome(), 0,
        )
