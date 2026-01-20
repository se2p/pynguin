#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import pytest

import pynguin.configuration as config
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.prompts.testcasegenerationprompt import (
    TestCaseGenerationPrompt,
)
from pynguin.utils.openai_key_resolver import is_api_key_present, require_api_key


@pytest.mark.skipif(
    not is_api_key_present(),
    reason="OpenAI API key is not provided in the configuration.",
)
def test_extract_python_code_valid():
    llm_output = "Some text\n```python\nprint('Hello, world!')\n```"
    expected_code = "\nprint('Hello, world!')\n"
    model = LLMAgent()
    assert model.extract_python_code_from_llm_output(llm_output) == expected_code


@pytest.mark.skipif(
    not is_api_key_present(),
    reason="OpenAI API key is not provided in the configuration.",
)
def test_extract_python_code_multiple_blocks():
    llm_output = "Text\n```python\nprint('Hello')\n```\nMore text\n```python\nprint('World')\n```"
    expected_code = "\nprint('Hello')\n\n\nprint('World')\n"
    model = LLMAgent()
    assert model.extract_python_code_from_llm_output(llm_output) == expected_code


def test_require_api_key_missing(monkeypatch):
    monkeypatch.delenv("PYNGUIN_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "")
    monkeypatch.setattr("pynguin.utils.openai_key_resolver.load_dotenv", lambda: None)
    with pytest.raises(ValueError, match="OpenAI API key not found"):
        require_api_key()


def test_is_api_key_present(monkeypatch):
    # Ensure env is cleared for initial checks
    monkeypatch.delenv("PYNGUIN_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("pynguin.utils.openai_key_resolver.load_dotenv", lambda: None)

    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "")
    assert is_api_key_present() is False

    monkeypatch.setattr(config.configuration.large_language_model, "api_key", None)
    assert is_api_key_present() is False

    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "    ")
    assert is_api_key_present() is False

    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "valid_api_key")
    assert is_api_key_present() is True

    # When config key is empty but env provides it, it should be present
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "")
    monkeypatch.setenv("PYNGUIN_OPENAI_API_KEY", "env_key")
    assert is_api_key_present() is True


@pytest.mark.skipif(
    not is_api_key_present(),
    reason="OpenAI API key is not provided in the configuration.",
)
def test_openai_model_query_success(mocker):
    config.configuration.large_language_model.enable_response_caching = True
    module_code = "def example_function():\n    return 'Hello, World!'"
    module_path = "/path/to/fake_module.py"
    prompt = TestCaseGenerationPrompt(module_code, module_path)

    # Mock the OpenAI client to avoid real API calls
    mock_response = mocker.Mock()
    mock_response.choices = [mocker.Mock(message=mocker.Mock(content="Generated test code"))]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20

    mock_client = mocker.Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mocker.patch("pynguin.large_language_model.llmagent.openai.OpenAI", return_value=mock_client)

    model = LLMAgent()
    model.clear_cache()

    response = model.query(prompt)

    assert response is not None
    assert model.llm_calls_counter == 1
    assert model.llm_calls_timer > 0


@pytest.mark.skipif(
    not is_api_key_present(),
    reason="OpenAI API key is not provided in the configuration.",
)
def test_openai_model_query_cache(mocker):
    config.configuration.large_language_model.enable_response_caching = True
    module_code = "def example_function():\n    return 'Hello, World!'"
    module_path = "/path/to/fake_module.py"
    prompt = TestCaseGenerationPrompt(module_code, module_path)

    mock_response = mocker.Mock()
    mock_response.choices = [mocker.Mock(message=mocker.Mock(content="Test response"))]
    mock_response.usage.prompt_tokens = 1
    mock_response.usage.completion_tokens = 1

    # Mock the OpenAI client class to return a mock client
    mock_client = mocker.Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mocker.patch("pynguin.large_language_model.llmagent.openai.OpenAI", return_value=mock_client)

    model = LLMAgent()
    model.clear_cache()

    response = model.query(prompt)
    assert response == "Test response"
    assert model.llm_calls_counter == 1

    # Second query should hit the cache
    response_cached = model.query(prompt)
    assert response_cached == "Test response"
    assert model.llm_calls_counter == 1  # Counter should not increment on cache hit
