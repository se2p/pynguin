#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the standalone LLM judge (llm_judge.py)."""

from __future__ import annotations

import pytest

import pynguin.configuration as config
from pynguin.refinement import llm_judge as llm_judge_module
from pynguin.refinement.llm_judge import JudgePairResult, JudgeScore, LLMJudge


def test_judge_score_compute_aggregate_uses_nonzero_scores_only():
    score = JudgeScore(
        identifier_meaningfulness=4,
        structural_simplicity=0,
        assertion_clarity=2,
        overall_understandability=0,
    )
    score.compute_aggregate()
    assert score.aggregate == pytest.approx(3.0)


def test_judge_pair_result_compute_deltas():
    result = JudgePairResult(
        original_scores=JudgeScore(
            identifier_meaningfulness=2,
            structural_simplicity=2,
            assertion_clarity=2,
            overall_understandability=2,
            aggregate=2,
        ),
        refined_scores=JudgeScore(
            identifier_meaningfulness=4,
            structural_simplicity=3,
            assertion_clarity=5,
            overall_understandability=4,
            aggregate=4,
        ),
    )
    result.compute_deltas()
    assert result.identifier_delta == 2
    assert result.structure_delta == 1
    assert result.assertion_delta == 3
    assert result.understandability_delta == 2
    assert result.delta == 2


def test_init_routes_api_key_through_shared_config(monkeypatch):
    seen: dict[str, object] = {}

    class _FakeClient:
        def __init__(self, model_name=None):
            seen["model_name"] = model_name

    monkeypatch.setattr(llm_judge_module, "LLMClient", _FakeClient)
    judge = LLMJudge(api_key="k-test", model="my-model")
    assert config.configuration.large_language_model.api_key == "k-test"
    assert seen["model_name"] == "my-model"
    assert judge.model == "my-model"


def test_parse_scores_from_json_snippet(monkeypatch):
    monkeypatch.setattr(llm_judge_module, "LLMClient", lambda **_kwargs: object())
    judge = LLMJudge()
    parsed = judge._parse_scores(
        'prefix {"identifier_meaningfulness": 4, "structural_simplicity": 3, '
        '"assertion_clarity": 5, "overall_understandability": 2} suffix'
    )
    assert parsed.identifier_meaningfulness == 4
    assert parsed.structural_simplicity == 3
    assert parsed.assertion_clarity == 5
    assert parsed.overall_understandability == 2


def test_parse_scores_raises_on_missing_json(monkeypatch):
    monkeypatch.setattr(llm_judge_module, "LLMClient", lambda **_kwargs: object())
    judge = LLMJudge()
    with pytest.raises(ValueError, match="No JSON found"):
        judge._parse_scores("not json")


def test_parse_scores_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr(llm_judge_module, "LLMClient", lambda **_kwargs: object())
    judge = LLMJudge()
    with pytest.raises(ValueError, match="Invalid JSON"):
        judge._parse_scores('{"identifier_meaningfulness": }')


@pytest.mark.parametrize(
    "raw, expected",
    [(10, 5.0), (-1, 1.0), ("3", 3.0), ("bad", 0.0), (None, 0.0)],
)
def test_validate_score_clamps_and_handles_invalid(monkeypatch, raw, expected):
    monkeypatch.setattr(llm_judge_module, "LLMClient", lambda **_kwargs: object())
    judge = LLMJudge()
    assert judge._validate_score(raw) == expected


def test_evaluate_test_success(monkeypatch):
    class _FakeClient:
        def __init__(self, model_name=None):
            self._model_name = model_name

        def generate_code(self, _prompt):
            return (
                '{"identifier_meaningfulness": 4, "structural_simplicity": 3, '
                '"assertion_clarity": 5, "overall_understandability": 4}'
            )

        def get_usage(self):
            return {"input_tokens": 10, "output_tokens": 2}

        def reset_usage(self):
            return None

    monkeypatch.setattr(llm_judge_module, "LLMClient", _FakeClient)
    judge = LLMJudge()
    score = judge.evaluate_test("def test_x():\n    assert True\n")
    assert score.success is True
    assert score.aggregate == pytest.approx(4.0)
    assert score.raw_response


def test_evaluate_test_returns_failed_score_on_exception(monkeypatch):
    class _FakeClient:
        def __init__(self, model_name=None):
            self._model_name = model_name

        def generate_code(self, _prompt):
            raise RuntimeError("network")

    monkeypatch.setattr(llm_judge_module, "LLMClient", _FakeClient)
    judge = LLMJudge()
    score = judge.evaluate_test("def test_x():\n    assert True\n")
    assert score.success is False
    assert "network" in (score.error or "")


def test_evaluate_test_pair_computes_deltas_and_usage(monkeypatch):
    class _FakeClient:
        def __init__(self, model_name=None):
            self._model_name = model_name

        def generate_code(self, prompt):
            if "original" in prompt:
                return (
                    '{"identifier_meaningfulness": 2, "structural_simplicity": 2, '
                    '"assertion_clarity": 2, "overall_understandability": 2}'
                )
            return (
                '{"identifier_meaningfulness": 4, "structural_simplicity": 4, '
                '"assertion_clarity": 4, "overall_understandability": 4}'
            )

        def get_usage(self):
            return {"input_tokens": 100, "output_tokens": 40}

        def reset_usage(self):
            return None

    monkeypatch.setattr(llm_judge_module, "LLMClient", _FakeClient)
    judge = LLMJudge()
    pair = judge.evaluate_test_pair("# original", "# refined")
    assert pair.original_scores.success is True
    assert pair.refined_scores.success is True
    assert pair.delta == pytest.approx(2.0)
    assert pair.input_tokens == 100
    assert pair.output_tokens == 40


def test_get_usage_handles_client_exception(monkeypatch):
    class _FakeClient:
        def __init__(self, model_name=None):
            self._model_name = model_name

        def get_usage(self):
            raise RuntimeError("no usage")

        def reset_usage(self):
            return None

    monkeypatch.setattr(llm_judge_module, "LLMClient", _FakeClient)
    judge = LLMJudge()
    judge._total_calls = 7
    assert judge.get_usage() == {"calls": 7, "input_tokens": 0, "output_tokens": 0}


def test_reset_usage_suppresses_client_errors(monkeypatch):
    class _FakeClient:
        def __init__(self, model_name=None):
            self._model_name = model_name

        def reset_usage(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(llm_judge_module, "LLMClient", _FakeClient)
    judge = LLMJudge()
    judge._total_calls = 9
    judge.reset_usage()
    assert judge._total_calls == 0
