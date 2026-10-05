# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Integration tests for synchronous and asynchronous LLM search query strategies."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
from pynguin.configuration import LLMMode
from pynguin.ga.algorithms.lldynamosaalgorithm import LLDynaMOSAAlgorithm
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.large_language_model.query_strategy import (
    AsyncLLMQueryStrategy,
    SyncLLMQueryStrategy,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


@pytest.fixture(autouse=True)
def _mock_require_api_key():
    with patch("pynguin.large_language_model.client.require_api_key") as mock:
        mock.return_value = MagicMock()
        mock.return_value.get_secret_value.return_value = "test-api-key"
        yield mock


def test_llmosa_sync_mode_stall_intervention(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.SYNC)
    monkeypatch.setattr(
        config.configuration.large_language_model, "min_remaining_budget_for_llm", -1
    )
    monkeypatch.setattr(config.configuration.large_language_model, "max_llm_interventions", -1)

    algorithm = LLMOSAAlgorithm()
    assert isinstance(algorithm._llm_query_strategy, SyncLLMQueryStrategy)

    llm_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._select_uncovered_targets = MagicMock(return_value=({MagicMock(): 0.0}, {}))
    algorithm._query_llm_for_targets = MagicMock(return_value=[llm_chromosome])

    initial_chrom = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._population = [initial_chrom]

    algorithm._maybe_intervene_on_stall()

    algorithm._select_uncovered_targets.assert_called_once()
    algorithm._query_llm_for_targets.assert_called_once()
    assert algorithm._population == [llm_chromosome, initial_chrom]


def test_llmosa_async_mode_stall_intervention(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.ASYNC)
    monkeypatch.setattr(
        config.configuration.large_language_model, "min_remaining_budget_for_llm", -1
    )
    monkeypatch.setattr(config.configuration.large_language_model, "max_llm_interventions", -1)

    algorithm = LLMOSAAlgorithm()
    assert isinstance(algorithm._llm_query_strategy, AsyncLLMQueryStrategy)

    llm_chromosome = MagicMock(spec=tcc.TestCaseChromosome)

    def slow_query_targets(*_args, **_kwargs):
        time.sleep(0.05)
        return [llm_chromosome]

    algorithm._select_uncovered_targets = MagicMock(return_value=({MagicMock(): 0.0}, {}))
    algorithm._query_llm_for_targets = MagicMock(side_effect=slow_query_targets)

    initial_chrom = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._population = [initial_chrom]

    algorithm._maybe_intervene_on_stall()

    algorithm._select_uncovered_targets.assert_called_once()
    assert algorithm._population == [initial_chrom]
    assert algorithm._llm_query_strategy.is_in_progress() is True

    timeout = time.time() + 5.0
    while algorithm._llm_query_strategy.is_in_progress() and time.time() < timeout:
        time.sleep(0.01)

    completed = algorithm._llm_query_strategy.poll()
    assert completed == [llm_chromosome]
    algorithm._integrate_llm_chromosomes(completed)

    assert algorithm._population == [llm_chromosome, initial_chrom]
    algorithm._llm_query_strategy.shutdown()


def test_lldynamosa_async_mode_integrates_and_updates_goals(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.ASYNC)
    monkeypatch.setattr(
        config.configuration.large_language_model, "min_remaining_budget_for_llm", -1
    )
    monkeypatch.setattr(config.configuration.large_language_model, "max_llm_interventions", -1)

    algorithm = LLDynaMOSAAlgorithm()
    algorithm._goals_manager = MagicMock()

    llm_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._select_uncovered_targets = MagicMock(return_value=({MagicMock(): 0.0}, {}))
    algorithm._query_llm_for_targets = MagicMock(return_value=[llm_chromosome])

    initial_chrom = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._population = [initial_chrom]

    algorithm._maybe_intervene_on_stall()

    algorithm._select_uncovered_targets.assert_called_once()

    timeout = time.time() + 5.0
    while algorithm._llm_query_strategy.is_in_progress() and time.time() < timeout:
        time.sleep(0.01)

    completed = algorithm._llm_query_strategy.poll()
    assert completed == [llm_chromosome]
    algorithm._integrate_llm_chromosomes(completed)

    assert algorithm._population == [llm_chromosome, initial_chrom]
    algorithm._goals_manager.update.assert_called_once_with(algorithm._population)
    algorithm._llm_query_strategy.shutdown()


def test_target_uncovered_callables_delegates_to_select_and_query():
    algorithm = LLMOSAAlgorithm()
    mock_targets = {MagicMock(): 0.5}
    mock_diagnostics = {MagicMock(): "hint"}
    mock_chromosomes = [MagicMock(spec=tcc.TestCaseChromosome)]

    algorithm._select_uncovered_targets = MagicMock(return_value=(mock_targets, mock_diagnostics))
    algorithm._query_llm_for_targets = MagicMock(return_value=mock_chromosomes)

    result = algorithm.target_uncovered_callables()

    algorithm._select_uncovered_targets.assert_called_once()
    algorithm._query_llm_for_targets.assert_called_once_with(mock_targets, mock_diagnostics)
    assert result == mock_chromosomes


def test_async_archive_update_concurrent_with_llm_query(monkeypatch):
    """Verifies that main-thread archive mutations do not race with background LLM queries."""
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.ASYNC)
    monkeypatch.setattr(
        config.configuration.large_language_model, "min_remaining_budget_for_llm", -1
    )
    monkeypatch.setattr(config.configuration.large_language_model, "max_llm_interventions", -1)

    algorithm = LLMOSAAlgorithm()

    llm_chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._select_uncovered_targets = MagicMock(return_value=({MagicMock(): 0.0}, {}))

    def slow_query_targets(*_args, **_kwargs):
        time.sleep(0.05)
        return [llm_chromosome]

    algorithm._query_llm_for_targets = MagicMock(side_effect=slow_query_targets)

    algorithm._maybe_intervene_on_stall()
    assert algorithm._llm_query_strategy.is_in_progress() is True

    mock_archive = MagicMock()
    algorithm._archive = mock_archive
    for _ in range(10):
        mock_archive.update([MagicMock(spec=tcc.TestCaseChromosome)])

    timeout = time.time() + 5.0
    while algorithm._llm_query_strategy.is_in_progress() and time.time() < timeout:
        time.sleep(0.01)

    completed = algorithm._llm_query_strategy.poll()
    assert completed == [llm_chromosome]
    algorithm._integrate_llm_chromosomes(completed)

    assert llm_chromosome in algorithm._population
    algorithm._llm_query_strategy.shutdown()


