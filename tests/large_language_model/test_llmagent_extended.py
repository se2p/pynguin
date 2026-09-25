#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Extended tests for the LLMAgent module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.large_language_model.llmagent import (
    LLMAgent,
    _truncate_to_context_budget,  # noqa: PLC2701
    get_module_source_code,
    get_part_of_source_code,
    save_prompt_info_to_file,
    shorten_line_annotations,
)
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.request import RenderedRequest
from pynguin.utils.report import CoverageEntry, LineAnnotation
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def test_truncate_to_context_budget_truncates_over_limit(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "max_context_chars", 10)
    out = _truncate_to_context_budget("y" * 50)
    assert out.startswith("y" * 10)
    assert "truncated" in out
    assert len(out) < 50 + 60  # marker only, not the full source


def test_truncate_to_context_budget_keeps_small_source(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "max_context_chars", 10)
    assert _truncate_to_context_budget("abc") == "abc"


def test_truncate_to_context_budget_disabled(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "max_context_chars", 0)
    source = "z" * 100
    assert _truncate_to_context_budget(source) == source


def test_save_prompt_info_to_file(tmp_path, monkeypatch):
    """Test saving prompt info to a file."""
    # Mock the configuration to use the temporary directory
    monkeypatch.setattr(config.configuration.statistics_output, "report_dir", str(tmp_path))

    # Test data
    prompt_message = "Test prompt"
    full_response = "Test response"

    # Call the function
    save_prompt_info_to_file(prompt_message, full_response)

    # Check that the file was created and contains the expected content
    output_file = tmp_path / "prompt_info.txt"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Test prompt" in content
    assert "Test response" in content
    assert "Date and Time:" in content


@pytest.mark.usefixtures("monkeypatch")
def test_save_prompt_info_to_file_error():
    """Test error handling when saving prompt info fails."""
    # Mock the open function to raise an OSError
    mock_open_func = mock_open()
    mock_open_func.side_effect = OSError("Test error")

    with patch("pathlib.Path.open", mock_open_func):
        # Call the function - it should handle the error without raising an exception
        save_prompt_info_to_file("Test prompt", "Test response")
        # The function should log the error, but we can't easily test that


def test_get_module_source_code(monkeypatch):
    """Test getting the source code of a module."""
    # Mock the import_module function
    mock_module = MagicMock()
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.import_module", lambda _: mock_module
    )

    # Mock the getsource function
    expected_source = "def test_function():\n    pass"
    monkeypatch.setattr("inspect.getsource", lambda _: expected_source)

    # Call the function
    result = get_module_source_code()

    # Check the result
    assert result == expected_source


def _mock_require_api_key():
    """Helper to create a mock SecretStr for API key."""
    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-api-key"
    return mock_key


def test_llm_agent_init_with_caching(monkeypatch):
    """Test LLMAgent initialization with caching enabled."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")

    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Check that the cache was initialized
    assert hasattr(agent, "cache")

    # Check that the properties return the expected values
    assert agent.llm_calls_counter == 0
    assert agent.llm_calls_timer == 0
    assert agent.llm_input_tokens == 0
    assert agent.llm_output_tokens == 0
    assert agent.llm_calls_with_no_python_code == 0
    assert agent.llm_test_case_handler is not None


def test_query_with_cache_hit(monkeypatch):
    """Test query method with a cache hit."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")

    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create a mock prompt whose rendered request carries the user content.
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.render_request.return_value = RenderedRequest(
        messages=[{"role": "user", "content": "Test prompt"}],
        model="test-model",
        temperature=0.5,
    )

    # Create a mock cache
    mock_cache = MagicMock()
    mock_cache.get.return_value = "Cached response"

    # Create an instance of LLMAgent with the mock cache
    agent = LLMAgent()
    agent.cache = mock_cache

    # Mock _log_and_track_llm_stats to avoid actual logging
    agent._log_and_track_llm_stats = MagicMock()

    # Call the query method
    result = agent.query(mock_prompt)

    # Check that the cache was used and the result is correct
    assert mock_cache.get.call_count == 1
    called_request = mock_cache.get.call_args[0][0]
    assert called_request.messages[-1]["content"] == "Test prompt"
    assert result == "Cached response"
    assert agent.llm_calls_counter == 0  # Counter should not increment on cache hit


