# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module generates unit tests for a given module using OpenAI's language model."""

import contextlib
import datetime
import inspect
import logging
import pathlib
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

with contextlib.suppress(ImportError):
    import openai  # noqa: F401

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.analyses.module import import_module
from pynguin.large_language_model.client import OpenAIClient, extract_python_code
from pynguin.large_language_model.llmtestcasehandler import LLMTestCaseHandler
from pynguin.large_language_model.prompts.assertiongenerationprompt import (
    AssertionGenerationPrompt,
)
from pynguin.large_language_model.prompts.localsearchprompt import LocalSearchPrompt
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
from pynguin.utils.openai_key_resolver import get_model_name, require_api_key  # noqa: F401
from pynguin.utils.report import LineAnnotation
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from types import ModuleType

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


def get_part_of_source_code(name: str) -> str:
    """Gets the source code of a specific part of the module.

    The extraction can be for a function, method or a constructor.
    Additionally, line numbers are added.

    Args:
        name (str): The name of the part to extract.

    Returns:
        The source code of the specified part with line numbers.
    """
    result = _find_lines(name)
    if result is None:
        return ""
    source_lines, start_line = result

    return "\n".join(f"{start_line + i:4d}: {line.rstrip()}" for i, line in enumerate(source_lines))


def shorten_line_annotations(
    line_annotations: list[LineAnnotation], name: str
) -> list[LineAnnotation]:
    """Shortens the line annotations to only include those relevant to the specified part.

    Args:
        line_annotations (list): The list of line annotations to shorten.
        name (str): The name of the part to filter by.

    Returns:
        The shortened list of line annotations.
    """
    result = _find_lines(name)
    if result is None:
        return []
    source_lines, start_line = result
    end_line = start_line + len(source_lines)
    return [
        line_annotation
        for line_annotation in line_annotations
        if start_line <= line_annotation.line_no < end_line and line_annotation.branches.covered > 0
    ]


def _find_lines(name: str) -> tuple[list[str], int] | None:
    """Find the source lines for a given object name.

    Args:
        name: The name of the object to find (can be nested like "Class.method").

    Returns:
        A tuple of (source_lines, start_line) if found, None otherwise.
    """
    module = import_module(config.configuration.module_name)
    parts = name.split(".")
    obj = module
    for part in parts:
        obj = cast("ModuleType", getattr(obj, part, None))
        if obj is None:
            _logger.debug("%s not found in %s", part, ".".join(parts))
            return None

    try:
        return inspect.getsourcelines(obj)
    except (OSError, TypeError, AttributeError) as e:
        _logger.debug("Could not get source for %s: %s", name, e)
        return None


class LLMAgent:
    """A class to interact with OpenAI's language model for generating unit tests."""

    def __init__(self):
        """Initializes the LLMAgent with configuration settings and cache."""
        self._model_name = get_model_name()
        self._llm_calls_counter = 0
        self._llm_calls_timer = 0
        self._llm_calls_with_no_python_code = 0
        self._llm_input_tokens = 0
        self._llm_output_tokens = 0
        self._llm_test_case_handler = LLMTestCaseHandler(self)

        self._client = OpenAIClient()
        self.cache = self._client.cache

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
        request = prompt.render_request()
        prompt_text = request.messages[-1]["content"]

        if config.configuration.large_language_model.enable_response_caching:
            cached_response = self.cache.get(request)
            if cached_response is not None:
                return cached_response

        start_time = time.time_ns()
        self._llm_calls_counter += 1

        try:
            response_text = self._client.send(request)

            # Sync usage details
            usage = self._client.get_usage()
            self._llm_input_tokens = usage["input_tokens"]
            self._llm_output_tokens = usage["output_tokens"]
            self._llm_calls_with_no_python_code = usage["calls_with_no_python_code"]

            if response_text:
                save_prompt_info_to_file(prompt_text, response_text)
            return response_text

        except Exception as e:  # noqa: BLE001
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
        """
        return extract_python_code(llm_output)

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

    def local_search_call(
        self,
        position,
        test_case_source_code: str,
        branch_coverage: list[LineAnnotation],
        module_source_code: str,
    ) -> str | None:
        """Changes the statement at the given position to increase branch coverage.

        Args:
            position (int): The position of the statement in the testcase.
            test_case_source_code (str): The source code of the test case.
            branch_coverage: The branch coverage of the test case of each branch.
            module_source_code (str): The source code of the module under test.

        Returns:
            Gives back the new line containing the changed statement as string.
        """
        prompt = LocalSearchPrompt(
            test_case_code=test_case_source_code,
            position=position,
            module_code=module_source_code,
            branch_coverage=branch_coverage,
        )
        return self.query(prompt)
