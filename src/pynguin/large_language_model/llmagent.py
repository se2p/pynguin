# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module generates unit tests for a given module using OpenAI's language model."""

from __future__ import annotations

import contextlib
import datetime
import inspect
import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

with contextlib.suppress(ImportError):
    import openai  # noqa: F401

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.analyses.module import import_module
from pynguin.large_language_model.client import (
    OpenAIClient,
    _run_coroutine_sync,
    extract_python_code,
)
from pynguin.large_language_model.llmtestcasehandler import LLMTestCaseHandler
from pynguin.large_language_model.prompts.assertiongenerationprompt import (
    AssertionGenerationPrompt,
)
from pynguin.large_language_model.prompts.localsearchprompt import LocalSearchPrompt
from pynguin.large_language_model.prompts.testcasegenerationprompt import (
    TestCaseGenerationPrompt,
)
from pynguin.large_language_model.prompts.uncoveredtargetsprompt import (
    UncoveredTargetsPrompt,
)
from pynguin.refinement.sut_inspector import SUTInspector
from pynguin.utils.openai_key_resolver import get_model_name, require_api_key  # noqa: F401
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from pynguin.large_language_model.prompts.prompt import Prompt
    from pynguin.large_language_model.request import RenderedRequest
    from pynguin.utils.generic.genericaccessibleobject import (
        GenericCallableAccessibleObject,
    )
    from pynguin.utils.report import LineAnnotation

_logger = logging.getLogger(__name__)

# Several LLMAgent instances exist in one run (search, seeding, assertion generation, ...)
# and may report concurrently, so their contributions to the shared totals are serialised.
_STATS_LOCK = threading.Lock()


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
    with contextlib.suppress(Exception):
        module = import_module(config.configuration.module_name)
        source_file = inspect.getsourcefile(module) or getattr(module, "__file__", None)
        if source_file and Path(source_file).exists():
            return Path(source_file)

    return Path(config.configuration.project_path) / (config.configuration.module_name + ".py")


def _truncate_to_context_budget(source: str) -> str:
    """Truncate module source to the configured LLM context-character budget.

    Coverage gains saturate beyond a moderate context size while token consumption
    keeps growing, so oversized sources are truncated to
    ``large_language_model.max_context_chars`` (a value of <= 0 disables truncation).

    Args:
        source: The full module source code.

    Returns:
        The source, truncated with a marker comment if it exceeds the budget.
    """
    max_chars = config.configuration.large_language_model.max_context_chars
    if max_chars > 0 and len(source) > max_chars:
        _logger.warning(
            "Module source (%d chars) exceeds max_context_chars (%d); truncating.",
            len(source),
            max_chars,
        )
        return source[:max_chars] + "\n# ... [truncated: source exceeds max_context_chars] ...\n"
    return source


def get_visibility_instructions() -> str:
    """Describes, in prose, which members of the module under test the LLM may call.

    The LLM is always prompted with the module's full, unfiltered source (see
    ``get_module_source_code``) -- it needs the whole picture to write correct
    tests. But the search-based side of Pynguin only ever targets elements
    ``element_visibility`` (default ``PUBLIC``) allows, so a call the LLM
    invents to an excluded element can never be resolved against the test
    cluster and is wasted budget. This instruction, included in the relevant
    prompts, tells the LLM which elements are actually in scope so it targets
    them instead; :func:`pynguin.large_language_model.parsing.deserializer.
    CstStatementDeserializer._compute_ambient_names` still drops any call to
    an excluded element the LLM generates regardless.

    Returns:
        A prose instruction for the prompt, or an empty string when every
        element is in scope (``element_visibility`` is ``ALL``) and no
        instruction is needed.
    """
    match config.configuration.element_visibility:
        case config.ElementVisibility.PUBLIC:
            return (
                "Only call public functions, classes and methods of the module under "
                "test (names that do not start with an underscore); do not call "
                "protected (`_name`) or private (`__name`) members."
            )
        case config.ElementVisibility.PROTECTED:
            return (
                "Only call public and protected functions, classes and methods of the "
                "module under test (names with at most one leading underscore); do "
                "not call private (`__name`) members."
            )
        case _:
            return ""


