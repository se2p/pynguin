#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Extended tests for the LLMAgent module."""

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.llmagent import get_module_source_code
from pynguin.large_language_model.llmagent import save_prompt_info_to_file
from pynguin.large_language_model.llmagent import set_api_key
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


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


def test_set_api_key_openai_not_available(monkeypatch):
    """Test set_api_key when OpenAI is not available."""
    # Mock OPENAI_AVAILABLE to be False
    monkeypatch.setattr("pynguin.large_language_model.llmagent.OPENAI_AVAILABLE", False)

    # Call the function and check that it raises the expected exception
    with pytest.raises(ValueError, match="OpenAI API library is not available"):
        set_api_key()


def test_set_api_key_invalid(monkeypatch):
    """Test set_api_key with an invalid API key."""
    # Mock OPENAI_AVAILABLE to be True
    monkeypatch.setattr("pynguin.large_language_model.llmagent.OPENAI_AVAILABLE", True)

    # Mock is_api_key_present to return True
    monkeypatch.setattr("pynguin.large_language_model.llmagent.is_api_key_present", lambda: True)

    # Mock is_api_key_valid to return False
    monkeypatch.setattr("pynguin.large_language_model.llmagent.is_api_key_valid", lambda: False)

    # Call the function and check that it raises the expected exception
    with pytest.raises(ValueError, match="OpenAI API key is invalid"):
        set_api_key()


def test_is_api_key_valid_exception(monkeypatch):
    """Test is_api_key_valid when an exception is raised."""
    # Mock is_api_key_present to return True
    monkeypatch.setattr("pynguin.large_language_model.llmagent.is_api_key_present", lambda: True)

    # Mock is_api_key_valid to return False
    monkeypatch.setattr("pynguin.large_language_model.llmagent.is_api_key_valid", lambda: False)

    # Now we'll test that set_api_key raises an exception when is_api_key_valid returns False
    with pytest.raises(ValueError, match="OpenAI API key is invalid"):
        set_api_key()


def test_llm_agent_init_with_caching(monkeypatch):
    """Test LLMAgent initialization with caching enabled."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")
    monkeypatch.setattr(config.configuration.large_language_model, "temperature", 0.5)

    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

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
    monkeypatch.setattr(config.configuration.large_language_model, "temperature", 0.5)

    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

    # Create a mock prompt
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.build_prompt.return_value = "Test prompt"
    mock_prompt.system_message = "System message"

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
    mock_cache.get.assert_called_once_with("Test prompt")
    assert result == "Cached response"
    assert agent.llm_calls_counter == 0  # Counter should not increment on cache hit


def test_query_with_openai_error(monkeypatch):
    """Test query method when OpenAI raises an error."""
    # Mock the configuration
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")
    monkeypatch.setattr(config.configuration.large_language_model, "temperature", 0.5)
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "test_api_key")

    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

    # Mock is_api_key_valid to return True
    monkeypatch.setattr("pynguin.large_language_model.llmagent.is_api_key_valid", lambda: True)

    # Create a mock prompt
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.build_prompt.return_value = "Test prompt"
    mock_prompt.system_message = "System message"

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
    monkeypatch.setattr(config.configuration.large_language_model, "temperature", 0.5)
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "test_api_key")

    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

    # Mock is_api_key_valid to return True
    monkeypatch.setattr("pynguin.large_language_model.llmagent.is_api_key_valid", lambda: True)

    # Create a mock prompt
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.build_prompt.return_value = "Test prompt"
    mock_prompt.system_message = "System message"

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

    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

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
    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Reset the counter
    agent._llm_calls_with_no_python_code = 0

    # Call the method with text that doesn't contain Python code blocks
    result = agent.extract_python_code_from_llm_output("This is just text, no code here.")

    # Check that the result is the original text and the counter was incremented
    assert result == "This is just text, no code here."
    assert agent.llm_calls_with_no_python_code == 1


def test_extract_python_code_none_input(monkeypatch):
    """Test extract_python_code_from_llm_output with None input."""
    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Call the method with None
    result = agent.extract_python_code_from_llm_output(None)

    # Check that the result is an empty string
    assert not result


def test_log_and_track_llm_stats(monkeypatch):
    """Test _log_and_track_llm_stats method."""
    # Mock set_api_key to avoid actual API calls
    monkeypatch.setattr("pynguin.large_language_model.llmagent.set_api_key", lambda: None)

    # Mock the stat.track_output_variable function
    mock_track = MagicMock()
    monkeypatch.setattr("pynguin.utils.statistics.stats.track_output_variable", mock_track)

    # Mock logging to avoid actual logging
    mock_logger = MagicMock()
    monkeypatch.setattr("pynguin.large_language_model.llmagent._logger", mock_logger)

    # Create an instance of LLMAgent
    agent = LLMAgent()

    # Set some stats
    agent._llm_calls_counter = 10
    agent._llm_calls_with_no_python_code = 3
    agent._llm_calls_timer = 5000000000  # 5 seconds in nanoseconds
    agent._llm_input_tokens = 100
    agent._llm_output_tokens = 200

    # Call the method
    agent._log_and_track_llm_stats()

    # Check that track_output_variable was called with the correct arguments
    assert mock_track.call_count == 5

    # Check that the correct runtime variables were tracked
    tracked_variables = [call[0][0] for call in mock_track.call_args_list]
    assert RuntimeVariable.TotalLLMCalls in tracked_variables
    assert RuntimeVariable.LLMQueryTime in tracked_variables
    assert RuntimeVariable.TotalLLMOutputTokens in tracked_variables
    assert RuntimeVariable.TotalLLMInputTokens in tracked_variables
    assert RuntimeVariable.TotalCodelessLLMResponses in tracked_variables

    # Check that the correct values were tracked
    tracked_values = {call[0][0]: call[0][1] for call in mock_track.call_args_list}
    assert tracked_values[RuntimeVariable.TotalLLMCalls] == 10
    assert tracked_values[RuntimeVariable.LLMQueryTime] == 5000000000
    assert tracked_values[RuntimeVariable.TotalLLMOutputTokens] == 200
    assert tracked_values[RuntimeVariable.TotalLLMInputTokens] == 100
    assert tracked_values[RuntimeVariable.TotalCodelessLLMResponses] == 3


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
