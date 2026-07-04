#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM client wrapper for the OpenAI provider.

Reuses Pynguin's existing OpenAI infrastructure instead of duplicating it:
API-key resolution and validation come from
``pynguin.large_language_model.llmagent`` and Markdown code-block extraction
from ``pynguin.utils.llm``.  The model name is taken from the shared
``large_language_model`` configuration.
"""

from __future__ import annotations

import logging
import random
import time

import pynguin.configuration as config
from pynguin.large_language_model.llmagent import set_api_key
from pynguin.utils.llm import extract_code

try:
    import openai
    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

_logger = logging.getLogger(__name__)

# A low temperature keeps code generation deterministic and consistent, which
# matters for refinement where we want reproducible edits.
_TEMPERATURE = 0.2
_MAX_TOKENS = 2000
_MAX_ATTEMPTS = 8
_BASE_BACKOFF = 2

_SYSTEM_PROMPT = (
    "You are an expert Python developer. "
    "Generate clean, correct Python code based on the user's request."
)

if OPENAI_AVAILABLE:
    _RATE_LIMIT_ERRORS: tuple[type[Exception], ...] = (openai.RateLimitError,)
    _TIMEOUT_ERRORS: tuple[type[Exception], ...] = (openai.APITimeoutError,)
    _API_ERRORS: tuple[type[Exception], ...] = (openai.OpenAIError,)
else:  # pragma: no cover - exercised only without the optional openai extra
    _RATE_LIMIT_ERRORS = ()
    _TIMEOUT_ERRORS = ()
    _API_ERRORS = ()


class LLMClient:
    """A client to interact with the OpenAI API.

    Thin wrapper that exposes a ``generate_code(prompt)`` method and reuses
    Pynguin's shared OpenAI key handling and code-extraction helpers.  The
    response is mapped to a Python code block (```python ... ```) when present,
    otherwise the raw text is returned.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize the LLM client.

        Args:
            model_name: OpenAI model to use.  Defaults to the shared
                ``large_language_model.model_name`` configuration.
        """
        self.model = model_name or config.configuration.large_language_model.model_name

        # Usage tracking (best-effort; OpenAI reports usage in the response).
        self._calls: int = 0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._time_seconds: float = 0.0

        # Reuse Pynguin's shared key resolution + validation (config or env).
        set_api_key()

    def reset_usage(self) -> None:
        """Reset all usage counters to zero."""
        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._time_seconds = 0.0

    def get_usage(self) -> dict:
        """Return a dict of cumulative usage statistics.

        Returns:
            A mapping with ``calls``, ``input_tokens``, ``output_tokens`` and
            ``time_seconds`` keys.
        """
        return {
            "calls": self._calls,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "time_seconds": self._time_seconds,
        }

    def generate_code(self, prompt: str) -> str:
        """Generate text and return the Python code block (or plain text).

        Retries on rate-limit/timeout/API errors with exponential backoff and
        jitter.  Returns a sentinel string (``"# LLM error: ..."``) when
        retries are exhausted or on unrecoverable errors so that callers can
        degrade gracefully instead of crashing.

        Args:
            prompt: The user prompt to send to the model.

        Returns:
            The extracted code, or a ``"# LLM ..."`` sentinel on failure.
        """
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            outcome = self._attempt_with_handling(prompt, attempt)
            if outcome is not None:
                return outcome
        return "# LLM retries exhausted"

    def _attempt_with_handling(self, prompt: str, attempt: int) -> str | None:
        """Run one request attempt; return result/sentinel, or ``None`` to retry."""
        try:
            return self._request_once(prompt)
        except _RATE_LIMIT_ERRORS:
            # ``random`` jitter is for backoff spreading, not cryptographic use.
            wait = _BASE_BACKOFF * (2 ** min(attempt - 1, 6)) + random.uniform(0, 3)  # noqa: S311
            return self._sleep_or_giveup(attempt, wait, "Rate-limited", "# LLM error: rate limited")
        except _TIMEOUT_ERRORS:
            wait = _BASE_BACKOFF * (2 ** min(attempt - 1, 6)) + random.uniform(0, 2)  # noqa: S311
            return self._sleep_or_giveup(attempt, wait, "Timeout", "# LLM error: timeout")
        except _API_ERRORS as exc:
            wait = _BASE_BACKOFF * (2 ** min(attempt - 1, 6)) + random.uniform(0, 2)  # noqa: S311
            return self._sleep_or_giveup(
                attempt, wait, f"API error ({exc})", "# LLM error: request failed"
            )
        except Exception:  # noqa: BLE001
            # Any unforeseen failure should degrade to a sentinel, never crash refinement.
            return "# LLM error: unable to generate code"

    def _sleep_or_giveup(
        self, attempt: int, wait: float, reason: str, exhausted_msg: str
    ) -> str | None:
        """Log the retry, sleep, and return ``None``; or the sentinel when exhausted."""
        _logger.warning("%s, retry %d/%d in %.1fs", reason, attempt, _MAX_ATTEMPTS, wait)
        if attempt >= _MAX_ATTEMPTS:
            return exhausted_msg
        time.sleep(wait)
        return None

    def _request_once(self, prompt: str) -> str:
        """Perform a single OpenAI request and return the extracted code."""
        start = time.perf_counter()
        self._calls += 1
        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=_SYSTEM_PROMPT),
            ChatCompletionUserMessageParam(role="user", content=prompt),
        ]
        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        self._account_tokens(response)
        text = response.choices[0].message.content or ""
        self._time_seconds += time.perf_counter() - start
        return _extract_code(text)

    def _account_tokens(self, response) -> None:
        """Best-effort token accounting from the API ``usage`` field."""
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
            self._output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)


def _extract_code(text: str) -> str:
    """Return the Python code block from ``text``, or the stripped text.

    Reuses :func:`pynguin.utils.llm.extract_code`; falls back to the raw
    (stripped) text when the model returns code without Markdown fences, which
    the refinement prompts explicitly request.

    Args:
        text: The raw text returned by the model.

    Returns:
        The extracted code block, or the stripped text when no fenced block is
        present.
    """
    extracted = extract_code(text).strip()
    return extracted or text.strip()
