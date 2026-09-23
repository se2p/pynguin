#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the DependencyAnalyzer module."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from pynguin.mock_generation.dependency_analyzer import (
    DependencyAnalyzer,
    HeuristicRules,
    MockDecision,
)

if TYPE_CHECKING:
    from pathlib import Path

_CLASSIFY = "pynguin.mock_generation.llm_classifier_client.classify_target"
_BATCH = "pynguin.mock_generation.llm_classifier_client.classify_targets_batch"
_GET_RULES = "pynguin.mock_generation.llm_classifier_client.get_rules"

_RULES = {
    "targets": [{"target": "redis.connection.Connection", "decision": "mock", "reason": "DB"}]
}


def _write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "sut.py"
    path.write_text(source, encoding="utf-8")
    return path


def _analyzer(tmp_path: Path, source: str, **kw) -> DependencyAnalyzer:
    return DependencyAnalyzer(_write(tmp_path, source), **kw)


# MockDecision


def test_mock_decision_fields():
    d = MockDecision("urllib3.poolmanager.PoolManager", "mock", "boundary", "llm", 0.9)
    assert d.target == "urllib3.poolmanager.PoolManager"
    assert d.decision == "mock"


# HeuristicRules


def test_rules_default_empty():
    assert HeuristicRules().targets == {}


def test_rules_parse_and_match():
    rules = HeuristicRules.__new__(HeuristicRules)
    rules.targets = HeuristicRules._parse(_RULES)
    assert rules.match("redis.connection.Connection") == "DB"
    assert rules.match("redis.client.Redis") is None


def test_rules_parse_ignores_skip_and_missing_target():
    data = {"targets": [{"target": "x.Y", "decision": "skip"}, {"decision": "mock"}]}
    assert HeuristicRules._parse(data) == {}


def test_rules_from_proxy_cache():
    with patch(_GET_RULES, return_value=_RULES):
        rules = HeuristicRules.from_proxy_cache("id-1")
    assert rules.match("redis.connection.Connection") == "DB"


# Candidate extraction


def test_extract_from_import():
    tree = ast.parse("from redis.connection import Connection, ConnectionPool\n")
    assert DependencyAnalyzer._extract_candidates(tree) == [
        ("redis.connection", "Connection"),
        ("redis.connection", "ConnectionPool"),
    ]


def test_extract_module_qualified_usage():
    tree = ast.parse("import urllib3\nx = urllib3.PoolManager()\n")
    assert ("urllib3", "PoolManager") in DependencyAnalyzer._extract_candidates(tree)


def test_extract_ignores_relative_and_future():
    tree = ast.parse("from __future__ import annotations\nfrom .models import Response\n")
    assert DependencyAnalyzer._extract_candidates(tree) == []


# Resolution to canonical FQN


def test_resolve_canonical_fqn():
    fqn, obj = DependencyAnalyzer._resolve("json", "JSONDecoder")
    assert fqn == "json.decoder.JSONDecoder"
    assert isinstance(obj, type)


def test_resolve_unresolvable_falls_back():
    fqn, obj = DependencyAnalyzer._resolve("nope_pkg", "Thing")
    assert fqn == "nope_pkg.Thing"
    assert obj is None


# Classification


def test_classify_exception_skipped(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n")
    d = a._classify("redis.exceptions.RedisError", ConnectionError)
    assert d.decision == "skip"
    assert d.source == "exception"


def test_classify_stdlib_skipped(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n")
    d = a._classify("json.decoder.JSONDecoder", None)
    assert d.decision == "skip"
    assert d.source == "stdlib"


def test_classify_rule_mock(tmp_path):
    rules = HeuristicRules.__new__(HeuristicRules)
    rules.targets = HeuristicRules._parse(_RULES)
    a = _analyzer(tmp_path, "x = 1\n", heuristic_rules=rules)
    d = a._classify("redis.connection.Connection", object)
    assert d.decision == "mock"
    assert d.source == "rule"


def test_classify_proxy_mock(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n", use_proxy=True)
    with patch(_CLASSIFY, return_value={"decision": "mock", "reason": "net", "confidence": 0.9}):
        d = a._classify("urllib3.poolmanager.PoolManager", object)
    assert d.decision == "mock"
    assert d.source == "llm"


def test_classify_unknown_without_proxy(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n", use_proxy=False)
    d = a._classify("some.external.Client", object)
    assert d.decision == "unknown"


def test_classify_proxy_error_falls_back_to_unknown(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n", use_proxy=True)
    with patch(_CLASSIFY, side_effect=RuntimeError("down")):
        d = a._classify("some.external.Client", object)
    assert d.decision == "unknown"


# End-to-end


def test_analyze_skips_exceptions_and_stdlib(tmp_path):
    a = _analyzer(tmp_path, "from json import JSONDecoder, JSONDecodeError\n")
    decisions = {d.target: d for d in a.analyze()}
    assert decisions["json.decoder.JSONDecoder"].source == "stdlib"
    assert decisions["json.decoder.JSONDecodeError"].source == "exception"


def test_analyze_deduplicates(tmp_path):
    a = _analyzer(tmp_path, "from json import JSONDecoder\nimport json\nx = json.JSONDecoder\n")
    targets = [d.target for d in a.analyze()]
    assert targets.count("json.decoder.JSONDecoder") == 1


def test_syntax_error_raises(tmp_path):
    a = _analyzer(tmp_path, "def broken(\n")
    with pytest.raises(SyntaxError):
        a.analyze()


# Batch classification


def test_classify_all_batches_proxy_and_keeps_local(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n", use_proxy=True)
    pairs = [
        ("json.decoder.JSONDecoder", None),  # stdlib -> local skip
        ("redis.exceptions.RedisError", ConnectionError),  # exception -> local skip
        ("urllib3.poolmanager.PoolManager", object),  # proxy-cache
        ("some.other.Client", object),  # proxy-cache
    ]
    batch_result = {
        "urllib3.poolmanager.PoolManager": {"decision": "mock", "reason": "net", "confidence": 0.9},
        "some.other.Client": {"decision": "skip", "reason": "data", "confidence": 0.8},
    }
    with patch(_BATCH, return_value=batch_result) as batch:
        decisions = {d.target: d for d in a._classify_all(pairs)}

    batch.assert_called_once()
    assert set(batch.call_args.args[0]) == {"urllib3.poolmanager.PoolManager", "some.other.Client"}
    assert decisions["json.decoder.JSONDecoder"].source == "stdlib"
    assert decisions["redis.exceptions.RedisError"].source == "exception"
    assert decisions["urllib3.poolmanager.PoolManager"].decision == "mock"
    assert decisions["some.other.Client"].decision == "skip"


def test_classify_all_no_proxy_yields_unknown(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n", use_proxy=False)
    decisions = a._classify_all([("some.external.Client", object)])
    assert decisions[0].decision == "unknown"


def test_classify_all_batch_error_falls_back_to_unknown(tmp_path):
    a = _analyzer(tmp_path, "x = 1\n", use_proxy=True)
    with patch(_BATCH, side_effect=RuntimeError("down")):
        decisions = a._classify_all([("some.external.Client", object)])
    assert decisions[0].decision == "unknown"


def test_analyze_uses_single_batch_call(tmp_path):
    src = "from redis.connection import Connection, ConnectionPool\n"
    a = _analyzer(tmp_path, src, use_proxy=True)
    with patch(_BATCH, return_value={}) as batch:
        a.analyze()
    batch.assert_called_once()
