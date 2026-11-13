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
from itertools import starmap
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
from pynguin.large_language_model.tracing import (
    CallOutcome,
    CallPurpose,
    CallUsage,
    LLMCallRecord,
    track_outcome,
    write_record,
)
from pynguin.refinement.api_signatures import describe_module_api
from pynguin.refinement.sut_inspector import SUTInspector
from pynguin.utils.naming import canonical_module_name
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


def get_importable_module_path(module_path: Path | None = None) -> str:
    """Returns the importable module path to display in prompts.

    Ensures the path does not include an absolute import-root directory (e.g. /input)
    so LLM prompts derive correct Python imports (e.g. 'from slugify.slugify import ...'
    rather than 'from input.slugify.slugify import ...').

    Args:
        module_path: Optional filesystem path of the module. If omitted, uses ``get_module_path()``.

    Returns:
        The relative or canonical importable module path (e.g. 'slugify/slugify.py').
    """
    if module_path is None:
        module_path = get_module_path()

    if config.configuration.project_path:
        project_root = Path(config.configuration.project_path).resolve()
        with contextlib.suppress(ValueError):
            rel = module_path.resolve().relative_to(project_root)
            if rel.name == "__init__.py":
                return f"{rel.parent}.py"
            return str(rel)

    canonical = canonical_module_name(config.configuration.module_name)
    return f"{canonical.replace('.', '/')}.py"


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


def _uncovered_targets_prompt(
    gao_coverage_map: dict[GenericCallableAccessibleObject, float],
    diagnostics: dict[GenericCallableAccessibleObject, str] | None,
) -> UncoveredTargetsPrompt:
    """Builds the prompt asking the LLM for tests that cover the given targets.

    Shared by the synchronous and asynchronous queries, so both send the same prompt.

    Args:
        gao_coverage_map: Maps callable objects to coverage percentages.
        diagnostics: Optional per-callable hints describing why a target is uncovered.

    Returns:
        The prompt for the uncovered targets.
    """
    return UncoveredTargetsPrompt(
        list(gao_coverage_map.keys()),
        get_module_source_code(),
        get_importable_module_path(),
        diagnostics=diagnostics,
        visibility_instructions=get_visibility_instructions(),
    )


def target_name(gao: GenericCallableAccessibleObject) -> str:
    """Names a targeted callable in the LLM call trace.

    Args:
        gao: The targeted callable.

    Returns:
        Its qualified name, or its string representation if it has none.
    """
    return getattr(gao.callable, "__qualname__", None) or str(gao)


def _target_names(gao_coverage_map: dict[GenericCallableAccessibleObject, float]) -> list[str]:
    return [target_name(gao) for gao in gao_coverage_map]


def _new_record(
    request: RenderedRequest,
    prompt: Prompt,
    *,
    purpose: str | None = None,
    targets: Sequence[str] = (),
    parent_call_id: str | None = None,
    repair_attempt: int = 0,
) -> LLMCallRecord:
    """Creates the trace record for a call that is about to be made.

    Args:
        request: The request that will be sent.
        prompt: The prompt the request was rendered from.
        purpose: Why the call is made; defaults to the prompt's resource name.
        targets: The names of the callables the call targets.
        parent_call_id: The call whose response a repair call asks to fix.
        repair_attempt: The repair attempt index (0 for an original call).

    Returns:
        The new record.
    """
    if purpose is None:
        resource_name = getattr(type(prompt), "_resource_name", None)
        purpose = resource_name if isinstance(resource_name, str) else CallPurpose.OTHER.value
    return LLMCallRecord(
        purpose=purpose,
        prompt=[dict(message) for message in request.messages],
        targets=list(targets),
        parent_call_id=parent_call_id,
        repair_attempt=repair_attempt,
    )


def _note_error(usage: CallUsage, error: BaseException) -> None:
    """Remembers an error the client raised instead of returning a response.

    Args:
        usage: The usage of the failed call.
        error: The raised error.
    """
    usage.error = repr(error)
    usage.timed_out = usage.timed_out or isinstance(error, TimeoutError)


