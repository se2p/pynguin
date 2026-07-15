#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from logging import Logger
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
from pynguin.analyses.module import ModuleTestCluster
from pynguin.ga.algorithms.randomalgorithm import RandomAlgorithm
from pynguin.testcase.execution import ExecutionResult, TestCaseExecutor
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericCallableAccessibleObject,
)
from tests.testcase._builders import int_stmt, make_test_case

if TYPE_CHECKING:
    from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def executor():
    return MagicMock(TestCaseExecutor)


def test_generate_sequences(executor, monkeypatch):
    config.configuration.stopping.maximum_search_time = 1
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    assert isinstance(algorithm, RandomAlgorithm)
    algorithm._logger = logger
    monkeypatch.setattr(algorithm, "generate_sequence", lambda _t, _f: None)
    test_cases = algorithm.generate_tests()
    assert test_cases.size() == 0


def test_generate_sequences_exception(executor, monkeypatch):
    def raise_exception(*_):
        raise GenerationException("Exception Test")

    def _combine_current_individual(*_):
        chromosome = MagicMock(tsc.TestSuiteChromosome)
        chromosome.get_fitness.return_value = 1.0
        return chromosome

    config.configuration.stopping.maximum_search_time = 1
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    assert isinstance(algorithm, RandomAlgorithm)
    algorithm._logger = logger
    monkeypatch.setattr(algorithm, "_combine_current_individual", _combine_current_individual)
    monkeypatch.setattr(algorithm, "generate_sequence", raise_exception)
    algorithm.generate_tests()
    assert any(
        call.args and "Generate test case failed with exception" in str(call.args[0])
        for call in logger.method_calls
    )


def test_random_test_cases_no_bounds(executor):
    config.configuration.algorithm = config.Algorithm.RANDOM
    logger = MagicMock(Logger)
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, MagicMock(ModuleTestCluster)
    ).get_search_algorithm()
    algorithm._logger = logger
    config.configuration.random.max_sequences_combined = 0
    config.configuration.random.max_sequence_length = 0
    tc_1 = make_test_case(int_stmt("var_0", 0))
    tc_2 = make_test_case(int_stmt("var_0", 0), int_stmt("var_1", 1))
    assert isinstance(algorithm, RandomAlgorithm)
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
    tc_1 = make_test_case(int_stmt("var_0", 0))
    tc_2 = make_test_case(int_stmt("var_0", 0), int_stmt("var_1", 1))
    assert isinstance(algorithm, RandomAlgorithm)
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
    assert isinstance(algorithm, RandomAlgorithm)
    result = algorithm._random_public_method(cast("OrderedSet[GenericAccessibleObject]", outs))
    assert result in {out_0, out_2}


def test_generate_sequence_no_objects_under_test(executor):
    config.configuration.algorithm = config.Algorithm.RANDOM
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, test_cluster
    ).get_search_algorithm()
    assert isinstance(algorithm, RandomAlgorithm)
    with pytest.raises(GenerationException):
        algorithm.generate_sequence(
            tsc.TestSuiteChromosome(),
            tsc.TestSuiteChromosome(),
        )


@pytest.mark.parametrize("has_exceptions", [pytest.param(True), pytest.param(False)])
def test_generate_sequence(has_exceptions, executor, monkeypatch):
    config.configuration.algorithm = config.Algorithm.RANDOM
    exec_result = MagicMock(ExecutionResult)
    exec_result.timeout = False
    exec_result.has_test_exceptions.return_value = has_exceptions
    executor.execute.return_value = exec_result
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.accessible_objects_under_test = {MagicMock(GenericCallableAccessibleObject)}
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, test_cluster
    ).get_search_algorithm()
    assert isinstance(algorithm, RandomAlgorithm)
    algorithm.test_factory = MagicMock()
    monkeypatch.setattr(algorithm, "_random_public_method", lambda _: MagicMock())
    monkeypatch.setattr(algorithm, "_random_test_cases", lambda _: [])

    passing = tsc.TestSuiteChromosome()
    failing = tsc.TestSuiteChromosome()
    algorithm.generate_sequence(passing, failing)

    if has_exceptions:
        assert failing.size() == 1
        assert passing.size() == 0
    else:
        assert passing.size() == 1
        assert failing.size() == 0


def test_generate_sequence_duplicate(executor, monkeypatch):
    config.configuration.algorithm = config.Algorithm.RANDOM
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.accessible_objects_under_test = {MagicMock(GenericCallableAccessibleObject)}
    algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, test_cluster
    ).get_search_algorithm()
    assert isinstance(algorithm, RandomAlgorithm)
    algorithm.test_factory = MagicMock()
    monkeypatch.setattr(algorithm, "_random_public_method", lambda _: MagicMock())
    monkeypatch.setattr(algorithm, "_random_test_cases", lambda _: [])

    # The generated sequence is an empty test case; seed an identical one so the
    # duplicate check discards it before execution.
    passing = tsc.TestSuiteChromosome()
    existing = tcc.TestCaseChromosome(tc.TestCase(), algorithm.test_factory)
    passing.add_test_case_chromosome(existing)
    failing = tsc.TestSuiteChromosome()

    algorithm.generate_sequence(passing, failing)

    executor.execute.assert_not_called()
    assert passing.size() == 1
    assert failing.size() == 0
