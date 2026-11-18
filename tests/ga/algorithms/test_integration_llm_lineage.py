#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for lineage tracking, blending and lineage elitism of LLM tests."""

from __future__ import annotations

import importlib
from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
from pynguin.analyses.module import generate_test_cluster
from pynguin.ga.algorithms.abstractmosaalgorithm import AbstractMOSAAlgorithm
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.large_language_model.llmtestcasehandler import LLMGeneration
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

MODULE_NAME = "tests.fixtures.examples.difficult"
ITERATIONS = 6
INJECTED = 3


def _base_evolve(self) -> None:
    super(LLMOSAAlgorithm, self).evolve()


def _base_breed(self, _factory=None):
    actual_factory = getattr(
        self._chromosome_factory, "test_case_chromosome_factory", self._chromosome_factory
    )
    return AbstractMOSAAlgorithm._breed_next_generation(self, actual_factory)


def _run(algorithm_kind, subject_properties, on_iteration=None):
    """Runs an LLM algorithm that gets INJECTED test cases before its first generation.

    The LLM is never queried: the query strategy's poll() delivers random test cases
    once, as if an asynchronous LLM query had completed.

    Returns:
        The algorithm and the code of its final population.
    """
    config.configuration.algorithm = algorithm_kind
    config.configuration.module_name = MODULE_NAME
    config.configuration.stopping.maximum_iterations = ITERATIONS
    config.configuration.search_algorithm.population = 6
    config.configuration.large_language_model.call_llm_for_uncovered_targets = False
    config.configuration.large_language_model.call_llm_on_stall_detection = False
    config.configuration.large_language_model.hybrid_initial_population = False
    randomness.RNG.seed(42)
    with install_import_hook(MODULE_NAME, subject_properties):
        with subject_properties.instrumentation_tracer:
            importlib.reload(importlib.import_module(MODULE_NAME))
        executor = TestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(MODULE_NAME)
        algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        assert isinstance(algorithm, LLMOSAAlgorithm)
        algorithm._logger = MagicMock(Logger)
        algorithm.model = MagicMock()
        deliveries = [[algorithm._get_random_chromosome() for _ in range(INJECTED)]]
        algorithm._llm_query_strategy.poll = lambda: (
            LLMGeneration(chromosomes=deliveries.pop()) if deliveries else None
        )
        if on_iteration is not None:
            original = algorithm.after_search_iteration

            def after_search_iteration(best):
                on_iteration(algorithm)
                original(best)

            algorithm.after_search_iteration = after_search_iteration
        algorithm.generate_tests()
        population = [chromosome.test_case.to_code() for chromosome in algorithm._population]
    return algorithm, population


@pytest.mark.parametrize("algorithm_kind", [config.Algorithm.LLMOSA, config.Algorithm.LLDYNAMOSA])
def test_defaults_behave_like_the_search_without_lineage_hooks(
    algorithm_kind, subject_properties, monkeypatch
):
    algorithm, population = _run(algorithm_kind, subject_properties)
    rng_state = randomness.RNG.getstate()
    assert algorithm._lineage.statistics([])[RuntimeVariable.LLMInjectedTests] == INJECTED

    with monkeypatch.context() as patched:
        patched.setattr(LLMOSAAlgorithm, "evolve", _base_evolve)
        patched.setattr(LLMOSAAlgorithm, "_breed_next_generation", _base_breed)
        patched.setattr(
            LLMOSAAlgorithm, "_register_injected_chromosomes", lambda _, chromosomes: chromosomes
        )
        _, baseline_population = _run(algorithm_kind, subject_properties)

    assert population == baseline_population
    assert rng_state == randomness.RNG.getstate()


@pytest.mark.parametrize("algorithm_kind", [config.Algorithm.LLMOSA, config.Algorithm.LLDYNAMOSA])
def test_lineage_elitism_keeps_every_injected_lineage_for_n_generations(
    algorithm_kind, subject_properties
):
    generations = 3
    config.configuration.search_algorithm.llm_lineage_elitism_generations = generations
    config.configuration.search_algorithm.llm_lineage_elitism_max_fraction = 1.0
    config.configuration.search_algorithm.llm_blend_mutants = 1
    config.configuration.search_algorithm.llm_blend_tournament_crossovers = 1
    config.configuration.search_algorithm.llm_blend_goal_crossovers = 1
    present_per_generation: list[set[int]] = []

    def record(algorithm):
        present_per_generation.append(algorithm._lineage.roots_in(algorithm._population))

    algorithm, _ = _run(algorithm_kind, subject_properties, on_iteration=record)

    roots = set(range(INJECTED))
    assert len(present_per_generation) >= generations
    for present in present_per_generation[:generations]:
        assert roots <= present
    statistics = algorithm._lineage.statistics(algorithm._population)
    assert statistics[RuntimeVariable.LLMLineageElitismReinsertions] > 0
    assert sum(value for variable, value in statistics.items() if "Bred" in variable.name) > 0
