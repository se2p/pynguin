# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Tests for quick_eval CLI-argument construction (coverage-only / --no-assertions).

The quick_eval harness lives in ``utils/_quick_eval`` (outside ``src``); make it
importable the same way the ``utils/quick_eval.py`` entry point does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_UTILS_DIR = Path(__file__).resolve().parents[2] / "utils"
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

from _quick_eval.runner import (  # noqa: E402
    LLM_MODE_FULL,  # noqa: PLC2701
    LLM_MODE_MIN,  # noqa: PLC2701
    _assertion_cli_args,  # noqa: PLC2701
    _llm_cli_args,  # noqa: PLC2701
)


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    """Drop LLM credentials so ``_llm_cli_args`` output is deterministic."""
    for var in (
        "LLM_API_KEY",
        "PYNGUIN_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "LLM_BASE_URL",
        "PYNGUIN_LLM_BASE_URL",
        "LLM_MODEL",
        "PYNGUIN_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


def _pairs(args: list[str]) -> dict[str, str]:
    """Collapse a flat ``[flag, value, ...]`` list into a ``{flag: value}`` mapping."""
    return {args[i]: args[i + 1] for i in range(0, len(args) - 1, 2)}


def test_assertion_args_coverage_only_disables_generation():
    assert _assertion_cli_args(no_assertions=True, budget=60) == [
        "--test-case-output.assertion-generation",
        "NONE",
    ]


def test_assertion_args_default_bounds_mutation_to_budget():
    # Below the 60s floor, the floor wins.
    assert _assertion_cli_args(no_assertions=False, budget=30) == [
        "--test-case-output.maximum-mutation-time",
        "60",
    ]
    # Above the floor, the budget is used verbatim.
    assert _assertion_cli_args(no_assertions=False, budget=200) == [
        "--test-case-output.maximum-mutation-time",
        "200",
    ]


def test_min_mode_drops_refinement_in_coverage_only():
    default = _pairs(_llm_cli_args(LLM_MODE_MIN))
    coverage_only = _pairs(_llm_cli_args(LLM_MODE_MIN, no_assertions=True))

    # Refinement is a non-coverage LLM request; it is dropped in coverage-only mode.
    assert default["--llm-refinement.enabled"] == "True"
    assert "--llm-refinement.enabled" not in coverage_only

    # Coverage-driving calls stay on in both cases.
    for flag in (
        "--algorithm",
        "--large-language-model.enable-response-caching",
        "--large-language-model.call-llm-on-stall-detection",
    ):
        assert flag in coverage_only


def test_full_mode_drops_llm_assertion_generation_in_coverage_only():
    default = _pairs(_llm_cli_args(LLM_MODE_FULL))
    coverage_only = _pairs(_llm_cli_args(LLM_MODE_FULL, no_assertions=True))

    # Full mode's in-search LLM assertion generation is dropped in coverage-only mode.
    assert default["--assertion-generation"] == "LLM"
    assert "--assertion-generation" not in coverage_only

    # The coverage-driving LLM calls stay on.
    for flag in (
        "--large-language-model.call-llm-for-uncovered-targets",
        "--large-language-model.call-llm-on-stall-detection",
        "--large-language-model.hybrid-initial-population",
    ):
        assert flag in coverage_only
