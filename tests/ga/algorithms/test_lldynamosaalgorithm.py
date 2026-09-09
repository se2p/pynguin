#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the DynaMOSA-LLM test-generation strategy."""

from unittest.mock import MagicMock, patch

import pytest

import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.ga.algorithms.lldynamosaalgorithm import LLDynaMOSAAlgorithm
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.report import CoverageEntry, CoverageReport, LineAnnotation
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


@pytest.fixture
def mock_require_api_key():
    """Mock the require_api_key function to avoid API key validation."""
    with patch("pynguin.large_language_model.client.require_api_key") as mock:
        mock.return_value = MagicMock()
        mock.return_value.get_secret_value.return_value = "test-api-key"
        yield mock


@pytest.fixture
def lldynamosa_algorithm():
    """Returns a LLDynaMOSA algorithm instance with mocked components."""
    with (
        patch("pynguin.large_language_model.client.require_api_key") as mock_key,
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

        algorithm = LLDynaMOSAAlgorithm()
        # Replace the real LLMAgent with our mock
        algorithm.model = mock_model

        algorithm._logger = MagicMock()
        algorithm._archive = MagicMock()
        algorithm._goals_manager = MagicMock()
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


def test_initialization():
    """Tests that the LLDynaMOSA algorithm initializes through the full MRO chain."""
    with patch.object(LLMAgent, "__init__", return_value=None):
        algorithm = LLDynaMOSAAlgorithm()

        assert isinstance(algorithm, LLDynaMOSAAlgorithm)
        assert isinstance(algorithm, LLMOSAAlgorithm)
        assert isinstance(algorithm, DynaMOSAAlgorithm)
        assert hasattr(algorithm, "model")
        assert isinstance(algorithm.model, LLMAgent)
        assert algorithm._stall_intervention_count == 0
        assert algorithm._population == []


# ----------------------------------------------------------------------
# Inheritance wiring: LLDynaMOSAAlgorithm extends both LLMOSAAlgorithm and
# DynaMOSAAlgorithm. These tests check the method resolution order itself, not
# behaviour already covered by test_llmosalgorithm.py / test_dynamosaalgorithm.py.
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "method_name",
    [
        "__init__",
        "_enough_budget_for_llm",
        "_diagnose_callable",
        "_get_random_population",
        "_breed_next_generation",
    ],
)
def test_inherits_llmosa_methods_unchanged(method_name):
    """These methods are target-independent and should match LLMOSAAlgorithm's."""
    assert getattr(LLDynaMOSAAlgorithm, method_name) is getattr(LLMOSAAlgorithm, method_name)


def test_inherits_evolve_from_dynamosa_not_mosa():
    """Use DynaMOSAAlgorithm.evolve() to preserve dynamic-target behavior in the MRO."""
    assert LLDynaMOSAAlgorithm.evolve is DynaMOSAAlgorithm.evolve


@pytest.mark.parametrize(
    "method_name",
    [
        "generate_tests",
        "_target_initial_uncovered_goals",
        "_maybe_intervene_on_stall",
        "_eligible_gaos_for_targeting",
        "target_uncovered_callables",
    ],
)
def test_overrides_target_selection_methods(method_name):
    """Dynamic-target methods must be defined directly on LLDynaMOSAAlgorithm."""
    assert method_name in LLDynaMOSAAlgorithm.__dict__


def test_target_initial_uncovered_goals_no_llm_call(lldynamosa_algorithm):
    """Tests that no LLM call is made when coverage is 1.0."""
    test_suite = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite.get_coverage.return_value = 1.0
    lldynamosa_algorithm.create_test_suite = MagicMock(return_value=test_suite)

    lldynamosa_algorithm._target_initial_uncovered_goals()

    lldynamosa_algorithm.model.call_llm_for_uncovered_targets.assert_not_called()