def test_llmosa_generate_tests_calls_cancel_all_on_shutdown(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.ASYNC)
    algorithm = LLMOSAAlgorithm()
    algorithm.before_search_start = MagicMock()
    algorithm._get_random_population = MagicMock(return_value=[])
    algorithm._archive = MagicMock()
    algorithm._target_initial_uncovered_goals = MagicMock()
    algorithm._compute_dominance = MagicMock()
    algorithm.before_first_search_iteration = MagicMock()
    algorithm.resources_left = MagicMock(return_value=False)
    algorithm._finalize_generation = MagicMock(return_value=MagicMock())
    algorithm.model = MagicMock()

    algorithm.generate_tests()

    algorithm.model.cancel_all.assert_called_once()


def test_lldynamosa_generate_tests_calls_cancel_all_on_shutdown(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.ASYNC)
    algorithm = LLDynaMOSAAlgorithm()
    algorithm._executor = MagicMock()
    algorithm.before_search_start = MagicMock()
    algorithm._get_random_population = MagicMock(return_value=[])
    algorithm._archive = MagicMock()
    algorithm._archive.solutions = []
    algorithm._target_initial_uncovered_goals = MagicMock()
    algorithm._ranking_function = MagicMock()
    algorithm.before_first_search_iteration = MagicMock()
    algorithm.resources_left = MagicMock(return_value=False)
    algorithm.after_search_finish = MagicMock()
    algorithm.create_test_suite = MagicMock(return_value=MagicMock())
    algorithm._get_best_individuals = MagicMock(return_value=[])
    algorithm.model = MagicMock()

    algorithm.generate_tests()

    algorithm.model.cancel_all.assert_called_once()


def test_llmosa_generate_tests_tracks_llm_blocking_time(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.SYNC)
    algorithm = LLMOSAAlgorithm()
    algorithm.before_search_start = MagicMock()
    algorithm._get_random_population = MagicMock(return_value=[])
    algorithm._archive = MagicMock()
    algorithm._target_initial_uncovered_goals = MagicMock()
    algorithm._compute_dominance = MagicMock()
    algorithm.before_first_search_iteration = MagicMock()
    algorithm.resources_left = MagicMock(return_value=False)
    algorithm._finalize_generation = MagicMock(return_value=MagicMock())
    algorithm.model = MagicMock()
    assert isinstance(algorithm._llm_query_strategy, SyncLLMQueryStrategy)
    algorithm._llm_query_strategy._blocked_seconds = 1.5

    with patch("pynguin.ga.algorithms.llmosalgorithm.stat") as mock_stat:
        algorithm.generate_tests()

    tracked_variables = {
        call.args[0]: call.args[1] for call in mock_stat.track_output_variable.call_args_list
    }
    assert tracked_variables[RuntimeVariable.LLMBlockingTimeSeconds] == 1.5


