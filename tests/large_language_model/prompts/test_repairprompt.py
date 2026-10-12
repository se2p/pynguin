#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for RepairPrompt."""

from __future__ import annotations

from pynguin.large_language_model.prompts.repairprompt import RepairPrompt


def test_repair_prompt_validation():
    """Verify variables validation."""
    prompt = RepairPrompt("broken code", "error message")
    assert prompt.broken_code == "broken code"
    assert prompt.error_message == "error message"
    assert prompt._template_vars() == [
        "broken_code",
        "error_message",
        "dependencies",
        "usage_examples",
        "api_signatures",
    ]


def test_repair_prompt_render():
    """Verify render output."""
    prompt = RepairPrompt("def test_x(): pass", "SyntaxError")
    request = prompt.render_request()
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert "def test_x(): pass" in request.messages[1]["content"]
    assert "SyntaxError" in request.messages[1]["content"]


def test_repair_prompt_renders_api_signatures():
    """The module's API signatures appear in the prompt when given."""
    without = RepairPrompt("def test_x(): pass", "TypeError").build_prompt()
    with_api = RepairPrompt(
        "def test_x(): pass", "TypeError", api_signatures="class Foo(bar: int)"
    ).build_prompt()

    assert "API of the Module Under Test" not in without
    assert "class Foo(bar: int)" in with_api