@patch("pynguin.ga.algorithms.lldynamosaalgorithm.config")
def test_target_initial_uncovered_goals_with_llm_call(mock_config, lldynamosa_algorithm):
    """Tests that an LLM call updates the goals manager, not just the archive."""
    mock_config.configuration.large_language_model.call_llm_for_uncovered_targets = True
    test_suite_before = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite_before.get_coverage.return_value = 0.5
    test_suite_after = MagicMock(spec=tsc.TestSuiteChromosome)
    test_suite_after.get_coverage.return_value = 0.7

    lldynamosa_algorithm.create_test_suite = MagicMock(
        side_effect=[test_suite_before, test_suite_after]
    )
    lldynamosa_algorithm.target_uncovered_callables = MagicMock(
        return_value=[MagicMock(spec=tcc.TestCaseChromosome)]
    )

    with patch.object(stat, "track_output_variable") as mock_track:
        lldynamosa_algorithm._target_initial_uncovered_goals()

    lldynamosa_algorithm.target_uncovered_callables.assert_called_once()
    assert len(lldynamosa_algorithm._population) == 1
    # DynaMOSA's UpdateTargets, not a flat archive.update(): this is the whole point
    # of Task 1.4 -- covering a parent target via an LLM chromosome must still unlock
    # its children.
    lldynamosa_algorithm._goals_manager.update.assert_called_once_with(
        lldynamosa_algorithm._population
    )
    lldynamosa_algorithm._archive.update.assert_not_called()
    mock_track.assert_any_call(RuntimeVariable.CoverageBeforeLLMCall, 0.5)
    mock_track.assert_any_call(RuntimeVariable.CoverageAfterLLMCall, 0.7)


def test_maybe_intervene_on_stall_updates_goals_manager(lldynamosa_algorithm):
    """Tests that a stall intervention unlocks goals, not just archive.update()."""
    llm_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    lldynamosa_algorithm.target_uncovered_callables = MagicMock(return_value=[llm_chromosome])
    existing_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    lldynamosa_algorithm._population = [existing_chromosome]

    lldynamosa_algorithm._maybe_intervene_on_stall()

    lldynamosa_algorithm.target_uncovered_callables.assert_called_once()
    assert lldynamosa_algorithm._population == [llm_chromosome, existing_chromosome]
    lldynamosa_algorithm._goals_manager.update.assert_called_once_with(
        lldynamosa_algorithm._population
    )


@patch("pynguin.ga.algorithms.lldynamosaalgorithm.config")
def test_generate_tests_with_llm_on_stall(mock_config, lldynamosa_algorithm):
    """Tests the generate_tests method with LLM intervention on stall detection."""
    mock_config.configuration.large_language_model.call_llm_on_stall_detection = True
    mock_config.configuration.large_language_model.max_llm_interventions = 2
    mock_config.configuration.large_language_model.max_plateau_len = 1
    mock_config.configuration.large_language_model.stall_detection_window_seconds = -1
    mock_config.configuration.large_language_model.min_remaining_budget_for_llm = -1
    mock_config.configuration.local_search.local_search = False

    lldynamosa_algorithm.resources_left = MagicMock(side_effect=[True, True, True, False])

    lldynamosa_algorithm._archive = MagicMock()
    lldynamosa_algorithm._archive.covered_goals = []
    lldynamosa_algorithm._archive.uncovered_goals = ["goal1", "goal2"]
    lldynamosa_algorithm._number_of_goals = 10

    lldynamosa_algorithm.before_search_start = MagicMock()
    lldynamosa_algorithm._get_random_population = MagicMock(return_value=[])
    lldynamosa_algorithm._target_initial_uncovered_goals = MagicMock()
    lldynamosa_algorithm.before_first_search_iteration = MagicMock()
    lldynamosa_algorithm.after_search_iteration = MagicMock()
    lldynamosa_algorithm.after_search_finish = MagicMock()
    lldynamosa_algorithm.target_uncovered_callables = MagicMock(
        return_value=[MagicMock(spec=tcc.TestCaseChromosome)]
    )
    lldynamosa_algorithm.create_test_suite = MagicMock()
    lldynamosa_algorithm.model = MagicMock()
    lldynamosa_algorithm.model.llm_calls_counter = 0

    with patch("pynguin.ga.algorithms.lldynamosaalgorithm._GoalsManager") as mock_goals_manager_cls:
        mock_goals_manager_cls.return_value = lldynamosa_algorithm._goals_manager

        def custom_evolve():
            if lldynamosa_algorithm.evolve.call_count == 1:
                lldynamosa_algorithm._archive.covered_goals = ["goal1"]

        lldynamosa_algorithm.evolve = MagicMock(side_effect=custom_evolve)

        lldynamosa_algorithm.generate_tests()

    assert lldynamosa_algorithm.evolve.call_count == 3
    lldynamosa_algorithm.after_search_finish.assert_called_once()


