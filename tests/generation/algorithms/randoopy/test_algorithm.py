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
import importlib
import inspect
from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.generation.algorithms.randoopy.algorithm import RandomGenerationAlgorithm
from pynguin.generation.executor import Executor
from pynguin.generation.symboltable import SymbolTable
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.recorder import CoverageRecorder


@pytest.fixture
def recorder():
    return MagicMock(CoverageRecorder)


@pytest.fixture
def executor():
    return MagicMock(Executor)


@pytest.fixture
def symbol_table():
    return MagicMock(SymbolTable)


def _inspect_member(member):
    try:
        return (
            inspect.isclass(member)
            or inspect.ismethod(member)
            or inspect.isfunction(member)
        )
    except BaseException:
        return None


def test_generate_sequences(recorder, executor, configuration_mock, symbol_table):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm._generate_sequence = lambda t, f, o: None
    test_cases, failing_test_cases = algorithm.generate_sequences(1, [])
    assert test_cases == []
    assert failing_test_cases == []
    assert len(logger.method_calls) == 7


def test_generate_sequences_exception(
    recorder, executor, configuration_mock, symbol_table
):
    def raise_exception(*args):
        raise GenerationException("Exception Test")

    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm._generate_sequence = raise_exception
    algorithm.generate_sequences(1, [])
    assert "Generate test case failed with exception" in logger.method_calls[3].args[0]


def test_find_objects_under_test(recorder, executor, configuration_mock, symbol_table):
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    result = algorithm._find_objects_under_test(
        [importlib.import_module("tests.fixtures.examples.triangle")]
    )
    assert len(result) == 2


def test_random_public_method_one_object_under_test(
    recorder, executor, configuration_mock, symbol_table
):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    result = algorithm._random_public_method(
        [importlib.import_module("tests.fixtures.examples.triangle")]
    )
    assert result


def test_random_public_method_private_object_under_test(
    recorder, executor, configuration_mock, symbol_table
):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    with pytest.raises(GenerationException) as exception:
        algorithm._random_public_method(
            [importlib.import_module("tests.fixtures.examples.private_methods")]
        )
    assert (
        str(exception.value) == "tests.fixtures.examples.private_methods has no public "
        "callables."
    )


def test_random_test_cases_no_bounds(
    recorder, executor, configuration_mock, symbol_table
):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    algorithm._configuration.max_sequences_combined = 0
    algorithm._configuration.max_sequence_length = 0
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    result = algorithm._random_test_cases([tc_1, tc_2])
    assert 0 <= len(result) <= 2


def test_random_test_cases_with_bounds(
    recorder, executor, configuration_mock, symbol_table
):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    algorithm._configuration.max_sequences_combined = 2
    algorithm._configuration.max_sequence_length = 2
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    result = algorithm._random_test_cases([tc_1, tc_2])
    assert 0 <= len(result) <= 1


def test_random_values_for_function_with_type_annotation(
    recorder, executor, configuration_mock, symbol_table
):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    callable_ = algorithm._random_public_method(
        [importlib.import_module("tests.fixtures.examples.triangle")]
    )
    test_cases = [MagicMock(tc.TestCase)]
    result = algorithm._random_values(test_cases, callable_)
    assert len(result) == 3
    assert str(result[0][1]) == "x: int"
    assert str(result[1][1]) == "y: int"
    assert str(result[2][1]) == "z: int"
