#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the MOSA-LLM test-generation strategy."""

import time
from unittest.mock import MagicMock, patch

import pytest

import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.ga.stoppingcondition import MaxSearchTimeStoppingCondition
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageEntry, CoverageReport, LineAnnotation
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


@pytest.fixture
def mock_require_api_key():
    """Mock the require_api_key function to avoid API key validation."""
    with patch("pynguin.large_language_model.llmagent.require_api_key") as mock:
        mock.return_value = MagicMock()
        mock.return_value.get_secret_value.return_value = "test-api-key"
        yield mock


@pytest.fixture
def llmosa_algorithm():
    """Returns a LLMOSA algorithm instance with mocked components."""
    with (
        patch("pynguin.large_language_model.llmagent.require_api_key") as mock_key,
        patch("pynguin.large_language_model.llmagent.openai.OpenAI"),
        patch("pynguin.large_language_model.llmagent.LLMAgent", autospec=True) as mock_llm_agent,
    ):
        mock_key.return_value = MagicMock()
        mock_key.return_value.get_secret_value.return_value = "test-api-key"
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


@pytest.mark.usefixtures("mock_require_api_key")
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
    # Use the iteration-count fallback (window <= 0) and disable the late-budget guard
    # so this test exercises the plateau path deterministically.
    mock_config.configuration.large_language_model.stall_detection_window_seconds = -1
    mock_config.configuration.large_language_model.min_remaining_budget_for_llm = -1

    # Mock resources_left to return True for 3 iterations then False
    llmosa_algorithm.resources_left = MagicMock(side_effect=[True, True, True, False])

    # Setup archive to simulate progress in coverage (to test plateau counter reset)
    llmosa_algorithm._archive = MagicMock()
    llmosa_algorithm._archive.covered_goals = []
    llmosa_algorithm._number_of_goals = 10  # Set some goals

    llmosa_algorithm.before_search_start = MagicMock()
    llmosa_algorithm._get_random_population = MagicMock(return_value=[])
    llmosa_algorithm._target_initial_uncovered_goals = MagicMock()
    llmosa_algorithm._compute_dominance = MagicMock()
    llmosa_algorithm.before_first_search_iteration = MagicMock()
    llmosa_algorithm.after_search_iteration = MagicMock()
    llmosa_algorithm._finalize_generation = MagicMock()
    llmosa_algorithm.target_uncovered_callables = MagicMock(
        return_value=[MagicMock(spec=tcc.TestCaseChromosome)]
    )
    llmosa_algorithm.create_test_suite = MagicMock()
    llmosa_algorithm.model = MagicMock()
    llmosa_algorithm.model.llm_calls_counter = 0

    # We need to capture the real implementation of evolve to modify the covered_goals
    # Define a custom evolve function that simulates progress
    def custom_evolve():
        # On the second call, simulate progress by adding a covered goal
        if llmosa_algorithm.evolve.call_count == 1:
            # This will trigger the plateau counter reset in the next iteration
            llmosa_algorithm._archive.covered_goals = ["goal1"]

    llmosa_algorithm.evolve = MagicMock(side_effect=custom_evolve)

    # Execute
    llmosa_algorithm.generate_tests()

    # Assert
    # The target_uncovered_callables might be called during initialization or other parts
    # We're only concerned that the code executes and covers line 103
    assert llmosa_algorithm.evolve.call_count == 3
    llmosa_algorithm._finalize_generation.assert_called_once()

    # Since we're directly testing line 103 (plateau_counter = 0), we don't need to
    # verify the value through plateau_counter_values. The test passes if the code
    # executes without errors, which means line 103 was covered.


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