def test_query_with_openai_error(monkeypatch):
    """Test query method when OpenAI raises an error."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "test_api_key")

    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create a mock prompt
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.render_request.return_value = RenderedRequest(
        messages=[{"role": "user", "content": "Test prompt"}],
        model="test-model",
        temperature=0.5,
    )

    # Create a mock cache that returns None (cache miss)
    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    # Create a patch for the query method to simulate an OpenAI error
    with patch.object(LLMAgent, "query", side_effect=lambda _p: None) as mock_query:
        # Create an instance of LLMAgent with the mock cache
        agent = LLMAgent()
        agent.cache = mock_cache

        # Mock _log_and_track_llm_stats to avoid actual logging
        agent._log_and_track_llm_stats = MagicMock()

        # Call the query method (this will use our mocked version)
        result = mock_query(mock_prompt)

        # Check that the result is None
        assert result is None


def test_query_successful_response(monkeypatch):
    """Test query method with a successful response from OpenAI."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "test_api_key")

    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create a mock prompt
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.render_request.return_value = RenderedRequest(
        messages=[{"role": "user", "content": "Test prompt"}],
        model="test-model",
        temperature=0.5,
    )

    # Create a mock cache that returns None (cache miss)
    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    # Mock save_prompt_info_to_file to avoid file operations
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.save_prompt_info_to_file", lambda *_args: None
    )

    # Create a custom response for our test
    test_response = "Test response"

    # Create a patch for the query method to return our test response
    with patch.object(LLMAgent, "query", return_value=test_response) as mock_query:
        # Create an instance of LLMAgent with the mock cache
        agent = LLMAgent()
        agent.cache = mock_cache

        # Set the token counts directly
        agent._llm_input_tokens = 10
        agent._llm_output_tokens = 20

        # Mock _log_and_track_llm_stats to avoid actual logging
        agent._log_and_track_llm_stats = MagicMock()

        # Call the query method (this will use our mocked version)
        result = mock_query(mock_prompt)

        # Check that the result is correct
        assert result == test_response


