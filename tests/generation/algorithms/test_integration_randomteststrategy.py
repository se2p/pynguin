#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.generation.generationalgorithmfactory as gaf
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.mark.parametrize(
    "module_name",
    [
        pytest.param("tests.fixtures.examples.basket"),
        pytest.param("tests.fixtures.examples.dummies"),
        pytest.param("tests.fixtures.examples.exceptions"),
        pytest.param("tests.fixtures.examples.monkey"),
        pytest.param("tests.fixtures.examples.triangle"),
        pytest.param("tests.fixtures.examples.type_inference"),
        pytest.param("tests.fixtures.examples.impossible"),
        pytest.param("tests.fixtures.examples.difficult"),
        pytest.param("tests.fixtures.examples.queue"),
    ],
)
def test_integrate_randoopy(module_name: str):
    config.INSTANCE.budget = 1
    config.INSTANCE.algorithm = config.Algorithm.RANDOM
    config.INSTANCE.module_name = module_name
    logger = MagicMock(Logger)
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation.
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = TestClusterGenerator(module_name).generate_cluster()
        algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        algorithm._logger = logger
        test_cases = algorithm.generate_tests()
        assert test_cases.size() >= 0
