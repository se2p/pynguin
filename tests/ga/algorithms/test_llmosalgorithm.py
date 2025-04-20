#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the MOSA-LLM test-generation strategy."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat

from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


@pytest.fixture
def mock_set_api_key():
    """Mock the set_api_key function to avoid API key validation."""
    with patch("pynguin.large_language_model.llmagent.set_api_key") as mock:
        yield mock


@pytest.fixture
def llmosa_algorithm():
    """Returns a LLMOSA algorithm instance with mocked components."""
    with (
        patch("pynguin.large_language_model.llmagent.set_api_key"),
        patch("pynguin.large_language_model.llmagent.LLMAgent", autospec=True) as mock_llm_agent,
    ):
        mock_model = MagicMock()
        mock_model.llm_calls_counter = 0
        mock_model.llm_test_case_handler = MagicMock()
        mock_model.call_llm_for_uncovered_targets = MagicMock(return_value="test response")
        mock_llm_agent.return_value = mock_model

        algorithm = LLMOSAAlgorithm()
        # Replace the real LLMAgent with our mock
        algorithm.model = mock_model

        algorithm._logger = MagicMock()
        algorithm._archive = MagicMock()
        algorithm._test_case_fitness_functions = [MagicMock(), MagicMock()]
        algorithm._test_suite_coverage_functions = [MagicMock()]
        algorithm._chromosome_factory = MagicMock()
        algorithm._population = []
        algorithm.executor = MagicMock()
        algorithm.test_cluster = MagicMock()
        algorithm._test_factory = MagicMock()
        algorithm._selection_function = MagicMock()
        algorithm._crossover_function = MagicMock()
        algorithm._ranking_function = MagicMock()
        return algorithm


@pytest.mark.usefixtures("mock_set_api_key")
def test_initialization():
    """Tests the initialization of the LLMOSA algorithm."""
    # We need to patch the LLMAgent class to avoid API key validation
    with patch.object(LLMAgent, "__init__", return_value=None):
        # Execute
        algorithm = LLMOSAAlgorithm()

        # Assert
        assert isinstance(algorithm, LLMOSAAlgorithm)
        assert hasattr(algorithm, "model")
        assert isinstance(algorithm.model, LLMAgent)


def test_target_initial_uncovered_goals_no_llm_call(llmosa_algorithm):
    """Tests that no LLM call is made when coverage is 1.0."""
    # Setup
    test_suite = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite.get_coverage.return_value = 1.0
    llmosa_algorithm.create_test_suite = MagicMock(return_value=test_suite)

    # Execute
    llmosa_algorithm._target_initial_uncovered_goals()

    # Assert
    llmosa_algorithm.model.call_llm_for_uncovered_targets.assert_not_called()


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_target_initial_uncovered_goals_with_llm_call(mock_config, llmosa_algorithm):
    """Tests that LLM call is made when coverage is less than 1.0 and config is set."""
    # Setup
    mock_config.configuration.large_language_model.call_llm_for_uncovered_targets = True
    test_suite_before = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite_before.get_coverage.return_value = 0.5
    test_suite_after = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite_after.get_coverage.return_value = 0.7

    llmosa_algorithm.create_test_suite = MagicMock(
        side_effect=[test_suite_before, test_suite_after]
    )
    llmosa_algorithm.target_uncovered_callables = MagicMock(
        return_value=[MagicMock(spec=tcc.TestCaseChromosome)]
    )

    # Execute
    with patch.object(stat, "track_output_variable") as mock_track:
        llmosa_algorithm._target_initial_uncovered_goals()

    # Assert
    llmosa_algorithm.target_uncovered_callables.assert_called_once()
    assert len(llmosa_algorithm._population) == 1
    llmosa_algorithm._archive.update.assert_called_once_with(llmosa_algorithm._population)
    mock_track.assert_any_call(RuntimeVariable.CoverageBeforeLLMCall, 0.5)
    mock_track.assert_any_call(RuntimeVariable.CoverageAfterLLMCall, 0.7)


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_generate_tests_with_llm_on_stall(mock_config, llmosa_algorithm):
    """Tests the generate_tests method with LLM intervention on stall detection."""
    # Setup
    mock_config.configuration.large_language_model.call_llm_on_stall_detection = True
    mock_config.configuration.large_language_model.max_llm_interventions = 2
    mock_config.configuration.large_language_model.max_plateau_len = 1

    llmosa_algorithm.resources_left = MagicMock(side_effect=[True, True, True, False])
    llmosa_algorithm._archive.covered_goals = []
    llmosa_algorithm.before_search_start = MagicMock()
    llmosa_algorithm._get_random_population = MagicMock(return_value=[])
    llmosa_algorithm._target_initial_uncovered_goals = MagicMock()
    llmosa_algorithm._compute_dominance = MagicMock()
    llmosa_algorithm.before_first_search_iteration = MagicMock()
    llmosa_algorithm.evolve = MagicMock()
    llmosa_algorithm.after_search_iteration = MagicMock()
    llmosa_algorithm._finalize_generation = MagicMock()
    llmosa_algorithm.target_uncovered_callables = MagicMock(
        return_value=[MagicMock(spec=tcc.TestCaseChromosome)]
    )

    # Execute
    llmosa_algorithm.generate_tests()

    # Assert
    assert llmosa_algorithm.target_uncovered_callables.call_count == 1
    assert llmosa_algorithm.evolve.call_count == 3
    llmosa_algorithm._finalize_generation.assert_called_once()