@patch("pynguin.ga.algorithms.lldynamosaalgorithm.get_coverage_report")
def test_target_uncovered_callables_queries_single_highest_priority(
    mock_get_coverage_report, lldynamosa_algorithm
):
    """Tests that only the single least-covered eligible callable is queried."""
    mock_coverage_report = MagicMock(spec=CoverageReport)
    mock_coverage_report.line_annotations = []
    mock_get_coverage_report.return_value = mock_coverage_report

    mock_gao_low = MagicMock(spec=GenericCallableAccessibleObject)
    mock_gao_high = MagicMock(spec=GenericCallableAccessibleObject)
    lldynamosa_algorithm._eligible_gaos_for_targeting = MagicMock(
        return_value={mock_gao_low, mock_gao_high}
    )

    test_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    handler = lldynamosa_algorithm.model.llm_test_case_handler
    handler.get_test_case_chromosomes_from_llm_results.return_value = [test_chromosome]

    with (
        patch("pynguin.ga.algorithms.lldynamosaalgorithm.config") as mock_config,
        patch(
            "pynguin.ga.algorithms.lldynamosaalgorithm.inspect.getsourcelines"
        ) as mock_getsourcelines,
    ):
        mock_config.configuration.large_language_model.coverage_threshold = 0.8
        mock_config.configuration.statistics_output.coverage_metrics = ["branch"]
        # mock_gao_low ends up with a lower coverage ratio (0/10) than mock_gao_high
        # (5/10): getsourcelines returns a different fake source range depending on
        # which GAO is asked for, and each range's line annotations below give it a
        # different coverage ratio.
        mock_coverage_report.line_annotations = [
            LineAnnotation(
                line_no=1,
                total=CoverageEntry(existing=10, covered=0),
                branches=CoverageEntry(existing=0, covered=0),
                branchless_code_objects=CoverageEntry(existing=0, covered=0),
                lines=CoverageEntry(existing=0, covered=0),
            ),
            LineAnnotation(
                line_no=101,
                total=CoverageEntry(existing=10, covered=5),
                branches=CoverageEntry(existing=0, covered=0),
                branchless_code_objects=CoverageEntry(existing=0, covered=0),
                lines=CoverageEntry(existing=0, covered=0),
            ),
        ]

        def fake_getsourcelines(callable_):
            if callable_ is mock_gao_low.callable:
                return (["line1"], 1)
            return (["line1"], 101)

        mock_getsourcelines.side_effect = fake_getsourcelines

        result = lldynamosa_algorithm.target_uncovered_callables()

    assert len(result) == 1
    assert result[0] == test_chromosome
    lldynamosa_algorithm.model.call_llm_for_uncovered_targets.assert_called_once()
    call_args = lldynamosa_algorithm.model.call_llm_for_uncovered_targets.call_args
    queried_gao_coverage_map = call_args[0][0]
    assert len(queried_gao_coverage_map) == 1


def test_eligible_gaos_for_targeting_restricts_to_active_goals(lldynamosa_algorithm):
    """Tests that only callables backing a currently-active goal are eligible."""
    active_gao = MagicMock(spec=GenericCallableAccessibleObject)
    inactive_gao = MagicMock(spec=GenericCallableAccessibleObject)

    active_fitness = MagicMock()
    active_fitness.goal.code_object_id = 1
    lldynamosa_algorithm._goals_manager.current_goals = [active_fitness]

    code_object_meta = MagicMock()
    code_object_meta.code_object.co_firstlineno = 10
    lldynamosa_algorithm.executor.subject_properties.existing_code_objects = {1: code_object_meta}
    lldynamosa_algorithm.test_cluster.accessible_objects_under_test = [
        active_gao,
        inactive_gao,
    ]

    with patch(
        "pynguin.ga.algorithms.lldynamosaalgorithm.inspect.getsourcelines"
    ) as mock_getsourcelines:

        def fake_getsourcelines(callable_):
            if callable_ is active_gao.callable:
                return (["l1"], 10)
            return (["l1"], 20)

        mock_getsourcelines.side_effect = fake_getsourcelines

        result = lldynamosa_algorithm._eligible_gaos_for_targeting()

    assert result == OrderedSet([active_gao])
