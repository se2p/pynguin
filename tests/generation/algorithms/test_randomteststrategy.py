#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testsuitechromosome as tsc
import pynguin.generation.generationalgorithmfactory as gaf
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.analyses.module import ModuleTestCluster
from pynguin.generation.algorithms.randomteststrategy import RandomTestStrategy
from pynguin.testcase.execution import ExecutionResult, TestCaseExecutor
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericCallableAccessibleObject,
)


@pytest.fixture
def executor():
    return MagicMock(TestCaseExecutor)


def test_generate_sequences(executor):
    config.configuration.stopping.maximum_search_time = 1
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x  # pragma: no cover
    algorithm.generate_sequence = lambda t, f, e: None  # pragma: no cover
    test_cases = algorithm.generate_tests()
    assert test_cases.size() == 0


def test_generate_sequences_exception(executor):
    def raise_exception(*args):
        raise GenerationException("Exception Test")

    def _combine_current_individual(*args):
        chromosome = MagicMock(tsc.TestSuiteChromosome)
        chromosome.get_fitness.return_value = 1.0
        return chromosome

    config.configuration.stopping.maximum_search_time = 1
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x  # pragma: no cover
    algorithm._combine_current_individual = _combine_current_individual
    algorithm.generate_sequence = raise_exception
    algorithm.generate_tests()
    assert "Generate test case failed with exception" in logger.method_calls[3].args[0]


def test_random_test_cases_no_bounds(executor):
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    algorithm._logger = logger
    config.configuration.random.max_sequences_combined = 0
    config.configuration.random.max_sequence_length = 0
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    assert isinstance(algorithm, RandomTestStrategy)
    result = algorithm._random_test_cases([tc_1, tc_2])
    assert 0 <= len(result) <= 2


def test_random_test_cases_with_bounds(executor):
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    algorithm._logger = logger
    config.configuration.random.max_sequences_combined = 2
    config.configuration.random.max_sequence_length = 2
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    assert isinstance(algorithm, RandomTestStrategy)
    result = algorithm._random_test_cases([tc_1, tc_2])
    assert 0 <= len(result) <= 1


def test_random_public_method(executor):
    config.configuration.algorithm = config.Algorithm.RANDOM
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    out_0 = MagicMock(GenericCallableAccessibleObject)
    out_1 = MagicMock(GenericAccessibleObject)
    out_2 = MagicMock(GenericCallableAccessibleObject)
    outs = {out_0, out_1, out_2}
    assert isinstance(algorithm, RandomTestStrategy)
    result = algorithm._random_public_method(outs)
    assert result == out_0 or result == out_2


@pytest.mark.parametrize("has_exceptions", [pytest.param(True), pytest.param(False)])
def test_generate_sequence(has_exceptions, executor, default_test_case):
    config.configuration.algorithm = config.Algorithm.RANDOM
    exec_result = MagicMock(ExecutionResult)
    exec_result.has_test_exceptions.return_value = has_exceptions
    executor.execute.return_value = exec_result
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, test_cluster
    ).get_search_algorithm()
    algorithm._random_public_method = lambda x: None  # pragma: no cover
    default_test_case.add_statement(MagicMock(stmt.Statement, ret_val=MagicMock()))
    algorithm._random_test_cases = lambda x: [default_test_case]  # pragma: no cover
    assert isinstance(algorithm, RandomTestStrategy)
    with pytest.raises(GenerationException):
        algorithm.generate_sequence(
            tsc.TestSuiteChromosome(),
            tsc.TestSuiteChromosome(),
        )


def test_generate_sequence_duplicate(executor, default_test_case):
    config.configuration.algorithm = config.Algorithm.RANDOM
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, test_cluster
    ).get_search_algorithm()
    algorithm._random_public_method = lambda x: None  # pragma: no cover
    algorithm._random_test_cases = lambda x: [default_test_case]  # pragma: no cover
    assert isinstance(algorithm, RandomTestStrategy)
    with pytest.raises(GenerationException):
        algorithm.generate_sequence(
            tsc.TestSuiteChromosome(),
            tsc.TestSuiteChromosome(),
        )
