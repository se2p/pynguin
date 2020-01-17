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
from logging import Logger
from unittest.mock import MagicMock

import pytest

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


def test_generate_sequences(recorder, executor, configuration_mock, symbol_table):
    logger = MagicMock(Logger)
    algorithm = RandomGenerationAlgorithm(
        recorder, executor, configuration_mock, symbol_table
    )
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm._generate_sequence = lambda t, f, a, o: None
    test_cases, failing_test_cases = algorithm.generate_sequences(1, [])
    assert test_cases == []
    assert failing_test_cases == []
    assert len(logger.method_calls) == 8


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
