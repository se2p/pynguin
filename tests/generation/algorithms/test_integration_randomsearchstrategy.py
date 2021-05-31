#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import itertools
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
    "module_name, algorithm",
    itertools.product(
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
        [
            config.Algorithm.RANDOM_TEST_SUITE_SEARCH,
            config.Algorithm.RANDOM_TEST_CASE_SEARCH,
        ],
    ),
)
def test_integrate_randomsearch(module_name: str, algorithm):
    # TODO(fk) reduce direct dependencies to config.INSTANCE
    config.configuration.algorithm = algorithm
    config.configuration.stopping.budget = 1
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.min_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    logger = MagicMock(Logger)
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation.
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = TestClusterGenerator(module_name).generate_cluster()
        search_algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        search_algorithm._logger = logger
        test_cases = search_algorithm.generate_tests()
        assert test_cases.size() >= 0
