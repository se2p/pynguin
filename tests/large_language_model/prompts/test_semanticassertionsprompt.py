#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for SemanticAssertionsPrompt."""

from __future__ import annotations

from pynguin.large_language_model.prompts.semanticassertionsprompt import (
    SemanticAssertionsPrompt,
)


def test_semantic_assertions_prompt_validation():
    """Verify variables validation."""
    prompt = SemanticAssertionsPrompt("sut context", "focal method", "test code")
    assert prompt.sut_context == "sut context"
    assert prompt.focal_method == "focal method"
    assert prompt.test_code == "test code"
    assert prompt._template_vars() == ["sut_context", "focal_method", "test_code"]


def test_semantic_assertions_prompt_render():
    """Verify render output."""
    prompt = SemanticAssertionsPrompt("doc and signature", "add", "def test_add(): pass")
    request = prompt.render_request()
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert "doc and signature" in request.messages[1]["content"]
    assert "add" in request.messages[1]["content"]
    assert "def test_add(): pass" in request.messages[1]["content"]
