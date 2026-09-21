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
    algorithm.target_uncovered_callables = MagicMock(return_value=[llm_chromosome])

    initial_chrom = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._population = [initial_chrom]

    algorithm._maybe_intervene_on_stall()

    algorithm.target_uncovered_callables.assert_called_once()
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

    def slow_target_callables():
        time.sleep(0.05)
        return [llm_chromosome]

    algorithm.target_uncovered_callables = MagicMock(side_effect=slow_target_callables)

    initial_chrom = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._population = [initial_chrom]

    # Trigger stall: should dispatch in background and return immediately
    algorithm._maybe_intervene_on_stall()

    # Right after dispatch, population should not yet have the LLM chromosome
    assert algorithm._population == [initial_chrom]
    assert algorithm._llm_query_strategy.is_in_progress() is True

    # Poll until ready
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
    algorithm.target_uncovered_callables = MagicMock(return_value=[llm_chromosome])

    initial_chrom = MagicMock(spec=tcc.TestCaseChromosome)
    algorithm._population = [initial_chrom]

    algorithm._maybe_intervene_on_stall()

    # Wait for completion
    timeout = time.time() + 5.0
    while algorithm._llm_query_strategy.is_in_progress() and time.time() < timeout:
        time.sleep(0.01)

    completed = algorithm._llm_query_strategy.poll()
    assert completed == [llm_chromosome]
    algorithm._integrate_llm_chromosomes(completed)

    assert algorithm._population == [llm_chromosome, initial_chrom]
    algorithm._goals_manager.update.assert_called_once_with(algorithm._population)
    algorithm._llm_query_strategy.shutdown()