def _finish_record(
    record: LLMCallRecord,
    response: str | None,
    usage: CallUsage | None,
    started: float,
) -> None:
    """Completes a record once its call has returned and counts its outcome.

    Args:
        record: The record to complete.
        response: The response, or None if the call failed.
        usage: The per-call usage the client filled in, or None for a cache hit.
        started: The ``time.perf_counter()`` value when the call started.
    """
    record.response = response
    record.latency_seconds = time.perf_counter() - started
    if usage is None:
        record.outcome = CallOutcome.CACHE_HIT
    else:
        record.input_tokens = usage.input_tokens
        record.output_tokens = usage.output_tokens
        record.retries = usage.retries
        if response is not None:
            record.outcome = CallOutcome.OK
        else:
            record.outcome = CallOutcome.TIMEOUT if usage.timed_out else CallOutcome.FAILED
            record.error = usage.error or "no response"
    track_outcome(record.outcome)


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
        self._llm_logical_queries = 0
        self._llm_endpoint_requests = 0
        self._llm_cache_hits = 0
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
    def llm_logical_queries(self) -> int:
        """Returns the number of logical LLM queries issued (cache hits included).

        Returns:
            The number of logical LLM queries issued.
        """
        return self._llm_logical_queries

    @property
    def llm_endpoint_requests(self) -> int:
        """Returns the number of actual LLM endpoint requests made.

        Larger than llm_logical_queries when retries occurred.

        Returns:
            The number of actual LLM endpoint requests made.
        """
        return self._llm_endpoint_requests

    @property
    def llm_cache_hits(self) -> int:
        """Returns the number of logical LLM queries served from the response cache.

        Returns:
            The number of logical LLM queries served from the response cache.
        """
        return self._llm_cache_hits

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

    def _sync_usage(self) -> None:
        """Copies the client's cumulative usage into the agent's counters."""
        usage = self._client.get_usage()
        self._llm_input_tokens = usage["input_tokens"]
        self._llm_output_tokens = usage["output_tokens"]
        self._llm_calls_with_no_python_code = usage["calls_with_no_python_code"]
        self._llm_endpoint_requests = usage["endpoint_requests"]

    def query(
        self,
        prompt: Prompt,
        *,
        purpose: str | None = None,
        targets: Sequence[str] = (),
    ) -> str | None:
        """Sends a query to the OpenAI API and returns the response.

        The call is written to the LLM call trace (if enabled).

        Args:
            prompt: The prompt object to build the query.
            purpose: Why the call is made, for the trace; defaults to the prompt's name.
            targets: The names of the callables the call targets, for the trace.

        Returns:
            The response from the OpenAI API, or None if the response is empty.
        """
        response, record = self.query_traced(prompt, purpose=purpose, targets=targets)
        write_record(record)
        return response

    def query_traced(
        self,
        prompt: Prompt,
        *,
        purpose: str | None = None,
        targets: Sequence[str] = (),
        parent_call_id: str | None = None,
        repair_attempt: int = 0,
    ) -> tuple[str | None, LLMCallRecord]:
        """Sends a query and returns the response with the record describing the call.

        The record is not written to the trace, so the caller can add the
        deserialisation result first and then pass it to ``tracing.write_record``.

        Args:
            prompt: The prompt object to build the query.
            purpose: Why the call is made, for the trace; defaults to the prompt's name.
            targets: The names of the callables the call targets, for the trace.
            parent_call_id: The call whose response a repair call asks to fix.
            repair_attempt: The repair attempt index (0 for an original call).

        Returns:
            The response (None if the call failed) and the record of the call.
        """
        request = prompt.render_request()
        record = _new_record(
            request,
            prompt,
            purpose=purpose,
            targets=targets,
            parent_call_id=parent_call_id,
            repair_attempt=repair_attempt,
        )
        prompt_text = request.messages[-1]["content"]
        self._llm_logical_queries += 1

        if config.configuration.large_language_model.enable_response_caching:
            cached_response = self.cache.get(request)
            if cached_response is not None:
                self._llm_cache_hits += 1
                self._log_and_track_llm_stats()
                _finish_record(record, cached_response, None, time.perf_counter())
                return cached_response, record

        start_time = time.time_ns()
        started = time.perf_counter()
        self._llm_calls_counter += 1
        usage = CallUsage()
        response_text: str | None = None

        try:
            response_text = self._client.send(request, usage=usage)

            if response_text:
                save_prompt_info_to_file(prompt_text, response_text)
        except Exception as e:  # noqa: BLE001
            _note_error(usage, e)
            _logger.error(
                "An error occurred while querying the OpenAI API. Model: %s, Prompt: %s, Error: %s",
                self._model_name,
                prompt_text,
                e,
            )
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
            self._sync_usage()
            self._log_and_track_llm_stats()
        _finish_record(record, response_text, usage, started)
        return response_text, record

    async def query_async(
        self,
        prompt: Prompt,
        *,
        purpose: str | None = None,
        targets: Sequence[str] = (),
    ) -> str | None:
        """Sends an asynchronous query to the OpenAI API and returns the response.

        The call is written to the LLM call trace (if enabled).

        Args:
            prompt: The prompt object to build the query.
            purpose: Why the call is made, for the trace; defaults to the prompt's name.
            targets: The names of the callables the call targets, for the trace.

        Returns:
            The response from the OpenAI API, or None if the response is empty.
        """
        request = prompt.render_request()
        record = _new_record(request, prompt, purpose=purpose, targets=targets)
        prompt_text = request.messages[-1]["content"]
        self._llm_logical_queries += 1

        if config.configuration.large_language_model.enable_response_caching:
            cached_response = self.cache.get(request)
            if cached_response is not None:
                self._llm_cache_hits += 1
                self._log_and_track_llm_stats()
                _finish_record(record, cached_response, None, time.perf_counter())
                write_record(record)
                return cached_response

        start_time = time.time_ns()
        started = time.perf_counter()
        self._llm_calls_counter += 1
        usage = CallUsage()
        response_text: str | None = None

        try:
            response_text = await self._client.send_async(request, usage=usage)

            if response_text:
                save_prompt_info_to_file(prompt_text, response_text)
        except Exception as e:  # noqa: BLE001
            _note_error(usage, e)
            _logger.error(
                "An error occurred while querying the OpenAI API. Model: %s, Prompt: %s, Error: %s",
                self._model_name,
                prompt_text,
                e,
            )
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
            self._sync_usage()
            self._log_and_track_llm_stats()
        _finish_record(record, response_text, usage, started)
        write_record(record)
        return response_text

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
        records = list(starmap(_new_record, zip(requests, prompts, strict=True)))
        responses, uncached_indices = self._lookup_cached(requests, records)
        uncached_requests = [requests[i] for i in uncached_indices]
        self._llm_logical_queries += len(requests)
        self._llm_cache_hits += len(requests) - len(uncached_requests)

        if not uncached_requests:
            self._log_and_track_llm_stats()
            return responses

        start_time = time.time_ns()
        started = time.perf_counter()
        self._llm_calls_counter += len(uncached_requests)
        usages = [CallUsage() for _ in uncached_requests]

        try:
            results = await self._client.send_batch_async(
                uncached_requests, max_concurrency=max_concurrency, usages=usages
            )
            for idx, res, req in zip(uncached_indices, results, uncached_requests, strict=False):
                responses[idx] = res
                if res:
                    save_prompt_info_to_file(req.messages[-1]["content"], res)
            failed = sum(1 for res in results if res is None)
            if failed:
                _logger.warning(
                    "%d out of %d batched LLM requests returned no response.",
                    failed,
                    len(uncached_requests),
                )
        except Exception as e:  # noqa: BLE001
            for usage in usages:
                _note_error(usage, e)
            _logger.error(
                "An error occurred during batch querying the OpenAI API. Error: %s",
                e,
            )
        finally:
            self._llm_calls_timer += time.time_ns() - start_time
            self._sync_usage()
            self._log_and_track_llm_stats()

        for idx, usage in zip(uncached_indices, usages, strict=True):
            _finish_record(records[idx], responses[idx], usage, started)
            write_record(records[idx])
        return responses

    def _lookup_cached(
        self, requests: list[RenderedRequest], records: list[LLMCallRecord]
    ) -> tuple[list[str | None], list[int]]:
        """Looks the requests of a batch up in the response cache.

        The records of the cache hits are completed and written to the trace.

        Args:
            requests: The requests of the batch.
            records: The trace records, parallel to ``requests``.

        Returns:
            The cached responses (None where there is none) and the indices of the
            requests that still have to be sent.
        """
        responses: list[str | None] = [None] * len(requests)
        if not getattr(config.configuration.large_language_model, "enable_response_caching", False):
            return responses, list(range(len(requests)))
        uncached_indices: list[int] = []
        cached_at = time.perf_counter()
        for i, req in enumerate(requests):
            cached = self.cache.get(req)
            if cached is None:
                uncached_indices.append(i)
                continue
            responses[i] = cached
            _finish_record(records[i], cached, None, cached_at)
            write_record(records[i])
        return responses, uncached_indices

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
        return self.query(self.build_test_generation_prompt(), purpose=CallPurpose.INITIAL.value)

    @staticmethod
    def build_test_generation_prompt() -> TestCaseGenerationPrompt:
        """Builds the prompt asking for tests for the whole module under test.

        Returns:
            The prompt.
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

        return TestCaseGenerationPrompt(
            module_code,
            get_importable_module_path(module_path),
            dependencies=dependencies,
            usage_examples=usage_examples,
            visibility_instructions=get_visibility_instructions(),
            api_signatures=describe_module_api(import_module(config.configuration.module_name)),
        )

    @staticmethod
    def build_uncovered_targets_prompt(
        gao_coverage_map: dict[GenericCallableAccessibleObject, float],
        diagnostics: dict[GenericCallableAccessibleObject, str] | None = None,
    ) -> UncoveredTargetsPrompt:
        """Builds the prompt asking for tests that cover the given targets.

        Args:
            gao_coverage_map: Maps callable objects to coverage percentages.
            diagnostics: Optional per-callable hints describing why a target is uncovered.

        Returns:
            The prompt.
        """
        return _uncovered_targets_prompt(gao_coverage_map, diagnostics)

    async def call_llm_for_uncovered_targets_async(
        self,
        gao_coverage_map: dict[GenericCallableAccessibleObject, float],
        diagnostics: dict[GenericCallableAccessibleObject, str] | None = None,
    ):
        """Asynchronously queries the language model for uncovered targets.

        Args:
            gao_coverage_map (dict): Maps callable objects to coverage percentages.
            diagnostics (dict): Optional per-callable diagnostic hints describing why
                a target is uncovered (e.g. never reached, one-sided branch).

        Returns:
            Any: Result of the query based on the constructed prompt.
        """
        return await self.query_async(
            self.build_uncovered_targets_prompt(gao_coverage_map, diagnostics),
            purpose=CallPurpose.UNCOVERED_TARGETS.value,
            targets=_target_names(gao_coverage_map),
        )

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
        - TotalLLMLogicalQueries: Logical queries issued, including cache hits.
        - TotalLLMEndpointRequests: Actual endpoint requests made (retries included).
        - TotalLLMCacheHits: Logical queries served from the response cache.

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
            RuntimeVariable.TotalLLMLogicalQueries: self.llm_logical_queries,
            RuntimeVariable.TotalLLMEndpointRequests: self.llm_endpoint_requests,
            RuntimeVariable.TotalLLMCacheHits: self.llm_cache_hits,
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
