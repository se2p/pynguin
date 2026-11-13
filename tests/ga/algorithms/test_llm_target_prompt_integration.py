#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test: the uncovered-targets prompt lists the uncovered goals."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pynguin.configuration as config
import pynguin.generator as gen
import pynguin.utils.statistics.stats as stat
from pynguin.large_language_model.client import OpenAIClient
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


def test_lldynamosa_prompt_lists_uncovered_goals(tmp_path: pathlib.Path) -> None:
    """Runs LLDynaMOSA on a module with a hard branch and inspects the prompt."""
    configuration = config.Configuration(
        algorithm=config.Algorithm.LLDYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_iterations=2),
        module_name="tests.fixtures.examples.difficult",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(pathlib.Path().absolute()),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
        seeding=config.SeedingConfiguration(seed=42),
        large_language_model=config.LLMConfiguration(
            call_llm_for_uncovered_targets=True,
            tests_per_query=2,
            problem_cards=list(config.ProblemCardType),
        ),
    )
    gen.set_configuration(configuration)
    prompts: list[str] = []

    def record_prompt(_client: OpenAIClient, request: RenderedRequest, **_kwargs) -> str:
        prompts.append(request.messages[-1]["content"])
        return "def test_x():\n    difficult_branches('a', 1337, 42)\n"

    with (
        patch("pynguin.large_language_model.client.require_api_key") as mock_key,
        patch("pynguin.large_language_model.llmagent.openai.OpenAI"),
        patch.object(OpenAIClient, "send", autospec=True, side_effect=record_prompt),
        patch.object(stat, "track_output_variable", wraps=stat.track_output_variable) as tracked,
    ):
        mock_key.return_value = MagicMock()
        mock_key.return_value.get_secret_value.return_value = "test-api-key"
        assert gen.run_pynguin() == gen.ReturnCode.OK

    assert len(prompts) == 1
    card_stats = [
        call.args[1]
        for call in tracked.call_args_list
        if call.args[0] == RuntimeVariable.LLMProblemCardStats
    ]
    assert len(card_stats) == 1
    assert "CDG_BOTTLENECK=" in card_stats[0]
    prompt = prompts[0]
    assert "- The function difficult_branches" in prompt
    # Random inputs essentially never hit x == 1337, the condition on line 10.
    assert "Branch outcomes never taken: line 10 (True)" in prompt
    assert "Write exactly 2 test functions." in prompt
    # The inner condition on line 11 only runs when the one on line 10 is True.
    assert (
        "Hint: the condition at line 11 is only evaluated when the condition at line 10 is True"
        in prompt
    )
