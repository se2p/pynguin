#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the MockGenerator module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from pynguin.large_language_model.mock_generation.dependency_analyzer import MockDecision
from pynguin.large_language_model.mock_generation.mock_generator import (
    MockGenerator,
    MockMethodConfig,
    MockParameter,
    MockTemplate,
)

if TYPE_CHECKING:
    from pathlib import Path

_DA = "pynguin.large_language_model.mock_generation.mock_generator.DependencyAnalyzer"


def _decision(target: str, decision: str) -> MockDecision:
    return MockDecision(target=target, decision=decision, reason="", source="llm", confidence=0.9)


def test_mock_template_defaults():
    t = MockTemplate(
        dependency="conn", import_path="redis", mock_target="redis.connection.Connection"
    )
    assert t.method_configs == []
    assert t.attribute_values == {}
    assert not t.setup_code


def test_mock_method_config_defaults():
    mc = MockMethodConfig(method_name="get", return_value_template="")
    assert mc.parameters == []
    assert mc.side_effect is None


def test_mock_parameter_fields():
    p = MockParameter(name="status", param_type="int", default_value=200, description="code")
    assert p.name == "status"
    assert p.default_value == 200


def test_generate_for_module_collects_mock_targets(tmp_path: Path):
    module = tmp_path / "m.py"
    module.write_text("import redis\n", encoding="utf-8")
    decisions = [
        _decision("redis.connection.Connection", "mock"),
        _decision("redis.exceptions.RedisError", "skip"),
        _decision("redis.retry.Retry", "mock"),
    ]
    with patch(_DA) as analyzer_cls:
        analyzer_cls.return_value.analyze.return_value = decisions
        gen = MockGenerator(use_proxy=True)
        gen.generate_for_module(module)

    assert gen.mock_targets == {"redis.connection.Connection", "redis.retry.Retry"}


def test_generate_for_module_records_source_counts(tmp_path: Path):
    module = tmp_path / "m.py"
    module.write_text("import redis\n", encoding="utf-8")
    decisions = [
        MockDecision("redis.connection.Connection", "mock", "", "rule", 0.9),
        MockDecision("redis.client.Redis", "mock", "", "rule", 0.9),
        MockDecision("redis.retry.Retry", "mock", "", "llm", 0.9),
        MockDecision("redis.exceptions.RedisError", "skip", "", "exception", 1.0),
    ]
    with patch(_DA) as analyzer_cls:
        analyzer_cls.return_value.analyze.return_value = decisions
        gen = MockGenerator(use_proxy=True)
        gen.generate_for_module(module)

    assert gen.source_counts == {"rule": 2, "llm": 1}


def test_generate_for_module_no_mock_targets(tmp_path: Path):
    module = tmp_path / "m.py"
    module.write_text("import json\n", encoding="utf-8")
    with patch(_DA) as analyzer_cls:
        analyzer_cls.return_value.analyze.return_value = [_decision("json.JSONEncoder", "skip")]
        gen = MockGenerator()
        gen.generate_for_module(module)

    assert gen.mock_targets == set()
