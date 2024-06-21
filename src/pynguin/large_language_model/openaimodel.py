# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module generates unit tests for a given module using OpenAI's language model."""
import logging
import pathlib
import re
import time

import openai

from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat import ChatCompletionUserMessageParam

import pynguin.configuration as config

from pynguin.large_language_model.caching import Cache
from pynguin.large_language_model.prompts.prompt import Prompt


logger = logging.getLogger(__name__)


def extract_python_code_from_llm_output(llm_output: str) -> str:
    """Extracts Python code blocks from the LLM output.

    Args:
        llm_output: The output from the LLM containing Python code.

    Returns:
        The extracted Python code.

    Raises:
        ValueError: If no Python code block is found in the LLM output.
    """
    code_blocks = re.findall(r"```python([\s\S]+?)```", llm_output)
    if not code_blocks:
        raise ValueError("No Python code block found in the LLM output.")
    return "\n".join(code_blocks)


def get_module_path() -> pathlib.Path:
    """Constructs the file path to the module to be tested.

    Returns:
        The file path to the module.
    """
    return pathlib.Path(config.configuration.project_path) / (
        config.configuration.module_name + ".py"
    )


def get_module_source_code() -> str:
    """Reads and returns the source code of the module.

    Returns:
        The source code of the module.

    Raises:
        FileNotFoundError: If the module file is not found.
    """
    module_path = get_module_path()
    return module_path.read_text()


def is_api_key_present() -> bool:
    """Checks if the OpenAI API key is present and not an empty string.

    Returns:
        bool: True if the API key is present and not empty, False otherwise.
    """
    api_key = config.configuration.large_language_model.api_key
    return bool(api_key and api_key.strip())


def set_api_key():
    """Sets the OpenAI API key from the configuration if it is valid.

    Raises:
        ValueError: If the OpenAI API key is missing or invalid.
    """
    if not is_api_key_present():
        raise ValueError("OpenAI API key is missing.")

    api_key = config.configuration.large_language_model.api_key
    if is_api_key_valid():
        openai.api_key = api_key
    else:
        raise ValueError("OpenAI API key is invalid.")


def is_api_key_valid(
    api_key: str = config.configuration.large_language_model.api_key,
) -> bool:
    """Checks if the provided OpenAI API key is valid.

    Args:
        api_key: The OpenAI API key to validate.

    Returns:
        bool: True if the API key is valid, False otherwise.

    Raises:
        openai.OpenAIError: If the API key is invalid or another error occurs.
    """
    try:
        openai.api_key = api_key
        openai.models.list()  # This would raise an error if the API key is invalid
        return True
    except openai.OpenAIError:
        return False


class OpenAIModel:
    """A class to interact with OpenAI's language model for generating unit tests."""

    def __init__(self):
        """Initializes the OpenAIModel with configuration settings and cache."""
        self._model_name = config.configuration.large_language_model.model_name
        self._max_query_len = (
            config.configuration.large_language_model.max_query_token_length
        )
        self._temperature = config.configuration.large_language_model.temperature
        self._llm_calls_counter = 0
        self._llm_calls_timer = 0

        if config.configuration.large_language_model.enable_response_caching:
            self.cache = Cache()

        set_api_key()

    @property
    def llm_calls_counter(self) -> int:
        """Returns the number of LLM API calls made.

        Returns:
            The number of LLM API calls made.
        """
        return self._llm_calls_counter

    @property
    def llm_calls_timer(self) -> float:
        """Returns the total time spent on LLM API calls.

        Returns:
            The total time spent on LLM API calls.
        """
        return self._llm_calls_timer

    def query(self, prompt: Prompt, max_tokens: int = 1000) -> str | None:
        """Sends a query to the OpenAI API and returns the response.

        Args:
            prompt: The prompt object to build the query.
            max_tokens: The maximum number of tokens to generate in the response.

        Returns:
            The response from the OpenAI API, or None if the response is empty.
        """
        prompt_text = prompt.build_prompt()

        if config.configuration.large_language_model.enable_response_caching:
            cached_response = self.cache.get(prompt_text)
            if cached_response:
                return cached_response

        start_time = time.time_ns()
        self._llm_calls_counter += 1

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionUserMessageParam(role="user", content=prompt_text)
        ]
        try:
            response = openai.chat.completions.create(
                model=self._model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=self._temperature,
            )
            response_text = response.choices[0].message.content
            if (
                config.configuration.large_language_model.enable_response_caching
                and response_text is not None
            ):
                self.cache.set(prompt_text, response_text)
            return response_text
        except openai.OpenAIError as e:
            logger.error("An error occurred while querying the OpenAI API: %s", e)
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
        return None

    def clear_cache(self):
        """Clears all entries in the cache."""
        self.cache.clear()
