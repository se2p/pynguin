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
import inspect
from logging import Logger
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.defaulttestcase as dtc
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


def _inspect_member(member):
    try:
        return (
            inspect.isclass(member)
            or inspect.ismethod(member)
            or inspect.isfunction(member)
        )
    except BaseException:
        return None


def test_generate_sequences(executor):
    config.INSTANCE.budget = 1
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor)
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm._generate_sequence = lambda t, f, o: None
    test_cases, failing_test_cases = algorithm.generate_sequences()
    assert test_cases == []
    assert failing_test_cases == []
    assert len(logger.method_calls) == 7


def test_generate_sequences_exception(executor):
    def raise_exception(*args):
        raise GenerationException("Exception Test")

    config.INSTANCE.budget = 1
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor)
    algorithm._logger = logger
    algorithm._find_objects_under_test = lambda x: x
    algorithm._generate_sequence = raise_exception
    algorithm.generate_sequences()
    assert "Generate test case failed with exception" in logger.method_calls[3].args[0]


def test_random_test_cases_no_bounds(executor):
    logger = MagicMock(Logger)
    algorithm = RandomTestStrategy(executor)
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
    algorithm = RandomTestStrategy(executor)
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
    algorithm = RandomTestStrategy(executor)
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
    algorithm = RandomTestStrategy(executor)
    test_cluster = MagicMock(TestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm._random_public_method = lambda x: None
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(MagicMock(stmt.Statement))
    algorithm._random_test_cases = lambda x: [test_case]
    with mock.patch(
        "pynguin.generation.algorithms.randoopy.randomteststrategy.testfactory"
    ) as m:
        algorithm._generate_sequence([dtc.DefaultTestCase()], [], test_cluster)
        m.append_generic_statement.assert_called_once()


def test_generate_sequence_duplicate(executor):
    algorithm = RandomTestStrategy(executor)
    test_cluster = MagicMock(TestCluster)
    test_cluster.accessible_objects_under_test = set()
    algorithm._random_public_method = lambda x: None
    test_case = dtc.DefaultTestCase()
    algorithm._random_test_cases = lambda x: [test_case]
    with mock.patch(
        "pynguin.generation.algorithms.randoopy.randomteststrategy.testfactory"
    ) as m:
        algorithm._generate_sequence([dtc.DefaultTestCase()], [], test_cluster)
        m.append_generic_statement.assert_called_once()
