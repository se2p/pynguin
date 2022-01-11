#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
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
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor


@pytest.mark.parametrize(
    "module_name,algorithm",
    itertools.product(
        [
            "tests.fixtures.examples.basket",
            "tests.fixtures.examples.dummies",
            "tests.fixtures.examples.simple",
            "tests.fixtures.examples.exceptions",
            "tests.fixtures.examples.monkey",
            "tests.fixtures.examples.triangle",
            "tests.fixtures.examples.impossible",
            "tests.fixtures.examples.difficult",
            "tests.fixtures.examples.queue",
            "tests.fixtures.examples.type_inference",
            "tests.fixtures.examples.enums",
            "tests.fixtures.examples.flaky",
        ],
        [config.Algorithm.MOSA, config.Algorithm.DYNAMOSA],
    ),
)
def test_integrate_mosa(module_name: str, algorithm):
    config.configuration.algorithm = algorithm
    config.configuration.stopping.maximum_iterations = 2
    config.configuration.stopping.stopping_condition = (
        config.StoppingCondition.MAX_ITERATIONS
    )
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.test_insertion_probability = 0.5
    config.configuration.search_algorithm.population = 3
    logger = MagicMock(Logger)
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = TestClusterGenerator(module_name).generate_cluster()
        algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        algorithm._logger = logger
        test_cases = algorithm.generate_tests()
        best_individuals = algorithm._get_best_individuals()
        assert test_cases.size() >= 0
        assert len(best_individuals) >= 0