@patch("pynguin.ga.algorithms.llmosalgorithm.get_coverage_report")
def test_target_uncovered_callables(mock_get_coverage_report, llmosa_algorithm):
    """Tests the target_uncovered_callables method."""
    # Setup
    mock_coverage_report = MagicMock(spec=CoverageReport)
    mock_coverage_report.line_annotations = []
    mock_get_coverage_report.return_value = mock_coverage_report

    mock_gao = MagicMock(spec=GenericCallableAccessibleObject)
    llmosa_algorithm.test_cluster.accessible_objects_under_test = [mock_gao]

    # Setup mock for test case chromosomes
    test_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    handler = llmosa_algorithm.model.llm_test_case_handler
    handler.get_test_case_chromosomes_from_llm_results.return_value = [test_chromosome]

    with patch("pynguin.ga.algorithms.llmosalgorithm.config") as mock_config:
        mock_config.configuration.large_language_model.coverage_threshold = 0.8
        mock_config.configuration.statistics_output.coverage_metrics = ["branch"]

        # Execute
        result = llmosa_algorithm.target_uncovered_callables()

    # Assert
    assert len(result) == 1
    assert result[0] == test_chromosome
    llmosa_algorithm.model.call_llm_for_uncovered_targets.assert_called_once()
    handler = llmosa_algorithm.model.llm_test_case_handler
    handler.get_test_case_chromosomes_from_llm_results.assert_called_once()


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_get_random_population_hybrid(mock_config, llmosa_algorithm):
    """Tests the _get_random_population method with hybrid population enabled."""
    # Setup
    mock_config.configuration.large_language_model.hybrid_initial_population = True
    test_suite = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite.test_case_chromosomes = [MagicMock(spec=tcc.TestCaseChromosome)]
    llmosa_algorithm._chromosome_factory.get_chromosome.return_value = test_suite

    # Execute
    result = llmosa_algorithm._get_random_population()

    # Assert
    assert result == test_suite.test_case_chromosomes
    llmosa_algorithm._chromosome_factory.get_chromosome.assert_called_once()


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_get_random_population_non_hybrid(mock_config, llmosa_algorithm):
    """Tests the _get_random_population method with hybrid population disabled."""
    # Setup
    mock_config.configuration.large_language_model.hybrid_initial_population = False
    mock_config.configuration.search_algorithm.population = 2

    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    factory = llmosa_algorithm._chromosome_factory.test_case_chromosome_factory
    factory.get_chromosome.return_value = chromosome

    # Execute
    result = llmosa_algorithm._get_random_population()

    # Assert
    assert len(result) == 2
    assert all(c == chromosome for c in result)
    assert (
        llmosa_algorithm._chromosome_factory.test_case_chromosome_factory.get_chromosome.call_count
        == 2
    )


def test_breed_next_generation(llmosa_algorithm):
    """Tests the _breed_next_generation method."""
    # Setup
    factory = MagicMock()

    # Execute
    patch_path = "pynguin.ga.algorithms.abstractmosaalgorithm.AbstractMOSAAlgorithm"
    with patch(f"{patch_path}._breed_next_generation") as mock_breed:
        llmosa_algorithm._breed_next_generation(factory)

    # Assert
    mock_breed.assert_called_once_with(
        llmosa_algorithm._chromosome_factory.test_case_chromosome_factory
    )
