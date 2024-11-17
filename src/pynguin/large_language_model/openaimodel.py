# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module generates unit tests for a given module using OpenAI's language model."""
import inspect
import logging
import pathlib
import re
import time

import datetime
from pathlib import Path

import openai

from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat import ChatCompletionUserMessageParam

import pynguin.configuration as config

from pynguin.analyses.module import import_module
from pynguin.large_language_model.caching import Cache
from pynguin.large_language_model.parsing.rewriter import rewrite_tests
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.prompts.testcasegenerationprompt import (
    TestCaseGenerationPrompt,
)


logger = logging.getLogger(__name__)


def save_prompt_info_to_file(prompt_message: str, full_response: str):
    """Append a prompt and its response, with a timestamp, to a log file.

    Parameters:
    - prompt_message: The prompt text.
    - full_response: The response text.

    Logs an error if writing to the file fails.
    """
    try:
        output_dir = Path(config.configuration.statistics_output.report_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "prompt_info.txt"

        with (output_file.open(mode="a", encoding="utf-8") as file):
            timestamp = datetime.datetime.now(datetime.timezone.utc
                                              ).strftime("%Y-%m-%d %H:%M:%S")
            file.write(f"==============\nDate and Time: {timestamp}\n==============\n")
            file.write(f"Prompt:\n{prompt_message}\n")
            file.write("==============\nFull Response\n==============\n")
            file.write(full_response + "\n")
            file.write("==============\n\n")
    except OSError as error:
        logging.exception("Error while writing prompt information to file: %s", error)


def save_llm_tests_to_file(test_cases: str):
    """Save extracted test cases to a Python (.py) file.

    Args:
        test_cases: The test cases to save, formatted as Python code.

    Raises:
        OSError: If there is an issue writing to the file, logs the exception.
    """
    try:
        output_dir = Path(config.configuration.statistics_output.report_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "generated_llm_tests.py"
        with output_file.open(mode="w", encoding="utf-8") as file:
            file.write("# LLM generated and rewritten (in Pynguin format) test cases\n")
            file.write(
                "# Date and time: "
                + datetime.datetime.now(datetime.timezone.utc)
                .strftime("%Y-%m-%d %H:%M:%S")
                + "\n\n"
            )
            file.write(test_cases)
        logging.info("Test cases saved successfully to %s", output_file)
    except OSError as error:
        logging.exception(
            "Error while saving LLM-generated test cases to file: %s", error
        )


def get_module_path() -> Path:
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
    module = import_module(config.configuration.module_name)
    return inspect.getsource(module)


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


def is_api_key_valid() -> bool:
    """Checks if the provided OpenAI API key is valid.

    Returns:
        bool: True if the API key is valid, False otherwise.

    Raises:
        openai.OpenAIError: If the API key is invalid or another error occurs.
    """
    try:
        openai.api_key = config.configuration.large_language_model.api_key
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
        self._llm_calls_with_no_python_code = 0

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
        return self._llm_calls_timer / 1e9

    @property
    def llm_calls_with_no_python_code(self) -> int:
        """Returns the number of LLM API calls that has no Python code.

        Returns:
            The number of LLM API calls that has no Python code.
        """
        return self._llm_calls_with_no_python_code

    def query(self, prompt: Prompt) -> str | None:
        """Sends a query to the OpenAI API and returns the response.

        Args:
            prompt: The prompt object to build the query.

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
            ChatCompletionUserMessageParam(role="user", content=f"${prompt_text}")
        ]
        try:
            response = openai.chat.completions.create(
                model=self._model_name,
                messages=messages,
                max_tokens=self._max_query_len,
                temperature=self._temperature,
            )
            response_text = response.choices[0].message.content
            if (
                config.configuration.large_language_model.enable_response_caching
                and response_text is not None
            ):
                self.cache.set(prompt_text, response_text)
            save_prompt_info_to_file(prompt_text, response_text)
            return response_text
        except openai.OpenAIError as e:
            logger.error("An error occurred while querying the OpenAI API: %s", e)
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
        return None

    def clear_cache(self):
        """Clears all entries in the cache."""
        self.cache.clear()

    def generate_tests_for_module_under_test(self) -> str | None:
        """Generates test cases for the module under test.

        Returns:
            The generated test cases as a string or
            None if no test cases were generated.
        """
        module_code = get_module_source_code()
        module_path = get_module_path()
        prompt = TestCaseGenerationPrompt(module_code, str(module_path))
        return self.query(prompt)

    def extract_python_code_from_llm_output(self, llm_output: str) -> str:
        """Extracts Python code blocks from the LLM output.

        Args:
            llm_output: The output from the LLM containing Python code.

        Returns:
            The extracted Python code.

        Raises:
            ValueError: If no Python code block is found in the LLM output.
        """
        code_blocks = re.findall(r"```python([\s\S]+?)(?:```|$)", llm_output)
        if not code_blocks:
            self._llm_calls_with_no_python_code += 1
            return llm_output
        return "\n".join(code_blocks)

    def extract_test_cases_from_llm_output(self, llm_output: str) -> str:
        """Extracts test cases from the LLM output.

        Args:
            llm_output: The output from the LLM containing test cases.

        Returns:
            The extracted test cases.
        """
        python_code = self.extract_python_code_from_llm_output(llm_output)
        logger.debug("Extracted Python code: %s.", python_code)
        generated_tests: dict[str, str] = rewrite_tests(python_code)
        tests_with_line_breaks = "\n\n".join(generated_tests.values())
        logger.debug("Rewritten tests: %s.", tests_with_line_breaks)
        save_llm_tests_to_file(tests_with_line_breaks)
        return tests_with_line_breaks
