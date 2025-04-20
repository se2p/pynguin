#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import itertools
import threading

from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf

from pynguin.analyses.module import generate_test_cluster
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import TestCaseExecutor


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
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.test_insertion_probability = 0.5
    config.configuration.search_algorithm.population = 3
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    logger = MagicMock(Logger)
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = generate_test_cluster(module_name)
        algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        algorithm._logger = logger
        test_cases = algorithm.generate_tests()
        best_individuals = algorithm._get_best_individuals()
        assert test_cases.size() >= 0
        assert len(best_individuals) >= 0