def get_module_source_code() -> str:
    """Reads and returns the source code of the module.

    The source is truncated to the configured LLM context-character budget
    (``large_language_model.max_context_chars``).

    Returns:
        The source code of the module.

    Raises:
        FileNotFoundError: If the module file is not found.
    """
    module = import_module(config.configuration.module_name)

    # Prefer reading directly from the source file on disk. Inspecting via
    # `inspect.getsource()` triggers `inspect.unwrap()`, which checks
    # `hasattr(module, '__wrapped__')`. If the module defines module-level
    # `__getattr__` (PEP 562), that attribute lookup executes instrumented code
    # while the tracer is inactive, causing TracingAbortedException.
    with contextlib.suppress(Exception):
        source_file = inspect.getsourcefile(module) or getattr(module, "__file__", None)
        if source_file and Path(source_file).exists():
            return _truncate_to_context_budget(Path(source_file).read_text(encoding="utf-8"))

    return _truncate_to_context_budget(inspect.getsource(module))


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
        try:
            obj = cast("ModuleType", getattr(obj, part, None))
        except Exception:  # noqa: BLE001
            _logger.debug("Error accessing %s in %s", part, ".".join(parts), exc_info=True)
            return None
        if obj is None:
            _logger.debug("%s not found in %s", part, ".".join(parts))
            return None

    try:
        return inspect.getsourcelines(obj)
    except (OSError, TypeError, AttributeError, Exception) as e:
        _logger.debug("Could not get source for %s: %s", name, e)
        return None


