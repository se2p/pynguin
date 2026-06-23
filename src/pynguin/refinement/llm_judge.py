#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM-as-a-Judge: Automated Readability Evaluation (Standalone).

This module provides LLM-based evaluation of test readability, using GPT-4o-mini
(or another LLM) to score tests on dimensions aligned with human judgment.

**This is NOT part of the refinement pipeline.** It is used only during the
post-pipeline evaluation phase (RQ1) to independently score test readability.
The refinement pipeline itself records only heuristic readability metrics
(via ``readability_metrics.py``); the LLM Judge, Cosmic Ray mutation testing,
and the developer survey are all run separately after the pipeline produces
its output.

The scoring rubric is designed to correlate with the user study dimensions
from Daka & Fraser (2015):
1. Identifier Meaningfulness
2. Structural Simplicity (AAA pattern)
3. Assertion Clarity
4. Overall Understandability

Usage (post-pipeline evaluation script)::

    from pynguin.refinement.llm_judge import LLMJudge

    judge = LLMJudge(api_key="sk-...")
    scores = judge.evaluate_test_pair(original_code, refined_code)
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pynguin.refinement.llm_client import LLMClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class JudgeScore:
    """Scores from LLM-as-a-Judge evaluation.

    Each dimension is scored 1-5 (like Likert scale):
    1 = Very poor
    2 = Poor
    3 = Acceptable
    4 = Good
    5 = Excellent
    """

    identifier_meaningfulness: float = 0.0
    structural_simplicity: float = 0.0
    assertion_clarity: float = 0.0
    overall_understandability: float = 0.0

    # Aggregated score (mean of all dimensions)
    aggregate: float = 0.0

    # Raw LLM response for debugging
    raw_response: str = ""

    # Whether evaluation succeeded
    success: bool = False
    error: str | None = None

    def compute_aggregate(self) -> None:
        """Compute aggregate score as mean of all dimensions."""
        scores = [
            self.identifier_meaningfulness,
            self.structural_simplicity,
            self.assertion_clarity,
            self.overall_understandability,
        ]
        valid_scores = [s for s in scores if s > 0]
        self.aggregate = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0


@dataclass
class JudgePairResult:
    """Result of comparing original vs refined test."""

    original_scores: JudgeScore = field(default_factory=JudgeScore)
    refined_scores: JudgeScore = field(default_factory=JudgeScore)

    # Improvement delta (refined - original)
    delta: float = 0.0

    # Per-dimension deltas
    identifier_delta: float = 0.0
    structure_delta: float = 0.0
    assertion_delta: float = 0.0
    understandability_delta: float = 0.0

    # Token usage for cost tracking
    input_tokens: int = 0
    output_tokens: int = 0

    def compute_deltas(self) -> None:
        """Compute improvement deltas."""
        self.identifier_delta = (
            self.refined_scores.identifier_meaningfulness
            - self.original_scores.identifier_meaningfulness
        )
        self.structure_delta = (
            self.refined_scores.structural_simplicity - self.original_scores.structural_simplicity
        )
        self.assertion_delta = (
            self.refined_scores.assertion_clarity - self.original_scores.assertion_clarity
        )
        self.understandability_delta = (
            self.refined_scores.overall_understandability
            - self.original_scores.overall_understandability
        )
        self.delta = self.refined_scores.aggregate - self.original_scores.aggregate