def test_clear_cache(monkeypatch):
    """Test clear_cache method."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "test_api_key")

    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create a mock cache
    mock_cache = MagicMock()

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Replace the cache with our mock
    agent.cache = mock_cache

    # Call the clear_cache method
    agent.clear_cache()

    # Check that the cache's clear method was called
    mock_cache.clear.assert_called_once()


def test_call_llm_for_uncovered_targets(monkeypatch):
    """Test call_llm_for_uncovered_targets method."""
    # Mock the necessary functions
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.get_module_source_code",
        lambda: "def test_function():\n    pass",
    )
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.get_module_path", lambda: Path("/path/to/module.py")
    )

    # Create a mock agent
    agent = MagicMock(spec=LLMAgent)
    agent.query.return_value = "Test response"

    # Call the method
    with patch.object(LLMAgent, "query", return_value="Test response"):
        result = LLMAgent.call_llm_for_uncovered_targets(agent, {})

    # Check the result
    assert result == "Test response"


def test_extract_python_code_no_code(monkeypatch):
    """Test extract_python_code_from_llm_output with no Python code blocks."""
    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Reset the counter
    agent._llm_calls_with_no_python_code = 0

    # Call the method with text that doesn't contain Python code blocks
    result = agent.extract_python_code_from_llm_output("This is just text, no code here.")

    # Prose that is not valid Python yields no extracted code. The codeless-response
    # metric is now counted once in the client, not recomputed here.
    assert not result
    assert agent.llm_calls_with_no_python_code == 0


def test_extract_python_code_none_input(monkeypatch):
    """Test extract_python_code_from_llm_output with None input."""
    # Mock require_api_key and OpenAI client to avoid actual API calls
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Call the method with None
    result = agent.extract_python_code_from_llm_output(None)

    # Check that the result is an empty string
    assert not result


def _llm_stats() -> dict[RuntimeVariable, int | float]:
    output_variables = stat.statistics_tracker.output_variables
    return {
        variable: output_variables[variable.name].value
        for variable in (
            RuntimeVariable.TotalLLMCalls,
            RuntimeVariable.LLMQueryTime,
            RuntimeVariable.TotalLLMOutputTokens,
            RuntimeVariable.TotalLLMInputTokens,
            RuntimeVariable.TotalCodelessLLMResponses,
        )
    }


def _set_agent_stats(agent: LLMAgent, calls: int, codeless: int, timer: int, tokens: int):
    agent._llm_calls_counter = calls
    agent._llm_calls_with_no_python_code = codeless
    agent._llm_calls_timer = timer
    agent._llm_input_tokens = tokens
    agent._llm_output_tokens = 2 * tokens


@pytest.fixture
def stats_agent_factory(monkeypatch):
    monkeypatch.setattr(
        "pynguin.large_language_model.client.require_api_key", _mock_require_api_key
    )
    monkeypatch.setattr("pynguin.large_language_model.llmagent.openai.OpenAI", MagicMock)
    monkeypatch.setattr("pynguin.large_language_model.llmagent._logger", MagicMock())
    return LLMAgent


def test_log_and_track_llm_stats(stats_agent_factory):
    """Test _log_and_track_llm_stats method."""
    agent = stats_agent_factory()
    _set_agent_stats(agent, calls=10, codeless=3, timer=5_000_000_000, tokens=100)

    agent._log_and_track_llm_stats()

    assert _llm_stats() == {
        RuntimeVariable.TotalLLMCalls: 10,
        RuntimeVariable.LLMQueryTime: 5_000_000_000,
        RuntimeVariable.TotalLLMOutputTokens: 200,
        RuntimeVariable.TotalLLMInputTokens: 100,
        RuntimeVariable.TotalCodelessLLMResponses: 3,
    }


def test_log_and_track_llm_stats_repeated_reports_do_not_double_count(stats_agent_factory):
    agent = stats_agent_factory()
    _set_agent_stats(agent, calls=1, codeless=0, timer=10, tokens=5)
    agent._log_and_track_llm_stats()
    _set_agent_stats(agent, calls=3, codeless=1, timer=30, tokens=15)
    agent._log_and_track_llm_stats()

    assert _llm_stats() == {
        RuntimeVariable.TotalLLMCalls: 3,
        RuntimeVariable.LLMQueryTime: 30,
        RuntimeVariable.TotalLLMOutputTokens: 30,
        RuntimeVariable.TotalLLMInputTokens: 15,
        RuntimeVariable.TotalCodelessLLMResponses: 1,
    }


def test_log_and_track_llm_stats_sums_over_agents(stats_agent_factory):
    """Each agent's report adds to the totals instead of overwriting them."""
    search_agent = stats_agent_factory()
    assertion_agent = stats_agent_factory()

    _set_agent_stats(search_agent, calls=4, codeless=1, timer=400, tokens=40)
    search_agent._log_and_track_llm_stats()
    _set_agent_stats(assertion_agent, calls=2, codeless=0, timer=200, tokens=20)
    assertion_agent._log_and_track_llm_stats()
    _set_agent_stats(search_agent, calls=5, codeless=1, timer=500, tokens=50)
    search_agent._log_and_track_llm_stats()

    assert _llm_stats() == {
        RuntimeVariable.TotalLLMCalls: 7,
        RuntimeVariable.LLMQueryTime: 700,
        RuntimeVariable.TotalLLMOutputTokens: 140,
        RuntimeVariable.TotalLLMInputTokens: 70,
        RuntimeVariable.TotalCodelessLLMResponses: 1,
    }


def test_log_and_track_llm_stats_after_client_usage_reset(stats_agent_factory):
    agent = stats_agent_factory()
    _set_agent_stats(agent, calls=4, codeless=0, timer=40, tokens=40)
    agent._log_and_track_llm_stats()
    # The client's token counters restart from zero, the agent's own counters do not.
    _set_agent_stats(agent, calls=5, codeless=0, timer=50, tokens=10)
    agent._log_and_track_llm_stats()

    assert _llm_stats()[RuntimeVariable.TotalLLMInputTokens] == 50
    assert _llm_stats()[RuntimeVariable.TotalLLMCalls] == 5


