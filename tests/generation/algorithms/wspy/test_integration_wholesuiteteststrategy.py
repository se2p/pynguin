#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
from pynguin.testcase.execution.executiontracer import ExecutionTracer
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
    config.INSTANCE.module_name = module_name
    config.INSTANCE.population = 3
    config.INSTANCE.min_initial_tests = 1
    config.INSTANCE.max_initial_tests = 1
    logger = MagicMock(Logger)
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation.
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        algorithm = WholeSuiteTestStrategy(
            executor, TestClusterGenerator(module_name).generate_cluster()
        )
        algorithm._logger = logger
        test_cases = algorithm.generate_tests()
        assert test_cases.size() >= 0
