# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#

"""Provides the LLM client abstraction and implementations."""

from __future__ import annotations

import abc
import ast
import asyncio
import concurrent.futures
import logging
import random
import re
import threading
import time
from typing import TYPE_CHECKING, Any, TypeVar

import pynguin.configuration as config
from pynguin.large_language_model.cache import LLMCache
from pynguin.utils.openai_key_resolver import get_llm_url, get_model_name, require_api_key

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from pydantic import SecretStr

    from pynguin.large_language_model.request import RenderedRequest

_T = TypeVar("_T")

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


_logger = logging.getLogger(__name__)

# Some models/endpoints reject an explicit temperature of 0. When that happens we
# retry once with this small positive temperature instead of failing the request.
_TEMPERATURE_FALLBACK = 0.1


def _is_temperature_unsupported_error(exc: Exception) -> bool:
    """Heuristically detect an API error caused by an unsupported temperature value.

    Providers phrase this differently (and some run behind OpenAI-compatible proxies),
    so we match on the error message mentioning ``temperature`` rather than a specific
    exception type.

    Args:
        exc: The exception raised by the API call.

    Returns:
        True if the error appears to be about the ``temperature`` parameter.
    """
    return "temperature" in str(exc).lower()


def _retry_fits_in_budget(
    *,
    budget: float,
    elapsed: float,
    wait: float,
    timeout: float | None,
) -> bool:
    """Whether another retry attempt still fits within the request's time budget.

    Args:
        budget: Total wall-clock budget for the logical request; <= 0 disables it.
        elapsed: Seconds already spent on this logical request.
        wait: The backoff wait that would precede the next attempt.
        timeout: The per-attempt timeout, or *None* when attempts are unbounded.

    Returns:
        True if the backoff plus another full attempt would stay within the budget.
    """
    if budget <= 0:
        return True
    if timeout is None:
        # An unbounded attempt can never be guaranteed to fit; allow it only while
        # the budget has not been spent yet.
        return elapsed + wait < budget
    return elapsed + wait + timeout <= budget


def extract_python_code(text: str | None) -> str:
    """Extracts Python code blocks from LLM markdown output.

    If no markdown python blocks are found, falls back to stripping the raw text.

    Args:
        text: The LLM output.

    Returns:
        The extracted Python code.
    """
    if not text:
        return ""
    pattern = r"^```(?:python)?\s*\n([\s\S]*?)^```"
    code_blocks = re.findall(pattern, text, re.MULTILINE)
    if not code_blocks:
        # Fallback: consume an optional language identifier after the opening fence
        # (e.g. ```py) so that language tokens are not leaked into the extracted code.
        pattern_fallback = r"```[ \t]*[A-Za-z0-9_+-]*[ \t]*\n?([\s\S]*?)(?:```|$)"
        code_blocks = re.findall(pattern_fallback, text)
    if not code_blocks:
        # No fenced block at all: only return the raw text if it is valid Python,
        # otherwise return "" so prose is never written into a .py file.
        stripped = text.strip()
        try:
            ast.parse(stripped)
        except (SyntaxError, ValueError):
            return ""
        return stripped

    cleaned_blocks = [block.strip() for block in code_blocks if block.strip()]
    if not cleaned_blocks:
        return text.strip()
    return "\n\n".join(cleaned_blocks) + "\n"