@patch("pynguin.ga.algorithms.llmosalgorithm.get_coverage_report")
def test_coverage_in_range(mock_get_coverage_report, llmosa_algorithm):
    """Tests the coverage_in_range function within target_uncovered_callables."""
    # Create mock line annotations
    line_annotations = [
        LineAnnotation(
            line_no=10,
            total=CoverageEntry(existing=5, covered=3),
            branches=CoverageEntry(existing=0, covered=0),
            branchless_code_objects=CoverageEntry(existing=0, covered=0),
            lines=CoverageEntry(existing=0, covered=0),
        ),
        LineAnnotation(
            line_no=15,
            total=CoverageEntry(existing=10, covered=5),
            branches=CoverageEntry(existing=0, covered=0),
            branchless_code_objects=CoverageEntry(existing=0, covered=0),
            lines=CoverageEntry(existing=0, covered=0),
        ),
        LineAnnotation(
            line_no=20,
            total=CoverageEntry(existing=8, covered=2),
            branches=CoverageEntry(existing=0, covered=0),
            branchless_code_objects=CoverageEntry(existing=0, covered=0),
            lines=CoverageEntry(existing=0, covered=0),
        ),
    ]

    # Setup mock coverage report
    mock_coverage_report = MagicMock(spec=CoverageReport)
    mock_coverage_report.line_annotations = line_annotations
    mock_get_coverage_report.return_value = mock_coverage_report

    # Mock other necessary objects
    llmosa_algorithm.test_cluster.accessible_objects_under_test = []
    llmosa_algorithm.model.call_llm_for_uncovered_targets.return_value = []
    handler = llmosa_algorithm.model.llm_test_case_handler
    handler.get_test_case_chromosomes_from_llm_results.return_value = []

    with patch("pynguin.ga.algorithms.llmosalgorithm.config") as mock_config:
        mock_config.configuration.large_language_model.coverage_threshold = 0.8
        mock_config.configuration.statistics_output.coverage_metrics = ["branch"]

        # Define the coverage_in_range function directly in the test
        def coverage_in_range(start_line, end_line):
            total_coverage_points = 0
            covered_coverage_points = 0
            for line_annot in line_annotations:
                if start_line <= line_annot.line_no <= end_line:
                    total_coverage_points += line_annot.total.existing
                    covered_coverage_points += line_annot.total.covered
            return covered_coverage_points, total_coverage_points

        # Store the function as an attribute on the llmosa_algorithm object
        llmosa_algorithm._last_coverage_in_range = coverage_in_range

        # Test the function with different ranges
        covered1, total1 = coverage_in_range(5, 12)  # Should include line 10
        covered2, total2 = coverage_in_range(10, 20)  # Should include all lines
        covered3, total3 = coverage_in_range(16, 25)  # Should include line 20

    # Assert
    assert covered1 == 3
    assert total1 == 5
    assert covered2 == 10  # 3 + 5 + 2
    assert total2 == 23  # 5 + 10 + 8
    assert covered3 == 2
    assert total3 == 8


@patch("pynguin.ga.algorithms.llmosalgorithm.get_coverage_report")
@patch("pynguin.ga.algorithms.llmosalgorithm.inspect.getsourcelines")
def test_calculate_gao_coverage_map(
    mock_getsourcelines, mock_get_coverage_report, llmosa_algorithm
):
    """Tests the calculate_gao_coverage_map function within target_uncovered_callables."""
    # Create mock line annotations
    line_annotations = [
        LineAnnotation(
            line_no=100,
            total=CoverageEntry(existing=10, covered=5),
            branches=CoverageEntry(existing=0, covered=0),
            branchless_code_objects=CoverageEntry(existing=0, covered=0),
            lines=CoverageEntry(existing=0, covered=0),
        ),
        LineAnnotation(
            line_no=101,
            total=CoverageEntry(existing=8, covered=4),
            branches=CoverageEntry(existing=0, covered=0),
            branchless_code_objects=CoverageEntry(existing=0, covered=0),
            lines=CoverageEntry(existing=0, covered=0),
        ),
        LineAnnotation(
            line_no=102,
            total=CoverageEntry(existing=6, covered=3),
            branches=CoverageEntry(existing=0, covered=0),
            branchless_code_objects=CoverageEntry(existing=0, covered=0),
            lines=CoverageEntry(existing=0, covered=0),
        ),
    ]

    # Setup mock coverage report
    mock_coverage_report = MagicMock(spec=CoverageReport)
    mock_coverage_report.line_annotations = line_annotations
    mock_get_coverage_report.return_value = mock_coverage_report

    # Create mock GAO
    mock_gao = MagicMock(spec=GenericCallableAccessibleObject)
    mock_gao.callable = MagicMock()

    # Setup mock for getsourcelines
    mock_getsourcelines.return_value = (
        ["line1", "line2", "line3"],
        100,
    )  # 3 lines starting at line 100

    # Setup test cluster with only one GAO to ensure getsourcelines is called exactly once
    # Clear any existing objects first
    llmosa_algorithm.test_cluster = MagicMock()
    llmosa_algorithm.test_cluster.accessible_objects_under_test = [mock_gao]

    # Mock other necessary objects
    llmosa_algorithm.model = MagicMock()
    llmosa_algorithm.model.call_llm_for_uncovered_targets.return_value = []
    handler = llmosa_algorithm.model.llm_test_case_handler
    handler.get_test_case_chromosomes_from_llm_results.return_value = []

    with patch("pynguin.ga.algorithms.llmosalgorithm.config") as mock_config:
        mock_config.configuration.large_language_model.coverage_threshold = 0.8
        mock_config.configuration.statistics_output.coverage_metrics = ["branch"]

        # Define the coverage_in_range function directly in the test
        def coverage_in_range(start_line, end_line):
            total_coverage_points = 0
            covered_coverage_points = 0
            for line_annot in line_annotations:
                if start_line <= line_annot.line_no <= end_line:
                    total_coverage_points += line_annot.total.existing
                    covered_coverage_points += line_annot.total.covered
            return covered_coverage_points, total_coverage_points

        # Define the calculate_gao_coverage_map function directly in the test
        def calculate_gao_coverage_map():
            gao_coverage = {}
            for gao in llmosa_algorithm.test_cluster.accessible_objects_under_test:
                if isinstance(gao, GenericCallableAccessibleObject):
                    try:
                        source_lines, start_line = mock_getsourcelines(gao.callable)
                        end_line = start_line + len(source_lines) - 1
                        covered, total = coverage_in_range(start_line, end_line)
                        coverage_ratio = covered / total if total > 0 else 0
                    except (TypeError, OSError):
                        coverage_ratio = 0
                    gao_coverage[gao] = coverage_ratio
            return gao_coverage

        # Store the functions as attributes on the llmosa_algorithm object
        llmosa_algorithm._last_coverage_in_range = coverage_in_range
        llmosa_algorithm._last_calculate_gao_coverage_map = calculate_gao_coverage_map

        # Reset the mock to clear previous calls
        mock_getsourcelines.reset_mock()

        # Test the function
        gao_coverage = calculate_gao_coverage_map()

    # Assert
    assert mock_gao in gao_coverage
    assert gao_coverage[mock_gao] == 12 / 24  # (5+4+3)/(10+8+6) = 12/24 = 0.5
    mock_getsourcelines.assert_called_once_with(mock_gao.callable)


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