class LLMAgent:  # noqa: PLR0904
    """A class to interact with OpenAI's language model for generating unit tests."""

    def __init__(self):
        """Initializes the LLMAgent with configuration settings and cache."""
        self._model_name = get_model_name()
        self._llm_calls_counter = 0
        self._llm_calls_timer = 0
        self._llm_calls_with_no_python_code = 0
        self._llm_input_tokens = 0
        self._llm_output_tokens = 0
        # The values this agent has already added to the run-wide statistics.
        self._reported_stats: dict[RuntimeVariable, float] = {}
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

    @property
    def client(self) -> OpenAIClient:
        """Returns the underlying LLM client.

        Returns:
            The OpenAIClient instance.
        """
        return self._client

    def cancel_all(self) -> None:
        """Cancel all in-flight requests and close client connections."""
        if hasattr(self, "_client") and hasattr(self._client, "cancel_all"):
            self._client.cancel_all()

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

    async def query_async(self, prompt: Prompt) -> str | None:
        """Sends an asynchronous query to the OpenAI API and returns the response.

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
            response_text = await self._client.send_async(request)

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

    async def query_batch_async(
        self, prompts: Sequence[Prompt], max_concurrency: int | None = None
    ) -> list[str | None]:
        """Sends a batch of queries concurrently to the OpenAI API.

        Args:
            prompts: The prompt objects to build the queries.
            max_concurrency: Maximum concurrent requests. If None, uses configured value.

        Returns:
            List of responses corresponding to the given prompts.
        """
        if not prompts:
            return []

        requests = [p.render_request() for p in prompts]
        cache_enabled = getattr(
            config.configuration.large_language_model, "enable_response_caching", False
        )
        responses: list[str | None] = [None] * len(prompts)
        uncached_indices: list[int] = []
        uncached_requests: list[RenderedRequest] = []

        for i, req in enumerate(requests):
            if cache_enabled:
                cached = self.cache.get(req)
                if cached is not None:
                    responses[i] = cached
                    continue
            uncached_indices.append(i)
            uncached_requests.append(req)

        if not uncached_requests:
            return responses

        start_time = time.time_ns()
        self._llm_calls_counter += len(uncached_requests)

        try:
            results = await self._client.send_batch_async(
                uncached_requests, max_concurrency=max_concurrency
            )
            usage = self._client.get_usage()
            self._llm_input_tokens = usage["input_tokens"]
            self._llm_output_tokens = usage["output_tokens"]
            self._llm_calls_with_no_python_code = usage["calls_with_no_python_code"]

            for idx, res, req in zip(uncached_indices, results, uncached_requests, strict=False):
                responses[idx] = res
                if res:
                    save_prompt_info_to_file(req.messages[-1]["content"], res)
        except Exception as e:  # noqa: BLE001
            _logger.error(
                "An error occurred during batch querying the OpenAI API. Error: %s",
                e,
            )
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
            self._log_and_track_llm_stats()

        return responses

    def query_batch(
        self, prompts: Sequence[Prompt], max_concurrency: int | None = None
    ) -> list[str | None]:
        """Synchronously executes a batch of queries concurrently.

        Args:
            prompts: The prompt objects to build the queries.
            max_concurrency: Maximum concurrent requests. If None, uses configured value.

        Returns:
            List of responses corresponding to the given prompts.
        """
        return _run_coroutine_sync(self.query_batch_async(prompts, max_concurrency=max_concurrency))

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

        dependencies = ""
        usage_examples = ""
        ref_config = config.configuration.llm_refinement
        if ref_config.enable_dependency_context or ref_config.enable_usage_examples:
            inspector = SUTInspector(project_root=config.configuration.project_path)
            if ref_config.enable_dependency_context:
                dependencies = inspector.inspect_dependencies(
                    config.configuration.module_name,
                    max_deps=ref_config.max_dependencies,
                )
            if ref_config.enable_usage_examples:
                usage_examples = inspector.inspect_usage_examples(
                    config.configuration.module_name,
                    max_examples=ref_config.max_usage_examples,
                )

        prompt = TestCaseGenerationPrompt(
            module_code,
            str(module_path),
            dependencies=dependencies,
            usage_examples=usage_examples,
            visibility_instructions=get_visibility_instructions(),
        )
        return self.query(prompt)

    def call_llm_for_uncovered_targets(
        self,
        gao_coverage_map: dict[GenericCallableAccessibleObject, float],
        diagnostics: dict[GenericCallableAccessibleObject, str] | None = None,
    ):
        """Queries the language model for uncovered targets.

        Args:
            gao_coverage_map (dict): Maps callable objects to coverage percentages.
            diagnostics (dict): Optional per-callable diagnostic hints describing why
                a target is uncovered (e.g. never reached, one-sided branch).

        Returns:
            Any: Result of the query based on the constructed prompt.
        """
        module_code = get_module_source_code()
        module_path = get_module_path()
        prompt = UncoveredTargetsPrompt(
            list(gao_coverage_map.keys()),
            module_code,
            str(module_path),
            diagnostics=diagnostics,
            visibility_instructions=get_visibility_instructions(),
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

        Adds this agent's usage since its last report to the following runtime
        variables, so they are totals across all agents of the run:
        - TotalLLMCalls: Total number of LLM calls made.
        - LLMQueryTime: Total time spent in LLM calls.
        - TotalLLMInputTokens / TotalLLMOutputTokens: Total tokens used.
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

        current = {
            RuntimeVariable.TotalLLMCalls: self.llm_calls_counter,
            RuntimeVariable.LLMQueryTime: self.llm_calls_timer,
            RuntimeVariable.TotalLLMOutputTokens: self.llm_output_tokens,
            RuntimeVariable.TotalLLMInputTokens: self.llm_input_tokens,
            RuntimeVariable.TotalCodelessLLMResponses: self.llm_calls_with_no_python_code,
        }
        with _STATS_LOCK:
            for variable, value in current.items():
                reported = self._reported_stats.get(variable, 0)
                # A counter below what was reported means the client usage was reset,
                # in which case everything counted since then is new.
                delta = value - reported if value >= reported else value
                stat.add_to_runtime_variable(variable, delta)
                self._reported_stats[variable] = value

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

    def generate_assertions_for_test_cases(
        self, test_cases_source_code: list[str]
    ) -> list[str | None]:
        """Generates assertions concurrently for a list of test case source codes.

        Args:
            test_cases_source_code: The source codes of the test cases.

        Returns:
            List of generated assertions code strings.
        """
        if not test_cases_source_code:
            return []
        module_source_code = get_module_source_code()
        prompts = [
            AssertionGenerationPrompt(
                test_case_source_code=code,
                module_source_code=module_source_code,
            )
            for code in test_cases_source_code
        ]
        results = self.query_batch(prompts)
        return [self.extract_python_code_from_llm_output(res) for res in results]

    async def generate_assertions_for_test_cases_async(
        self, test_cases_source_code: list[str]
    ) -> list[str | None]:
        """Asynchronously generates assertions concurrently for test cases.

        Args:
            test_cases_source_code: The source codes of the test cases.

        Returns:
            List of generated assertions code strings.
        """
        if not test_cases_source_code:
            return []
        module_source_code = get_module_source_code()
        prompts = [
            AssertionGenerationPrompt(
                test_case_source_code=code,
                module_source_code=module_source_code,
            )
            for code in test_cases_source_code
        ]
        results = await self.query_batch_async(prompts)
        return [self.extract_python_code_from_llm_output(res) for res in results]

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
            visibility_instructions=get_visibility_instructions(),
        )
        return self.query(prompt)
