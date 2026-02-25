#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Readability scoring metrics for refined tests."""

import ast
import re
from typing import Any

_VAR_GENERIC_PATTERN = re.compile(r"^(var|list|dict|tuple|set)_\d+$")


def _extract_identifiers(tree: ast.AST) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


def score_aaa(test_code: str) -> float:
    """Scores presence and ordering of AAA markers (0..1)."""
    lower = test_code.lower()
    present = ["# arrange" in lower, "# act" in lower, "# assert" in lower]
    if not any(present):
        return 0.0
    # Ordering correctness
    arrange_pos = lower.find("# arrange")
    act_pos = lower.find("# act")
    assert_pos = lower.find("# assert")
    order_ok = arrange_pos <= act_pos <= assert_pos and act_pos != -1 and assert_pos != -1
    base = sum(present) / 3.0
    if order_ok:
        base += 0.25  # small bonus for correct order
    return min(base, 1.0)


def score_semantic_names(test_code: str) -> float:
    """Ratio of semantic (non-generic) identifiers to all identifiers (0..1)."""
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return 0.0
    identifiers = _extract_identifiers(tree)
    if not identifiers:
        return 0.0
    generic = sum(1 for n in identifiers if _VAR_GENERIC_PATTERN.match(n))
    return (len(identifiers) - generic) / len(identifiers)


def score_assertion_clarity(test_code: str) -> float:
    """Scores specificity of assertions: attribute/key/value presence vs trivial asserts.

    Heuristic: counts asserts referencing attribute access, subscripts, comparisons.
    """
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return 0.0
    total = 0
    specific = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            total += 1
            test = node.test
            if isinstance(test, (ast.Compare, ast.Call, ast.Attribute, ast.Subscript)):
                specific += 1
    if total == 0:
        return 0.0
    return specific / total


def score_conciseness(test_code: str) -> float:
    """Simple conciseness: ideal length window. Penalize overly long or extremely short.

    Returns 0..1 where ~10-40 lines (excluding blanks/comments) maps to high score.
    """
    lines = [
        line for line in test_code.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    n = len(lines)
    if n == 0:
        return 0.0
    if 10 <= n <= 40:
        return 1.0
    # Outside window: decay
    if n < 10:
        return n / 10.0
    # n > 40
    return max(0.0, 1.0 - (n - 40) / 40.0)


def aggregate_readability(test_code: str) -> dict[str, float]:
    """Compute individual readability sub-scores for a test."""
    return {
        "aaa": score_aaa(test_code),
        "semantic_names": score_semantic_names(test_code),
        "assertion_clarity": score_assertion_clarity(test_code),
        "conciseness": score_conciseness(test_code),
    }


def compute_all(test_code: str) -> dict[str, Any]:
    """Compute all readability scores including an aggregate mean."""
    scores = aggregate_readability(test_code)
    # Simple aggregate: average
    scores["aggregate"] = sum(scores.values()) / len(scores) if scores else 0.0
    return scores