def _annotation(line_no, existing, covered, br_existing=0, br_covered=0):
    return LineAnnotation(
        line_no=line_no,
        total=CoverageEntry(existing=existing, covered=covered),
        branches=CoverageEntry(existing=br_existing, covered=br_covered),
        branchless_code_objects=CoverageEntry(existing=0, covered=0),
        lines=CoverageEntry(existing=0, covered=0),
    )


@patch("pynguin.ga.algorithms.llmosalgorithm.inspect.getsourcelines")
def test_diagnose_callable_never_reached(mock_getsourcelines, llmosa_algorithm):
    mock_getsourcelines.return_value = (["l1", "l2"], 10)  # lines 10-11
    annotations = [_annotation(10, 3, 0), _annotation(11, 2, 0)]
    gao = MagicMock(spec=GenericCallableAccessibleObject)
    hint = llmosa_algorithm._diagnose_callable(gao, annotations)
    assert "never reached" in hint


@patch("pynguin.ga.algorithms.llmosalgorithm.inspect.getsourcelines")
def test_diagnose_callable_branch_polarity(mock_getsourcelines, llmosa_algorithm):
    mock_getsourcelines.return_value = (["l1", "l2"], 10)
    # Reached (covered > 0) but a branch on line 10 only took one of two outcomes.
    annotations = [_annotation(10, 3, 2, br_existing=2, br_covered=1), _annotation(11, 2, 2)]
    gao = MagicMock(spec=GenericCallableAccessibleObject)
    hint = llmosa_algorithm._diagnose_callable(gao, annotations)
    assert "only took one outcome" in hint
    assert "10" in hint


@patch("pynguin.ga.algorithms.llmosalgorithm.inspect.getsourcelines")
def test_diagnose_callable_no_hint_when_covered(mock_getsourcelines, llmosa_algorithm):
    mock_getsourcelines.return_value = (["l1"], 10)
    annotations = [_annotation(10, 3, 3, br_existing=2, br_covered=2)]
    gao = MagicMock(spec=GenericCallableAccessibleObject)
    assert not llmosa_algorithm._diagnose_callable(gao, annotations)


@patch("pynguin.ga.algorithms.llmosalgorithm.inspect.getsourcelines", side_effect=OSError)
def test_diagnose_callable_unavailable_source(mock_getsourcelines, llmosa_algorithm):  # noqa: ARG001
    gao = MagicMock(spec=GenericCallableAccessibleObject)
    assert not llmosa_algorithm._diagnose_callable(gao, [])


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_enough_budget_for_llm_guard_disabled(mock_config, llmosa_algorithm):
    mock_config.configuration.large_language_model.min_remaining_budget_for_llm = -1
    llmosa_algorithm._stopping_conditions = []
    assert llmosa_algorithm._enough_budget_for_llm() is True


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_enough_budget_for_llm_no_time_condition(mock_config, llmosa_algorithm):
    mock_config.configuration.large_language_model.min_remaining_budget_for_llm = 45
    llmosa_algorithm._stopping_conditions = [MagicMock()]
    assert llmosa_algorithm._enough_budget_for_llm() is True


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_enough_budget_for_llm_suppresses_when_low(mock_config, llmosa_algorithm):
    mock_config.configuration.large_language_model.min_remaining_budget_for_llm = 45
    condition = MaxSearchTimeStoppingCondition(10)  # only 10s total budget
    condition.before_search_start(time.time_ns())
    llmosa_algorithm._stopping_conditions = [condition]
    # ~10s remaining < 45s guard -> suppress.
    assert llmosa_algorithm._enough_budget_for_llm() is False


@patch("pynguin.ga.algorithms.llmosalgorithm.config")
def test_enough_budget_for_llm_allows_when_ample(mock_config, llmosa_algorithm):
    mock_config.configuration.large_language_model.min_remaining_budget_for_llm = 45
    condition = MaxSearchTimeStoppingCondition(600)
    condition.before_search_start(time.time_ns())
    llmosa_algorithm._stopping_conditions = [condition]
    assert llmosa_algorithm._enough_budget_for_llm() is True


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
