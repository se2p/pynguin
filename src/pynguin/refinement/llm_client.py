#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM client wrapper for the OpenAI provider."""

import logging
import os
import random
import re
import time
from pathlib import Path

import requests  # type: ignore[import-untyped]

_logger = logging.getLogger(__name__)

_HTTP_OK = 200
_HTTP_TOO_MANY_REQUESTS = 429

try:
    from dotenv import load_dotenv

    # Look for .env file in project root (up to 5 levels from this file)
    env_path = Path(__file__).resolve()
    for _ in range(5):
        env_path = env_path.parent
        env_file = env_path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    # python-dotenv not installed, will rely on system environment variables
    pass


class LLMClient:
    """A client to interact with the OpenAI API.

    Simple wrapper that exposes a `generate_code(prompt)` method. It maps a
    text response to a Python code block (```python ... ```) when present.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            model_name: OpenAI model to use (e.g., "gpt-4o-mini", "gpt-4o")
            api_key: OpenAI API key (required; can come from OPENAI_API_KEY)
        """
        self.model = model_name

        # Usage tracking (best-effort; OpenAI provides usage)
        self._calls: int = 0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._time_seconds: float = 0.0

        # OpenAI setup
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self.openai_endpoint = "https://api.openai.com/v1/chat/completions"

    def reset_usage(self) -> None:
        """Reset all usage counters to zero."""
        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._time_seconds = 0.0

    def get_usage(self) -> dict:
        """Return a dict of cumulative usage statistics."""
        return {
            "calls": self._calls,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "time_seconds": self._time_seconds,
        }

    def generate_code(self, prompt: str) -> str:
        """Generate text and return the Python code block (or plain text).

        Retries on network/server errors with exponential backoff + jitter.
        Returns a sentinel string when retries are exhausted or on unrecoverable errors.
        """
        return self._generate_openai(prompt)

    def _generate_openai(self, prompt: str) -> str:
        """Generate code using OpenAI API with retry + exponential backoff."""
        base_backoff = 2
        max_attempts = 8

        for attempt in range(1, max_attempts + 1):
            outcome = self._attempt_with_handling(prompt, attempt, max_attempts, base_backoff)
            if outcome is not None:
                return outcome

        return "# LLM retries exhausted"

    def _attempt_with_handling(
        self, prompt: str, attempt: int, max_attempts: int, base_backoff: int
    ) -> str | None:
        """Run one request attempt; return result/sentinel, or ``None`` to retry."""
        try:
            return self._request_once(prompt)
        except _RateLimitError as rle:
            # ``random`` jitter is for backoff spreading, not cryptographic use.
            jitter = random.uniform(0, 3)  # noqa: S311
            wait = (rle.retry_after or base_backoff * (2 ** min(attempt - 1, 6))) + jitter
            return self._sleep_or_giveup(
                attempt, max_attempts, wait, "Rate-limited (429)", "# LLM error: rate limited"
            )
        except requests.exceptions.Timeout:
            wait = base_backoff * (2 ** min(attempt - 1, 6)) + random.uniform(0, 2)  # noqa: S311
            return self._sleep_or_giveup(
                attempt, max_attempts, wait, "Timeout", "# LLM error: timeout"
            )
        except requests.exceptions.RequestException as exc:
            wait = base_backoff * (2 ** min(attempt - 1, 6)) + random.uniform(0, 2)  # noqa: S311
            return self._sleep_or_giveup(
                attempt, max_attempts, wait, f"Request error ({exc})", "# LLM error: request failed"
            )
        except Exception:  # noqa: BLE001
            # Any unforeseen failure should degrade to a sentinel, never crash refinement.
            return "# LLM error: unable to generate code"

    def _sleep_or_giveup(
        self, attempt: int, max_attempts: int, wait: float, reason: str, exhausted_msg: str
    ) -> str | None:
        """Log the retry, sleep, and return ``None``; or the sentinel when exhausted."""
        _logger.warning("%s, retry %d/%d in %.1fs", reason, attempt, max_attempts, wait)
        if attempt >= max_attempts:
            return exhausted_msg
        time.sleep(wait)
        return None

    def _request_once(self, prompt: str) -> str:
        """Perform a single OpenAI request and return the extracted code.

        Raises:
            _RateLimitError: On an HTTP 429 response.
            requests.HTTPError: On any other non-200 response.
            requests.exceptions.RequestException: On network/transport errors.
        """
        start = time.perf_counter()
        self._calls += 1
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            self.openai_endpoint, headers=headers, json=self._build_payload(prompt), timeout=90
        )
        code = self._parse_response(response)
        self._time_seconds += time.perf_counter() - start
        return code

    def _build_payload(self, prompt: str) -> dict:
        """Build the chat-completions request payload."""
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Python developer. "
                        "Generate clean, correct Python code "
                        "based on the user's request."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,  # Low temperature for more consistent code generation
            "max_tokens": 2000,
        }

    def _parse_response(self, response) -> str:
        """Validate the response, account tokens, and return the extracted code."""
        if response.status_code == _HTTP_TOO_MANY_REQUESTS:
            retry_after = response.headers.get("Retry-After")
            raise _RateLimitError(float(retry_after) if retry_after else None)

        if response.status_code != _HTTP_OK:
            raise requests.HTTPError(
                f"HTTP {response.status_code}: {self._error_message(response)}"
            )

        result = response.json()
        self._account_tokens(result)
        text = result["choices"][0]["message"]["content"]
        return self._extract_code(text)

    @staticmethod
    def _error_message(response) -> str:
        """Extract a human-readable error message from a failed response."""
        try:
            return response.json().get("error", {}).get("message", response.text)
        except (ValueError, AttributeError):
            return response.text

    def _account_tokens(self, result) -> None:
        """Best-effort token accounting from the API ``usage`` field."""
        usage = result.get("usage") if isinstance(result, dict) else None
        if isinstance(usage, dict):
            self._input_tokens += int(usage.get("prompt_tokens", 0) or 0)
            self._output_tokens += int(usage.get("completion_tokens", 0) or 0)

    def _extract_code(self, text: str) -> str:
        """Extract Python code block from text, or return text as-is."""
        # Try with language specifier first
        match = re.search(r"```python\s*\n([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()

        # Try without language specifier
        match = re.search(r"```\s*\n([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()

        # No code blocks found, return as-is
        return text.strip()


class _RateLimitError(Exception):
    """Internal sentinel for HTTP 429 responses."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
