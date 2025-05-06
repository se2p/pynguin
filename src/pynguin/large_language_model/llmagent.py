# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module generates unit tests for a given module using OpenAI's language model."""

import datetime
import inspect
import logging
import pathlib
import re
import time

from pathlib import Path


try:
    import openai

    from openai.types.chat import ChatCompletionMessageParam
    from openai.types.chat import ChatCompletionSystemMessageParam
    from openai.types.chat import ChatCompletionUserMessageParam

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat

from pynguin.analyses.module import import_module
from pynguin.large_language_model.caching import Cache
from pynguin.large_language_model.llmtestcasehandler import LLMTestCaseHandler
from pynguin.large_language_model.prompts.assertiongenerationprompt import (
    AssertionGenerationPrompt,
)
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.prompts.testcasegenerationprompt import (
    TestCaseGenerationPrompt,
)
from pynguin.large_language_model.prompts.uncoveredtargetsprompt import (
    UncoveredTargetsPrompt,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


_logger = logging.getLogger(__name__)


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

        with output_file.open(mode="a", encoding="utf-8") as file:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            file.write(f"==============\nDate and Time: {timestamp}\n==============\n")
            file.write(f"Prompt:\n{prompt_message}\n")
            file.write("==============\nFull Response\n==============\n")
            file.write(full_response + "\n")
            file.write("==============\n\n")
    except OSError as error:
        _logger.exception("Error while writing prompt information to file: %s", error)


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
    if not OPENAI_AVAILABLE:
        raise ValueError(
            "OpenAI API library is not available. You can install it with poetry "
            "install --with openai."
        )
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


class LLMAgent:
    """A class to interact with OpenAI's language model for generating unit tests."""

    def __init__(self):
        """Initializes the LLMAgent with configuration settings and cache."""
        self._model_name = config.configuration.large_language_model.model_name
        self._temperature = config.configuration.large_language_model.temperature
        self._llm_calls_counter = 0
        self._llm_calls_timer = 0
        self._llm_calls_with_no_python_code = 0
        self._llm_input_tokens = 0
        self._llm_output_tokens = 0
        self._llm_test_case_handler = LLMTestCaseHandler(self)

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

    @property
    def llm_input_tokens(self) -> int:
        """Returns the number of LLM input tokens.

        Returns:
            The number of LLM input tokens.
        """
        return self._llm_input_tokens

    @property
    def llm_output_tokens(self) -> int:
        """Returns the number of LLM input tokens.

        Returns:
            The number of LLM output tokens.
        """
        return self._llm_output_tokens

    @property
    def llm_test_case_handler(self):
        """Returns the number of LLM test case handler."""
        return self._llm_test_case_handler

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
            ChatCompletionSystemMessageParam(role="system", content=prompt.system_message),
            ChatCompletionUserMessageParam(role="user", content=prompt_text),
        ]

        try:
            response = openai.chat.completions.create(
                model=self._model_name,
                messages=messages,
                temperature=self._temperature,
            )
            if response.usage is not None:
                self._llm_input_tokens += response.usage.prompt_tokens
                self._llm_output_tokens += response.usage.completion_tokens
            response_text = response.choices[0].message.content

            if (
                config.configuration.large_language_model.enable_response_caching
                and response_text is not None
            ):
                self.cache.set(prompt_text, response_text)

            if response_text:
                save_prompt_info_to_file(prompt_text, response_text)
            return response_text

        except openai.OpenAIError as e:
            _logger.error(
                "An error occurred while querying the OpenAI API. Model: %s, Prompt: %s, Error: %s",
                self._model_name,
                prompt_text,
                e,
            )
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
            self._log_and_track_llm_stats()

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

    def call_llm_for_uncovered_targets(
        self, gao_coverage_map: dict[GenericCallableAccessibleObject, float]
    ):
        """Queries the language model for uncovered targets.

        Args:
            gao_coverage_map (dict): Maps callable objects to coverage percentages.

        Returns:
            Any: Result of the query based on the constructed prompt.
        """
        module_code = get_module_source_code()
        module_path = get_module_path()
        prompt = UncoveredTargetsPrompt(
            list(gao_coverage_map.keys()), module_code, str(module_path)
        )
        return self.query(prompt)

    def extract_python_code_from_llm_output(self, llm_output: str | None) -> str:
        """Extracts Python code blocks from the LLM output.

        Args:
            llm_output: The output from the LLM containing Python code.

        Returns:
            The extracted Python code.

        Raises:
            ValueError: If no Python code block is found in the LLM output.
        """
        python_markdown = r"```python([\s\S]+?)(?:```|$)"
        if llm_output:
            code_blocks = re.findall(python_markdown, llm_output)
            if not code_blocks:
                self._llm_calls_with_no_python_code += 1
                return llm_output
            return "\n".join(code_blocks)
        return ""

    def _log_and_track_llm_stats(self) -> None:
        """Logs LLM statistics and updates tracking variables.

        Updates the following runtime variables:
        - TotalLLMCalls: Total number of LLM calls made.
        - LLMQueryTime: Total time spent in LLM calls.
        - TotalCodelessLLMResponses: Number of LLM calls that returned no Python code.

        Logs the following:
        - Number of responses with Python code.
        - Total time spent in LLM calls.
        """
        number_of_llm_responses_with_python_code = (
            self.llm_calls_counter - self.llm_calls_with_no_python_code
        )

        _logger.info(
            "%d out of %d LLM responses have Python code.",
            number_of_llm_responses_with_python_code,
            self.llm_calls_counter,
        )
        _logger.info("Total LLM call time is %s seconds", self.llm_calls_timer / 1e9)

        stat.track_output_variable(RuntimeVariable.TotalLLMCalls, self.llm_calls_counter)
        stat.track_output_variable(RuntimeVariable.LLMQueryTime, self.llm_calls_timer)
        stat.track_output_variable(RuntimeVariable.TotalLLMOutputTokens, self.llm_output_tokens)
        stat.track_output_variable(RuntimeVariable.TotalLLMInputTokens, self.llm_input_tokens)
        stat.track_output_variable(
            RuntimeVariable.TotalCodelessLLMResponses,
            self.llm_calls_with_no_python_code,
        )

    def generate_assertions_for_test_case(self, test_case_source_code: str) -> str | None:
        """Generates assertions for a given test case source code.

        Args:
            test_case_source_code (str): The source code of the test case.

        Returns:
            str: The generated assertions as a string.
        """
        module_source_code = get_module_source_code()
        prompt = AssertionGenerationPrompt(
            test_case_source_code=test_case_source_code,
            module_source_code=module_source_code,
        )
        prompt_result = self.query(prompt)
        return self.extract_python_code_from_llm_output(prompt_result)