def _run_coroutine_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run a coroutine synchronously, handling both existing and new event loops.

    Args:
        coro: The coroutine to execute.

    Returns:
        The result of the coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if not loop.is_running():
        return loop.run_until_complete(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class LLMClient(abc.ABC):
    """Abstract base class for LLM clients."""

    @abc.abstractmethod
    def send(self, request: RenderedRequest) -> str | None:
        """Sends a rendered request to the LLM.

        Args:
            request: The request payload.

        Returns:
            The LLM response content or None on failure.
        """

    async def send_async(
        self, request: RenderedRequest, timeout: float | None = None
    ) -> str | None:
        """Sends a rendered request asynchronously to the LLM.

        Args:
            request: The request payload.
            timeout: Per-attempt timeout in seconds overriding the configured
                ``request_timeout``; *None* uses the configured value.

        Returns:
            The LLM response content or None on failure.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.send, request)

    async def send_batch_async(
        self,
        requests: list[RenderedRequest],
        timeout: float | None = None,
        max_concurrency: int | None = None,
    ) -> list[str | None]:
        """Sends a batch of requests concurrently with bounded concurrency.

        Args:
            requests: The list of RenderedRequests to send.
            timeout: Per-attempt timeout in seconds overriding the configured
                ``request_timeout``; *None* uses the configured value.
            max_concurrency: Maximum number of concurrent requests. Defaults to
                the configured ``max_concurrency``.

        Returns:
            List of LLM response strings in the same order as the requests.
        """
        if not requests:
            return []
        if max_concurrency is None:
            max_concurrency = getattr(
                config.configuration.large_language_model, "max_concurrency", 5
            )
        if max_concurrency <= 0:
            max_concurrency = 1

        semaphore = asyncio.Semaphore(max_concurrency)

        async def _send_one(req: RenderedRequest) -> str | None:
            async with semaphore:
                return await self.send_async(req, timeout=timeout)

        return list(await asyncio.gather(*[_send_one(req) for req in requests]))

    def send_batch(
        self,
        requests: list[RenderedRequest],
        timeout: float | None = None,
        max_concurrency: int | None = None,
    ) -> list[str | None]:
        """Sends a batch of requests concurrently from synchronous code.

        Args:
            requests: The list of RenderedRequests to send.
            timeout: Per-attempt timeout in seconds overriding the configured
                ``request_timeout``; *None* uses the configured value.
            max_concurrency: Maximum number of concurrent requests. Defaults to
                the configured ``max_concurrency``.

        Returns:
            List of LLM response strings in the same order as the requests.
        """
        return _run_coroutine_sync(
            self.send_batch_async(requests, timeout=timeout, max_concurrency=max_concurrency)
        )

    @abc.abstractmethod
    def get_usage(self) -> dict[str, Any]:
        """Returns cumulative usage statistics of the client.

        Returns:
            A dictionary containing calls, input_tokens, output_tokens, time_seconds,
            and calls_with_no_python_code.
        """

    @abc.abstractmethod
    def reset_usage(self) -> None:
        """Resets all usage counters to zero."""


class OpenAIClient(LLMClient):
    """A thread-safe instance-based OpenAI client."""

    def __init__(self, api_key: SecretStr | None = None, model: str | None = None) -> None:
        """Initializes the OpenAI Client.

        Args:
            api_key: The resolved API key.
            model: The target model name.

        Raises:
            ValueError: If OpenAI is not available.
        """
        if not OPENAI_AVAILABLE:
            raise ValueError(
                "OpenAI API library is not available. Install it with poetry install --with openai."
            )

        self._api_key = api_key or require_api_key()
        self._model = model or get_model_name()

        # Metrics/usage tracking
        self._lock = threading.RLock()
        self._calls = 0
        self._retries = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._time_seconds = 0.0
        self._calls_with_no_python_code = 0

        # Once a model rejects an explicit temperature of 0, remember it so all future
        # requests from this client skip the doomed attempt and use the fallback directly.
        self._temperature_zero_rejected = False

        # Dynamic exception lists for retrying
        self._rate_limit_errors: tuple[type[Exception], ...] = (openai.RateLimitError,)
        self._timeout_errors: tuple[type[Exception], ...] = (openai.APITimeoutError,)
        self._api_errors: tuple[type[Exception], ...] = (openai.OpenAIError,)

        # Create cache instance
        self._cache = LLMCache()

        # Create client instance
        llm_url = get_llm_url()
        kwargs: dict[str, Any] = {"api_key": self._api_key.get_secret_value()}
        if llm_url:
            kwargs["base_url"] = llm_url
        # The SDK retries internally by default (2 retries = 3 attempts), which would
        # multiply with the retry loop in ``send`` and make a single logical request
        # cost ``max_retries * 3 * request_timeout``.  Retrying is this class's job.
        kwargs["max_retries"] = 0
        self._client_kwargs = kwargs
        self._client = openai.OpenAI(**kwargs)
        self._async_client: openai.AsyncOpenAI | None = None

    @property
    def async_client(self) -> openai.AsyncOpenAI:
        """Returns the AsyncOpenAI client instance (lazily initialized).

        Returns:
            The AsyncOpenAI instance.
        """
        with self._lock:
            if self._async_client is None:
                self._async_client = openai.AsyncOpenAI(**self._client_kwargs)
            return self._async_client

    @property
    def model(self) -> str:
        """Returns the configured model name.

        Returns:
            The model name.
        """
        return self._model

    @property
    def cache(self) -> LLMCache:
        """Returns the LLM cache.

        Returns:
            The cache instance.
        """
        return self._cache

    def get_usage(self) -> dict[str, Any]:
        """Returns LLM usage statistics.

        Returns:
            A dict of metrics.
        """
        with self._lock:
            return {
                "calls": self._calls,
                "retries": self._retries,
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "time_seconds": self._time_seconds,
                "calls_with_no_python_code": self._calls_with_no_python_code,
            }

    def reset_usage(self) -> None:
        """Resets all usage counters."""
        with self._lock:
            self._calls = 0
            self._retries = 0
            self._input_tokens = 0
            self._output_tokens = 0
            self._time_seconds = 0.0
            self._calls_with_no_python_code = 0

    def _build_request_kwargs(
        self,
        request: RenderedRequest,
        temperature: float,
        timeout: float | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": temperature,
            "max_tokens": request.max_tokens,
            "stop": request.stop,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout
        if request.enable_thinking is not None:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": request.enable_thinking}
            }
        return kwargs

    def _record_response(
        self,
        request: RenderedRequest,
        response: Any,
        elapsed: float,
    ) -> str | None:
        usage = getattr(response, "usage", None)
        prompt_tokens = (getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
        completion_tokens = (
            (getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
        )

        content = response.choices[0].message.content

        has_no_code = False
        if content:
            python_markdown = r"```python([\s\S]+?)(?:```|$)"
            if not re.search(python_markdown, content):
                has_no_code = True

        with self._lock:
            self._input_tokens += prompt_tokens
            self._output_tokens += completion_tokens
            self._time_seconds += elapsed
            if has_no_code:
                self._calls_with_no_python_code += 1

        cache_enabled = getattr(
            config.configuration.large_language_model, "enable_response_caching", False
        )
        if cache_enabled and content is not None:
            self._cache.set(request, content)

        return content

    def _handle_retry_error(
        self,
        *,
        exc: Exception,
        attempt: int,
        max_attempts: int,
        base_backoff: float,
        request_budget: float,
        request_started: float,
        timeout: float | None,
    ) -> float:
        is_rate_limit = self._rate_limit_errors and isinstance(exc, self._rate_limit_errors)
        is_timeout = self._timeout_errors and isinstance(exc, self._timeout_errors)
        is_api_err = self._api_errors and isinstance(exc, self._api_errors)

        if not (is_rate_limit or is_timeout or is_api_err):
            raise exc

        if is_rate_limit:
            label = "RateLimit"
            jitter = 3.0
        elif is_timeout:
            label = "Timeout"
            jitter = 2.0
        else:
            label = "APIError"
            jitter = 2.0

        wait = base_backoff * (2 ** min(attempt - 1, 6)) + random.uniform(0, jitter)  # noqa: S311
        _logger.warning(
            "LLM %s on attempt %d/%d, retrying in %.1fs: %s",
            label,
            attempt,
            max_attempts,
            wait,
            exc,
        )
        if attempt >= max_attempts:
            _logger.error("LLM retries exhausted.")
            raise exc
        if not _retry_fits_in_budget(
            budget=request_budget,
            elapsed=time.perf_counter() - request_started,
            wait=wait,
            timeout=timeout,
        ):
            _logger.error(
                "LLM request budget of %.0fs exhausted after %d attempt(s); "
                "giving up instead of retrying.",
                request_budget,
                attempt,
            )
            raise exc
        with self._lock:
            self._retries += 1
        return wait

    def send(self, request: RenderedRequest, timeout: float | None = None) -> str | None:
        """Sends a query to OpenAI with retry policy, timeout, and usage tracking.

        Args:
            request: The RenderedRequest payload.
            timeout: Per-attempt timeout in seconds overriding the configured
                ``request_timeout``; *None* uses the configured value.

        Returns:
            The response string, or None if failed.
        """
        if getattr(config.configuration.large_language_model, "enable_response_caching", False):
            cached = self._cache.get(request)
            if cached is not None:
                return cached

        max_attempts = config.configuration.large_language_model.max_retries
        base_backoff = 2.0
        if timeout is None:
            timeout = config.configuration.large_language_model.request_timeout
        request_budget = config.configuration.large_language_model.max_request_time
        request_started = time.perf_counter()

        with self._lock:
            self._calls += 1

        temperature = request.temperature
        with self._lock:
            if temperature == 0 and self._temperature_zero_rejected:
                temperature = _TEMPERATURE_FALLBACK
        temperature_fallback_applied = False

        for attempt in range(1, max_attempts + 1):
            start_time = time.perf_counter()
            try:
                kwargs = self._build_request_kwargs(request, temperature, timeout)
                response = self._client.chat.completions.create(**kwargs)
                elapsed = time.perf_counter() - start_time
                return self._record_response(request, response, elapsed)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.perf_counter() - start_time
                with self._lock:
                    self._time_seconds += elapsed

                if (
                    temperature == 0
                    and not temperature_fallback_applied
                    and _is_temperature_unsupported_error(exc)
                ):
                    temperature_fallback_applied = True
                    temperature = _TEMPERATURE_FALLBACK
                    with self._lock:
                        self._temperature_zero_rejected = True
                    _logger.warning(
                        "Model %r rejected temperature=0; using temperature=%s for this "
                        "and all future requests from this client.",
                        request.model,
                        _TEMPERATURE_FALLBACK,
                    )
                    continue

                wait = self._handle_retry_error(
                    exc=exc,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    base_backoff=base_backoff,
                    request_budget=request_budget,
                    request_started=request_started,
                    timeout=timeout,
                )
                time.sleep(wait)

        return None

    async def send_async(
        self, request: RenderedRequest, timeout: float | None = None
    ) -> str | None:
        """Sends a query asynchronously to OpenAI with retry policy, timeout, and usage tracking.

        Args:
            request: The RenderedRequest payload.
            timeout: Per-attempt timeout in seconds overriding the configured
                ``request_timeout``; *None* uses the configured value.

        Returns:
            The response string, or None if failed.
        """
        if getattr(config.configuration.large_language_model, "enable_response_caching", False):
            cached = self._cache.get(request)
            if cached is not None:
                return cached

        max_attempts = config.configuration.large_language_model.max_retries
        base_backoff = 2.0
        if timeout is None:
            timeout = config.configuration.large_language_model.request_timeout
        request_budget = config.configuration.large_language_model.max_request_time
        request_started = time.perf_counter()

        with self._lock:
            self._calls += 1

        temperature = request.temperature
        with self._lock:
            if temperature == 0 and self._temperature_zero_rejected:
                temperature = _TEMPERATURE_FALLBACK
        temperature_fallback_applied = False

        for attempt in range(1, max_attempts + 1):
            start_time = time.perf_counter()
            try:
                kwargs = self._build_request_kwargs(request, temperature, timeout)
                response = await self.async_client.chat.completions.create(**kwargs)
                elapsed = time.perf_counter() - start_time
                return self._record_response(request, response, elapsed)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.perf_counter() - start_time
                with self._lock:
                    self._time_seconds += elapsed

                if (
                    temperature == 0
                    and not temperature_fallback_applied
                    and _is_temperature_unsupported_error(exc)
                ):
                    temperature_fallback_applied = True
                    temperature = _TEMPERATURE_FALLBACK
                    with self._lock:
                        self._temperature_zero_rejected = True
                    _logger.warning(
                        "Model %r rejected temperature=0; using temperature=%s for this "
                        "and all future requests from this client.",
                        request.model,
                        _TEMPERATURE_FALLBACK,
                    )
                    continue

                wait = self._handle_retry_error(
                    exc=exc,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    base_backoff=base_backoff,
                    request_budget=request_budget,
                    request_started=request_started,
                    timeout=timeout,
                )
                await asyncio.sleep(wait)

        return None
