#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the new TestCaseGenerationPrompt template-based class."""

import pynguin.configuration as config
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.prompts.testcasegenerationprompt import TestCaseGenerationPrompt
from pynguin.large_language_model.request import RenderedRequest


def test_testcasegenerationprompt_init():
    prompt = TestCaseGenerationPrompt("def foo():\n    pass", "example/path.py")
    assert prompt.module_code == "def foo():\n    pass"
    assert prompt.module_path == "example/path.py"
    assert prompt._resource_name == "test_case_generation"
    assert prompt._template_vars() == ["module_code", "module_path"]


def test_testcasegenerationprompt_build_prompt():
    prompt = TestCaseGenerationPrompt("def foo():\n    pass", "example/path.py")
    expected = (
        "Write unit tests for the following module. Don't use unittest, but only pytest.\n"
        "Module path: `example/path.py`\n"
        "Module source code: `def foo():\n    pass`"
    )
    assert prompt.build_prompt() == expected


def test_testcasegenerationprompt_render():
    prompt = TestCaseGenerationPrompt("def foo():\n    pass", "example/path.py")
    rendered = prompt.render(module_code="def foo():\n    pass", module_path="example/path.py")

    assert isinstance(rendered, RenderedRequest)
    assert len(rendered.messages) == 2
    assert rendered.messages[0]["role"] == "system"
    assert "You are a unit test generating AI" in rendered.messages[0]["content"]
    assert rendered.messages[1]["role"] == "user"
    assert "Write unit tests for the following module" in rendered.messages[1]["content"]


def test_prompt_parameter_overrides(monkeypatch):
    # Single source of truth:
    # - model comes ONLY from the run configuration.
    # - temperature / max_tokens come ONLY from the per-prompt YAML.

    # 1. Defaults come from defaults.yaml (temperature=0.8, max_tokens=null).
    prompt = TestCaseGenerationPrompt("def foo():\n    pass", "example/path.py")
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "gpt-4o-mini")

    rendered = prompt.render(module_code="def foo():\n    pass", module_path="example/path.py")
    assert rendered.model == "gpt-4o-mini"
    assert rendered.temperature == 0.8
    assert rendered.max_tokens is None

    # 2. A prompt-specific YAML (refinement) overrides temperature/max_tokens.
    class DummyRefinementPrompt(Prompt):
        _resource_name = "refinement"

        def _template_vars(self):
            return ["prompt"]

    ref_prompt = DummyRefinementPrompt()
    rendered_ref = ref_prompt.render(prompt="fix this")
    assert rendered_ref.temperature == 0.2
    assert rendered_ref.max_tokens == 2000

    # 3. Model always follows the run configuration, even for refinement;
    #    temperature stays the YAML value regardless of run config.
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "custom-model")
    rendered_ref_overridden = ref_prompt.render(prompt="fix this")
    assert rendered_ref_overridden.model == "custom-model"
    assert rendered_ref_overridden.temperature == 0.2