class LLMJudge:
    """LLM-based test readability evaluator.

    Uses a structured prompt to elicit consistent scores from an LLM,
    aligned with human readability judgment dimensions.
    """

    # Evaluation prompt template
    EVALUATION_PROMPT = """\
You are an expert software engineer evaluating the readability of Python unit tests.

**Test Code to Evaluate:**
```python
{test_code}
```

**Evaluation Rubric:**

Rate the test on each dimension using a 1-5 scale:
1 = Very poor
2 = Poor
3 = Acceptable
4 = Good
5 = Excellent

**Dimensions:**

1. **Identifier Meaningfulness** (1-5)
   - 1: All generic names (var_0, str_1, int_2)
   - 3: Mix of generic and meaningful names
   - 5: All names are descriptive and self-documenting

2. **Structural Simplicity** (1-5)
   - 1: Monolithic, no clear structure
   - 3: Some structure visible but not explicit
   - 5: Clear Arrange-Act-Assert pattern with markers

3. **Assertion Clarity** (1-5)
   - 1: No assertions or only trivial ones (is not None)
   - 3: Basic assertions present
   - 5: Comprehensive assertions that clearly verify behavior

4. **Overall Understandability** (1-5)
   - 1: Very difficult to understand what the test does
   - 3: Understandable with some effort
   - 5: Immediately clear what the test verifies

**Response Format:**
Respond with ONLY a JSON object (no markdown, no explanation):
{{
    "identifier_meaningfulness": X,
    "structural_simplicity": X,
    "assertion_clarity": X,
    "overall_understandability": X
}}

Replace X with your score (1-5) for each dimension."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
    ):
        """Initialize the LLM Judge.

        Args:
            api_key: OpenAI API key (required; can use OPENAI_API_KEY)
            model: Model name (default: gpt-4o-mini)
        """
        # OpenAI only; LLMClient will check env var if api_key is None.
        self.client = LLMClient(
            model_name=model,
            api_key=api_key,
        )

        self.model = model
        self.provider = "openai"

        # Track usage
        self._total_calls = 0

    def evaluate_test(self, test_code: str) -> JudgeScore:
        """Evaluate a single test's readability.

        Args:
            test_code: The test code to evaluate

        Returns:
            JudgeScore with ratings on each dimension
        """
        prompt = self.EVALUATION_PROMPT.format(test_code=test_code)

        try:
            # Get LLM response
            response = self.client.generate_code(prompt)
            self._total_calls += 1

            # Parse JSON response
            scores = self._parse_scores(response)
            scores.raw_response = response
            scores.success = True
            scores.compute_aggregate()

            _LOGGER.info(
                "LLM Judge scores: identifier=%.1f, structure=%.1f, assertion=%.1f, overall=%.1f",
                scores.identifier_meaningfulness,
                scores.structural_simplicity,
                scores.assertion_clarity,
                scores.overall_understandability,
            )

            return scores

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("LLM Judge evaluation failed: %s", e)
            return JudgeScore(success=False, error=str(e))

    def evaluate_test_pair(self, original_code: str, refined_code: str) -> JudgePairResult:
        """Evaluate and compare original vs refined test.

        Args:
            original_code: Original Pynguin-generated test
            refined_code: Test after LLM refinement

        Returns:
            JudgePairResult with scores for both and deltas
        """
        result = JudgePairResult()

        # Evaluate original
        _LOGGER.info("Evaluating original test...")
        result.original_scores = self.evaluate_test(original_code)

        # Evaluate refined
        _LOGGER.info("Evaluating refined test...")
        result.refined_scores = self.evaluate_test(refined_code)

        # Compute deltas
        if result.original_scores.success and result.refined_scores.success:
            result.compute_deltas()

        # Track token usage
        try:
            usage = self.client.get_usage()
            result.input_tokens = usage.get("input_tokens", 0)
            result.output_tokens = usage.get("output_tokens", 0)
        except Exception:  # noqa: BLE001, S110
            pass

        return result

    def _parse_scores(self, response: str) -> JudgeScore:
        """Parse LLM response into JudgeScore.

        Args:
            response: Raw LLM response (should be JSON)

        Returns:
            JudgeScore with parsed values
        """
        scores = JudgeScore()

        # Try to extract JSON from response
        # Handle cases where LLM wraps in markdown or adds explanation
        json_match = re.search(r"\{[^}]+\}", response)
        if not json_match:
            raise ValueError(f"No JSON found in response: {response[:100]}")

        json_str = json_match.group()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {json_str}") from e

        # Extract scores with validation
        scores.identifier_meaningfulness = self._validate_score(
            data.get("identifier_meaningfulness", 0)
        )
        scores.structural_simplicity = self._validate_score(data.get("structural_simplicity", 0))
        scores.assertion_clarity = self._validate_score(data.get("assertion_clarity", 0))
        scores.overall_understandability = self._validate_score(
            data.get("overall_understandability", 0)
        )

        return scores

    def _validate_score(self, value: Any) -> float:
        """Validate and clamp score to 1-5 range.

        Args:
            value: Raw score value from JSON

        Returns:
            Validated float score in range [1, 5]
        """
        try:
            score = float(value)
            return max(1.0, min(5.0, score))
        except (TypeError, ValueError):
            return 0.0

    def get_usage(self) -> dict[str, int]:
        """Get total token usage across all evaluations.

        Returns:
            Dict with calls, input_tokens, output_tokens
        """
        try:
            usage = self.client.get_usage()
            return {
                "calls": self._total_calls,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
        except Exception:  # noqa: BLE001
            return {"calls": self._total_calls, "input_tokens": 0, "output_tokens": 0}

    def reset_usage(self) -> None:
        """Reset token usage counters."""
        self._total_calls = 0
        with contextlib.suppress(Exception):
            self.client.reset_usage()