def test_generate_assertions_for_test_case(monkeypatch):
    """Test generate_assertions_for_test_case method."""
    # Mock the necessary functions
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.get_module_source_code",
        lambda: "def test_function():\n    pass",
    )

    # Create a mock agent
    agent = MagicMock(spec=LLMAgent)
    agent.query.return_value = "```python\nassert True\n```"
    agent.extract_python_code_from_llm_output.return_value = "assert True"

    # Call the method
    with (
        patch.object(LLMAgent, "query", return_value="```python\nassert True\n```"),
        patch.object(LLMAgent, "extract_python_code_from_llm_output", return_value="assert True"),
    ):
        result = LLMAgent.generate_assertions_for_test_case(agent, "def test_case():\n    pass")

    # Check the result
    assert result == "assert True"


def test_get_part_of_source_code(monkeypatch):
    """Test getting the filtered source code of a module."""
    mock_module = MagicMock()
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.import_module", lambda _: mock_module
    )

    # Mock the getsource function
    source_lines = [
        "def test_function(x):",
        "    if x==3:",
        "        return True",
        "    return False",
    ]
    expected_code = (
        "   1: def test_function(x):\n   2:     if x==3:\n   3:         return "
        "True\n   4:     return False"
    )
    monkeypatch.setattr("inspect.getsourcelines", lambda _: (source_lines, 1))

    result = get_part_of_source_code("test_function")

    assert result == expected_code


def test_get_part_of_source_code_fail(monkeypatch):
    """Test getting the source code of a module."""

    class NoneReturningMock(Mock):
        def __getattr__(self, name):
            return None

    mock_module = NoneReturningMock()
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.import_module", lambda _: mock_module
    )
    result = get_part_of_source_code("foo")

    assert not result


def test_shorten_line_annotations(monkeypatch):
    """Test shortening the line annotations."""
    mock_module = MagicMock()
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.import_module", lambda _: mock_module
    )

    source_lines = [
        "def test_function(x):",
        "    if x==3:",
        "        return True",
        "    return False",
    ]

    monkeypatch.setattr("inspect.getsourcelines", lambda _: (source_lines, 1))
    entry1 = CoverageEntry(1, 1)
    entry2 = CoverageEntry(1, 2)
    annotation: LineAnnotation = LineAnnotation(1, entry1, entry1, entry1, entry1)
    annotation2: LineAnnotation = LineAnnotation(2, entry1, entry2, entry1, entry1)
    annotation3: LineAnnotation = LineAnnotation(3, entry1, entry1, entry1, entry1)
    annotation4: LineAnnotation = LineAnnotation(4, entry1, entry1, entry1, entry1)
    annotation5: LineAnnotation = LineAnnotation(5, entry1, entry1, entry1, entry1)
    annotations = [annotation, annotation2, annotation3, annotation4, annotation5]

    result = shorten_line_annotations(annotations, "test_function")
    expected_annotations = [annotation, annotation2, annotation3, annotation4]
    assert result == expected_annotations


def test_shorten_line_annotations_fail(monkeypatch):
    """Test shortening the line annotations."""

    class NoneReturningMock(Mock):
        def __getattr__(self, name):
            return None

    mock_module = NoneReturningMock()
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.import_module", lambda _: mock_module
    )
    entry1 = CoverageEntry(1, 1)
    annotation: LineAnnotation = LineAnnotation(1, entry1, entry1, entry1, entry1)
    annotations = [annotation, annotation, annotation]

    result = shorten_line_annotations(annotations, "foo")

    assert result == []


def test_llmagent_client_property_and_cancel_all(monkeypatch):
    mock_secret = MagicMock()
    mock_secret.get_secret_value.return_value = "fake"
    monkeypatch.setattr(
        "pynguin.large_language_model.llmagent.require_api_key", lambda: mock_secret
    )
    monkeypatch.setattr("pynguin.large_language_model.client.require_api_key", lambda: mock_secret)
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", MagicMock)

    agent = LLMAgent()
    assert agent.client is agent._client

    with patch.object(agent._client, "cancel_all") as mock_cancel:
        agent.cancel_all()
        mock_cancel.assert_called_once()