def test_lldynamosa_generate_tests_tracks_llm_blocking_time(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.SYNC)
    algorithm = LLDynaMOSAAlgorithm()
    algorithm._executor = MagicMock()
    algorithm.before_search_start = MagicMock()
    algorithm._get_random_population = MagicMock(return_value=[])
    algorithm._archive = MagicMock()
    algorithm._archive.solutions = []
    algorithm._target_initial_uncovered_goals = MagicMock()
    algorithm._ranking_function = MagicMock()
    algorithm.before_first_search_iteration = MagicMock()
    algorithm.resources_left = MagicMock(return_value=False)
    algorithm.after_search_finish = MagicMock()
    algorithm.create_test_suite = MagicMock(return_value=MagicMock())
    algorithm._get_best_individuals = MagicMock(return_value=[])
    algorithm.model = MagicMock()
    assert isinstance(algorithm._llm_query_strategy, SyncLLMQueryStrategy)
    algorithm._llm_query_strategy._blocked_seconds = 2.5

    with patch("pynguin.ga.algorithms.lldynamosaalgorithm.stat") as mock_stat:
        algorithm.generate_tests()

    tracked_variables = {
        call.args[0]: call.args[1] for call in mock_stat.track_output_variable.call_args_list
    }
    assert tracked_variables[RuntimeVariable.LLMBlockingTimeSeconds] == 2.5


def test_async_mode_never_blocks_the_caller(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", LLMMode.ASYNC)
    algorithm = LLMOSAAlgorithm()
    assert isinstance(algorithm._llm_query_strategy, AsyncLLMQueryStrategy)
    assert algorithm._llm_query_strategy.blocked_seconds == 0.0


def _initial_targeting_algorithm(monkeypatch, mode, query_seconds=0.0):
    monkeypatch.setattr(config.configuration.large_language_model, "llm_mode", mode)
    monkeypatch.setattr(
        config.configuration.large_language_model, "call_llm_for_uncovered_targets", True
    )
    algorithm = LLDynaMOSAAlgorithm()
    algorithm._goals_manager = MagicMock()
    algorithm._archive = MagicMock()
    algorithm.create_test_suite = MagicMock(
        return_value=MagicMock(get_coverage=MagicMock(return_value=0.5))
    )
    llm_chromosome = MagicMock(spec=tcc.TestCaseChromosome)

    def query_targets(*_args, **_kwargs):
        time.sleep(query_seconds)
        return [llm_chromosome]

    algorithm._select_uncovered_targets = MagicMock(return_value=({MagicMock(): 0.5}, {}))
    algorithm._query_llm_for_targets = MagicMock(side_effect=query_targets)
    algorithm._population = []
    return algorithm, llm_chromosome


def test_initial_llm_query_in_sync_mode_counts_towards_blocking_time(monkeypatch):
    algorithm, llm_chromosome = _initial_targeting_algorithm(
        monkeypatch, LLMMode.SYNC, query_seconds=0.05
    )

    algorithm._target_initial_uncovered_goals()

    assert algorithm._population == [llm_chromosome]
    algorithm._goals_manager.update.assert_called_once_with(algorithm._population)
    assert algorithm._llm_query_strategy.blocked_seconds >= 0.05


def test_initial_llm_query_in_async_mode_is_integrated_by_poll(monkeypatch):
    algorithm, llm_chromosome = _initial_targeting_algorithm(
        monkeypatch, LLMMode.ASYNC, query_seconds=0.05
    )

    with patch("pynguin.ga.algorithms.lldynamosaalgorithm.stat") as mock_stat:
        algorithm._target_initial_uncovered_goals()

    algorithm._select_uncovered_targets.assert_called_once()
    assert algorithm._population == []
    assert algorithm._llm_query_strategy.is_in_progress() is True
    tracked = [call.args[0] for call in mock_stat.track_output_variable.call_args_list]
    assert RuntimeVariable.CoverageAfterLLMCall not in tracked

    timeout = time.time() + 5.0
    while algorithm._llm_query_strategy.is_in_progress() and time.time() < timeout:
        time.sleep(0.01)
    completed = algorithm._llm_query_strategy.poll()
    algorithm._integrate_llm_chromosomes(completed)

    assert algorithm._population == [llm_chromosome]
    assert algorithm._llm_query_strategy.blocked_seconds == 0.0
    algorithm._llm_query_strategy.shutdown()


def test_initial_llm_query_without_targets_sends_nothing(monkeypatch):
    algorithm, _ = _initial_targeting_algorithm(monkeypatch, LLMMode.SYNC)
    algorithm._select_uncovered_targets = MagicMock(return_value=({}, {}))

    algorithm._target_initial_uncovered_goals()

    algorithm._query_llm_for_targets.assert_not_called()
    assert algorithm._population == []
