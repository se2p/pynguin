#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import importlib

import pytest

import pynguin.configuration as config
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.large_language_model.llmagent import (
    LLMAgent,
    get_module_path,
    get_module_source_code,
)
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
    expected_code = "print('Hello, world!')\n"
    model = LLMAgent()
    assert model.extract_python_code_from_llm_output(llm_output) == expected_code


@pytest.mark.skipif(
    not is_api_key_present(),
    reason="OpenAI API key is not provided in the configuration.",
)
def test_extract_python_code_multiple_blocks():
    llm_output = "Text\n```python\nprint('Hello')\n```\nMore text\n```python\nprint('World')\n```"
    expected_code = "print('Hello')\n\nprint('World')\n"
    model = LLMAgent()
    assert model.extract_python_code_from_llm_output(llm_output) == expected_code


def test_require_api_key_missing(monkeypatch):
    monkeypatch.delenv("PYNGUIN_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(config.configuration.large_language_model, "api_key", "")
    monkeypatch.setattr("pynguin.utils.openai_key_resolver.load_dotenv", lambda: None)
    with pytest.raises(ValueError, match="OpenAI API key not found"):
        require_api_key()


def test_is_api_key_present(monkeypatch):
    # Ensure env is cleared for initial checks
    monkeypatch.delenv("PYNGUIN_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
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


def test_get_module_path_for_package(monkeypatch):
    monkeypatch.setattr(config.configuration, "module_name", "markupsafe")
    path = get_module_path()
    assert path.name == "__init__.py"
    assert path.parent.name == "markupsafe"
    assert path.exists()


def test_get_module_path_for_single_file(monkeypatch, tmp_path):
    foo_file = tmp_path / "my_single_mod.py"
    foo_file.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(config.configuration, "project_path", str(tmp_path))
    monkeypatch.setattr(config.configuration, "module_name", "my_single_mod")
    monkeypatch.syspath_prepend(str(tmp_path))

    path = get_module_path()
    assert path.name == "my_single_mod.py"
    assert path.exists()


def test_get_module_source_code_with_module_level_getattr(monkeypatch, tmp_path):
    """Ensure modules with module-level __getattr__ do not trigger TracingAbortedException.

    Regression test for Issue #271.
    """
    code = (
        "def __getattr__(name):\n"
        "    if name == 'val':\n"
        "        return 42\n"
        "    raise AttributeError(name)\n"
    )
    mod_file = tmp_path / "mod_with_getattr.py"
    mod_file.write_text(code, encoding="utf-8")
    monkeypatch.setattr(config.configuration, "project_path", str(tmp_path))
    monkeypatch.setattr(config.configuration, "module_name", "mod_with_getattr")
    monkeypatch.syspath_prepend(str(tmp_path))

    props = SubjectProperties()
    # Import SUT under active tracer (as Pynguin does in _load_sut)
    with install_import_hook("mod_with_getattr", props), props.instrumentation_tracer:
        importlib.import_module("mod_with_getattr")

    # Post-import: tracer is stopped (_current_thread_identifier is None)
    props.instrumentation_tracer.init_trace()

    source = get_module_source_code()
    assert "def __getattr__(name):" in source
    assert "return 42" in source


def test_get_module_source_code_hides_non_visible_members_by_default(monkeypatch):
    """Regression test for Issue #285.

    The LLM must not be shown, and thus cannot be prompted to call, elements
    ``element_visibility`` (default ``PUBLIC``) excludes from the test
    cluster's public API. Uses ``tests.fixtures.cluster.visibility``, the same
    fixture ``tests/analyses/test_module.py`` uses to pin down what the test
    cluster itself considers accessible, so this stays consistent with it.
    """
    monkeypatch.setattr(config.configuration, "module_name", "tests.fixtures.cluster.visibility")

    source = get_module_source_code()

    assert "def public_function" in source
    assert "class PublicClass" in source
    assert "def public_method" in source
    # A class is never hidden by its own name -- only non-public members are.
    assert "class _ProtectedClass" in source
    assert "_protected_function" not in source
    assert "__private_function" not in source
    assert "_protected_method" not in source
    assert "__private_method" not in source


def test_get_module_source_code_keeps_protected_members(monkeypatch):
    monkeypatch.setattr(
        config.configuration, "element_visibility", config.ElementVisibility.PROTECTED
    )
    monkeypatch.setattr(config.configuration, "module_name", "tests.fixtures.cluster.visibility")

    source = get_module_source_code()

    assert "def public_function" in source
    assert "def _protected_function" in source
    assert "def _protected_method" in source
    assert "__private_function" not in source
    assert "__private_method" not in source


def test_get_module_source_code_keeps_all_members_when_visibility_all(monkeypatch):
    monkeypatch.setattr(config.configuration, "element_visibility", config.ElementVisibility.ALL)
    monkeypatch.setattr(config.configuration, "module_name", "tests.fixtures.cluster.visibility")

    source = get_module_source_code()

    assert "def public_function" in source
    assert "def _protected_function" in source
    assert "def __private_function" in source
    assert "def _protected_method" in source
    assert "def __private_method" in source
