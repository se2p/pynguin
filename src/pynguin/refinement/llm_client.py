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
import time
from typing import TYPE_CHECKING

import pynguin.configuration as config
from pynguin.large_language_model.client import OpenAIClient
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.utils.llm import extract_code
from pynguin.utils.openai_key_resolver import require_api_key

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

_logger = logging.getLogger(__name__)

# Prefix for all sentinel strings returned when code generation fails. Callers
# use this to detect a failed generation instead of matching exact messages.
LLM_ERROR_PREFIX = "# LLM error"


def set_api_key() -> None:
    """Resolve and set the global OpenAI API key for the refinement client.

    Reuses Pynguin's shared key resolution/validation
    (:func:`pynguin.utils.openai_key_resolver.require_api_key`) and assigns the
    resolved value to the module-global ``openai.api_key`` used by
    :meth:`LLMClient._request_once`.
    """
    if OPENAI_AVAILABLE:
        openai.api_key = require_api_key().get_secret_value()


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


def _refinement_timeout() -> float | None:
    """Return the per-attempt timeout for refinement requests.

    Returns:
        The configured refinement timeout, falling back to the shared
        ``large_language_model.request_timeout`` when it is unset.
    """
    configured = config.configuration.llm_refinement.request_timeout
    if configured is None:
        return config.configuration.large_language_model.request_timeout
    return configured


class LLMClient:
    """A client to interact with the OpenAI API.

    Thin wrapper that exposes a ``generate_code(prompt)`` method and reuses
    Pynguin's shared OpenAI key handling and code-extraction helpers.  The
    response is mapped to a Python code block (```python ... ```) when present,
    otherwise the raw text is returned.
    """

    def __init__(self) -> None:
        """Initialize the LLM client.

        The model name is taken solely from the shared
        ``large_language_model.model_name`` configuration via the rendered
        prompt request, so no model is passed to the underlying client.
        """
        # Usage tracking (best-effort; OpenAI reports usage in the response).
        # ``_calls`` are the refinement/repair calls (a dedicated client instance
        # separate from the generation client).
        self._calls: int = 0
        self._retries: int = 0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._time_seconds: float = 0.0

        self._client = OpenAIClient()

    def reset_usage(self) -> None:
        """Reset all usage counters to zero."""
        self._client.reset_usage()
        self._calls = 0
        self._retries = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._time_seconds = 0.0

    def get_usage(self) -> dict:
        """Return a dict of cumulative usage statistics.

        Returns:
            A mapping with ``calls`` (repair calls), ``retries``,
            ``input_tokens``, ``output_tokens`` and ``time_seconds`` keys.
        """
        return {
            "calls": self._calls,
            "retries": self._retries,
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

        # Load refinement prompt configuration
        class RefinementPrompt(Prompt):
            _resource_name = "refinement"

            def _template_vars(self) -> list[str]:
                return ["prompt"]

            def render_request(self) -> RenderedRequest:
                return self.render(prompt=prompt)

        return self.generate_from_prompt(RefinementPrompt())

    def generate_from_prompt(self, prompt: Prompt) -> str:
        """Generate code using a templated Prompt instance.

        Args:
            prompt: The Prompt object to render and send.

        Returns:
            The extracted code, or a ``"# LLM ..."`` sentinel on failure.
        """
        request = prompt.render_request()

        # Sync refinement errors to client for dynamic check
        self._client._rate_limit_errors = _RATE_LIMIT_ERRORS  # noqa: SLF001
        self._client._timeout_errors = _TIMEOUT_ERRORS  # noqa: SLF001
        self._client._api_errors = _API_ERRORS  # noqa: SLF001

        start = time.perf_counter()
        try:
            response_text = self._client.send(request, timeout=_refinement_timeout())
            if response_text is None:
                return f"{LLM_ERROR_PREFIX}: request failed"
            return _extract_code(response_text)
        except _RATE_LIMIT_ERRORS:
            return f"{LLM_ERROR_PREFIX}: rate limited"
        except _TIMEOUT_ERRORS:
            return f"{LLM_ERROR_PREFIX}: timeout"
        except _API_ERRORS:
            return f"{LLM_ERROR_PREFIX}: request failed"
        except Exception:  # noqa: BLE001
            # Any unforeseen failure should degrade to a sentinel, never crash refinement.
            return f"{LLM_ERROR_PREFIX}: unable to generate code"
        finally:
            usage = self._client.get_usage()
            self._calls = usage["calls"]
            self._retries = usage.get("retries", 0)
            self._input_tokens = usage["input_tokens"]
            self._output_tokens = usage["output_tokens"]
            self._time_seconds += time.perf_counter() - start


def _extract_code(text: str) -> str:
    """Return the Python code block from ``text`` or the stripped text."""
    extracted = extract_code(text).strip()
    return extracted or text.strip()
