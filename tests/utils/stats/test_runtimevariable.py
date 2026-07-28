#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the RuntimeVariable enum."""

from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def test_llm_related_runtime_variables():
    """Test that all LLM-related runtime variables are defined."""
    # Test LLM strategy
    assert RuntimeVariable.LLMStrategy == "LLMStrategy"

    # Test LLM call statistics
    assert RuntimeVariable.TotalLLMCalls == "TotalLLMCalls"
    assert RuntimeVariable.TotalLLMInputTokens == "TotalLLMInputTokens"
    assert RuntimeVariable.TotalLLMOutputTokens == "TotalLLMOutputTokens"
    assert RuntimeVariable.TotalCodelessLLMResponses == "TotalCodelessLLMResponses"
    assert RuntimeVariable.LLMQueryTime == "LLMQueryTime"

    # Test LLM test case statistics
    assert RuntimeVariable.TotalLTCs == "TotalLTCs"
    assert RuntimeVariable.LLMAdmitted == "LLMAdmitted"
    assert RuntimeVariable.LLMAdmittedUnresolvedCall == "LLMAdmittedUnresolvedCall"
    assert RuntimeVariable.LLMAdmittedImport == "LLMAdmittedImport"
    assert RuntimeVariable.LLMAdmittedCompound == "LLMAdmittedCompound"
    assert RuntimeVariable.LLMDroppedUnknownNames == "LLMDroppedUnknownNames"
    assert RuntimeVariable.LLMDroppedUnsupportedShape == "LLMDroppedUnsupportedShape"
    assert RuntimeVariable.LLMAssertionLifted == "LLMAssertionLifted"
    assert RuntimeVariable.LLMAssertionKeptRaw == "LLMAssertionKeptRaw"
    assert RuntimeVariable.LLMAssertionDropped == "LLMAssertionDropped"

    # Test LLM coverage statistics
    assert RuntimeVariable.CoverageBeforeLLMCall == "CoverageBeforeLLMCall"
    assert RuntimeVariable.CoverageAfterLLMCall == "CoverageAfterLLMCall"

    # Test LLM assertion statistics
    assert RuntimeVariable.TotalAssertionsAddedFromLLM == "TotalAssertionsAddedFromLLM"
    assert RuntimeVariable.TotalAssertionsReceivedFromLLM == "TotalAssertionsReceivedFromLLM"


def test_runtime_variable_repr():
    """Test the __repr__ method of RuntimeVariable."""
    assert repr(RuntimeVariable.LLMStrategy) == "LLMStrategy"
