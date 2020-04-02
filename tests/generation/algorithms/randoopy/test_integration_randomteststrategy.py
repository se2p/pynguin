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
import itertools
from logging import Logger
from typing import Callable
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.generation.algorithms.randoopy.randomtestmonkeytypestrategy import (
    RandomTestMonkeyTypeStrategy,
)
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.mark.parametrize(
    "algorithm_to_run,module_name",
    itertools.product(
        [RandomTestStrategy, RandomTestMonkeyTypeStrategy],
        [
            "tests.fixtures.accessibles.accessible",
            "tests.fixtures.cluster.dependency",
            "tests.fixtures.cluster.no_dependencies",
            "tests.fixtures.cluster.simple_dependencies",
            "tests.fixtures.examples.basket",
            "tests.fixtures.examples.dummies",
            "tests.fixtures.examples.exceptions",
            "tests.fixtures.examples.monkey",
            "tests.fixtures.examples.triangle",
            "tests.fixtures.examples.type_inference",
        ],
    ),
)
def test_integrate_randoopy(algorithm_to_run: Callable, module_name):
    config.INSTANCE.budget = 1
    config.INSTANCE.measure_coverage = False
    logger = MagicMock(Logger)
    executor = TestCaseExecutor()
    algorithm = algorithm_to_run(
        executor, TestClusterGenerator(module_name).generate_cluster()
    )
    algorithm._logger = logger
    test_cases, failing_test_cases = algorithm.generate_sequences()
    assert test_cases.size() >= 0
    assert failing_test_cases.size() >= 0
