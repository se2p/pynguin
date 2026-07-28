#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for the module-level refinement prompts."""

from __future__ import annotations

import pytest

from pynguin.large_language_model.prompts import (
    ModuleReadabilityRefinementPrompt,
    ModuleRefinementPrompt,
    ModuleSemanticAssertionsPrompt,
)

_MODULE_CODE = "import module_0\n\ndef test_case_0():\n    assert module_0.f(1) == 2\n"
_SUT_CONTEXT = "def f(x): returns x + 1"

_MODULE_PROMPT_CLASSES = [
    ModuleReadabilityRefinementPrompt,
    ModuleSemanticAssertionsPrompt,
    ModuleRefinementPrompt,
]


@pytest.mark.parametrize("prompt_cls", _MODULE_PROMPT_CLASSES)
def test_module_prompt_template_vars(prompt_cls):
    prompt = prompt_cls(module_test_code=_MODULE_CODE, sut_context=_SUT_CONTEXT)
    assert prompt.module_test_code == _MODULE_CODE
    assert prompt.sut_context == _SUT_CONTEXT
    assert prompt._template_vars() == ["module_test_code", "sut_context"]


@pytest.mark.parametrize("prompt_cls", _MODULE_PROMPT_CLASSES)
def test_module_prompt_render_interpolates_and_is_deterministic(prompt_cls):
    prompt = prompt_cls(module_test_code=_MODULE_CODE, sut_context=_SUT_CONTEXT)
    request = prompt.render_request()

    # System message present + user message carries both template variables.
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    user_content = request.messages[1]["content"]
    assert _SUT_CONTEXT in user_content
    assert "def test_case_0():" in user_content

    # Deterministic (temperature 0.0) and a raised token budget for whole-module output.
    assert request.temperature == 0.0
    assert request.max_tokens is not None
    assert request.max_tokens >= 8000


@pytest.mark.parametrize("prompt_cls", _MODULE_PROMPT_CLASSES)
def test_module_prompt_preserves_module_0_prefix_instruction(prompt_cls):
    prompt = prompt_cls(module_test_code=_MODULE_CODE, sut_context=_SUT_CONTEXT)
    user_content = prompt.render_request().messages[1]["content"]
    assert "module_0." in user_content
    # Every module prompt must forbid dropping/renaming test functions.
    assert "original name" in user_content.lower()
