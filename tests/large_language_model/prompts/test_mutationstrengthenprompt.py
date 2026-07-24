#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for MutationStrengthenPrompt."""

from __future__ import annotations

from pynguin.large_language_model.prompts.mutationstrengthenprompt import (
    MutationStrengthenPrompt,
)


def test_mutation_strengthen_prompt_validation():
    """Verify variables validation."""
    prompt = MutationStrengthenPrompt(
        "module code", "test code", "surviving mutants", "focal method"
    )
    assert prompt.module_code == "module code"
    assert prompt.test_code == "test code"
    assert prompt.surviving_mutants == "surviving mutants"
    assert prompt.focal_method == "focal method"
    assert prompt._template_vars() == [
        "module_code",
        "test_code",
        "surviving_mutants",
        "focal_method",
    ]


def test_mutation_strengthen_prompt_render():
    """Verify render output."""
    prompt = MutationStrengthenPrompt("module", "def test_x(): pass", "survivor details", "focal")
    request = prompt.render_request()
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert "module" in request.messages[1]["content"]
    assert "def test_x(): pass" in request.messages[1]["content"]
    assert "survivor details" in request.messages[1]["content"]
    assert "focal" in request.messages[1]["content"]
