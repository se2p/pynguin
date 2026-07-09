#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the (currently inert) LLM local search hook."""

from unittest.mock import MagicMock

from pynguin.testcase.llmlocalsearch import LLMLocalSearch


def test_llm_local_search_is_a_noop():
    chromosome = MagicMock()
    objective = MagicMock()
    factory = MagicMock()
    suite = MagicMock()
    executor = MagicMock()

    search = LLMLocalSearch(chromosome, objective, factory, suite, executor)

    assert search.llm_local_search(0) is False
    # No interaction with the objective/factory/suite/executor: it is a pure no-op.
    objective.has_improved.assert_not_called()
    factory.mutate_call.assert_not_called()
