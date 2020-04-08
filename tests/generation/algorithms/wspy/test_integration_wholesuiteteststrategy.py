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

import pynguin.configuration as config
from pynguin.generation.algorithms.wspy.wholesuiteteststrategy import (
    WholeSuiteTestStrategy,
)
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.mark.parametrize(
    "module_name",
    [
        "tests.fixtures.examples.basket",
        "tests.fixtures.examples.dummies",
        "tests.fixtures.examples.exceptions",
        "tests.fixtures.examples.monkey",
        "tests.fixtures.examples.triangle",
        "tests.fixtures.examples.impossible",
        "tests.fixtures.examples.difficult",
        "tests.fixtures.examples.queue",
    ],
)
def test_integrate_wspy(module_name: str):
    # TODO(fk) reduce direct dependencies to config.INSTANCE
    config.INSTANCE.budget = 1
    config.INSTANCE.measure_coverage = False
    config.INSTANCE.algorithm = config.Algorithm.WSPY
    config.INSTANCE.module_name = module_name
    config.INSTANCE.population = 3
    config.INSTANCE.min_initial_tests = 1
    config.INSTANCE.max_initial_tests = 1
    logger = MagicMock(Logger)
    with install_import_hook(
        config.INSTANCE.algorithm.use_instrumentation, module_name
    ):
        # Need to force reload in order to apply instrumentation.
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor()
        algorithm = WholeSuiteTestStrategy(
            executor, TestClusterGenerator(module_name).generate_cluster()
        )
        algorithm._logger = logger
        test_cases, failing_test_cases = algorithm.generate_sequences()
        assert test_cases.size() >= 0
        assert failing_test_cases.size() >= 0
