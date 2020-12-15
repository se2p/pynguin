#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import itertools
from logging import Logger
from typing import Callable
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.testfactory as tf
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.mark.parametrize(
    "algorithm_to_run,module_name",
    itertools.product(
        [RandomTestStrategy],
        [
            "tests.fixtures.examples.basket",
            "tests.fixtures.examples.dummies",
            "tests.fixtures.examples.exceptions",
            "tests.fixtures.examples.monkey",
            "tests.fixtures.examples.triangle",
            "tests.fixtures.examples.type_inference",
            "tests.fixtures.examples.impossible",
            "tests.fixtures.examples.difficult",
            "tests.fixtures.examples.queue",
        ],
    ),
)
def test_integrate_randoopy(algorithm_to_run: Callable, module_name: str):
    config.INSTANCE.budget = 1
    config.INSTANCE.module_name = module_name
    logger = MagicMock(Logger)
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation.
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = TestClusterGenerator(module_name).generate_cluster()
        test_factory = tf.TestFactory(cluster)
        algorithm = algorithm_to_run(executor, cluster, test_factory, MagicMock())
        algorithm._logger = logger
        test_cases = algorithm.generate_tests()
        assert test_cases.size() >= 0
