#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM client wrapper for OpenAI and Ollama providers."""

import os
import random
import re
import time
from pathlib import Path

import requests

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
    """A unified client to interact with LLM providers (Ollama or OpenAI).

    Simple wrapper that exposes a `generate_code(prompt)` method. It maps a
    text response to a Python code block (```python ... ```) when present.

    Supports two providers:
    - "ollama": University's local Ollama instance (free, requires VPN)
    - "openai": OpenAI API (requires API key, costs money)
    """

    def __init__(
        self,
        provider: str = "ollama",  # "ollama" or "openai"
        base_url: str = "http://rhaegal.dimis.fim.uni-passau.de:15343",
        model_name: str = "codellama:7b",
        api_key: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            provider: LLM provider - "ollama" or "openai"
            base_url: Base URL (for Ollama only)
            model_name: Model to use
                - Ollama: "codellama:7b" (fast), "deepseek-coder-v2:16b" (better quality)
                - OpenAI: "gpt-4o" (best), "gpt-4o-mini" (cheap)
            api_key: OpenAI API key (only needed for provider="openai")
        """
        self.provider = provider.lower()
        self.model = model_name

        # Usage tracking (best-effort; OpenAI provides usage, Ollama does not)
        self._calls: int = 0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._time_seconds: float = 0.0

        if self.provider == "ollama":
            self.base_url = base_url.rstrip("/")
            self.generate_endpoint = f"{self.base_url}/api/generate"
            self.api_key = None
        elif self.provider == "openai":
            # OpenAI setup
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                    "or pass api_key parameter."
                )
            self.openai_endpoint = "https://api.openai.com/v1/chat/completions"
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'ollama' or 'openai'.")

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
        if self.provider == "ollama":
            return self._generate_ollama(prompt)
        if self.provider == "openai":
            return self._generate_openai(prompt)
        return "# LLM error: unknown provider"

    def _generate_ollama(self, prompt: str) -> str:
        """Generate code using Ollama."""
        attempts = 0
        base_backoff = 2
        max_attempts = 3

        while attempts < max_attempts:
            try:
                start = time.perf_counter()
                self._calls += 1
                payload = {"model": self.model, "prompt": prompt, "stream": False}

                response = requests.post(self.generate_endpoint, json=payload, timeout=120)

                if response.status_code != 200:
                    raise requests.HTTPError(f"HTTP {response.status_code}: {response.text}")

                result = response.json()
                text = result.get("response", "")

                self._time_seconds += time.perf_counter() - start

                return self._extract_code(text)

            except requests.exceptions.Timeout:  # noqa: PERF203
                attempts += 1
                if attempts >= max_attempts:
                    return "# LLM error: timeout"

                exponential_wait = base_backoff * (2 ** (attempts - 1))
                jitter = random.uniform(0, 1)  # noqa: S311
                wait_time = min(exponential_wait + jitter, 30)

                time.sleep(wait_time)

            except requests.exceptions.RequestException:
                attempts += 1

                if attempts >= max_attempts:
                    return "# LLM error: request failed"

                exponential_wait = base_backoff * (2 ** (attempts - 1))
                jitter = random.uniform(0, 1)  # noqa: S311
                wait_time = min(exponential_wait + jitter, 30)

                time.sleep(wait_time)

            except Exception:  # noqa: BLE001
                return "# LLM error: unable to generate code"

        return "# LLM retries exhausted"

    def _generate_openai(self, prompt: str) -> str:
        """Generate code using OpenAI API."""
        attempts = 0
        base_backoff = 1
        max_attempts = 3

        while attempts < max_attempts:
            try:
                start = time.perf_counter()
                self._calls += 1
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                payload = {
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

                response = requests.post(
                    self.openai_endpoint, headers=headers, json=payload, timeout=60
                )

                if response.status_code != 200:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", error_msg)
                    except Exception:  # noqa: BLE001, S110
                        pass
                    raise requests.HTTPError(f"HTTP {response.status_code}: {error_msg}")

                result = response.json()

                # Best-effort token accounting (depends on API returning `usage`)
                usage = result.get("usage") if isinstance(result, dict) else None
                if isinstance(usage, dict):
                    self._input_tokens += int(usage.get("prompt_tokens", 0) or 0)
                    self._output_tokens += int(usage.get("completion_tokens", 0) or 0)

                text = result["choices"][0]["message"]["content"]

                self._time_seconds += time.perf_counter() - start

                return self._extract_code(text)

            except requests.exceptions.Timeout:  # noqa: PERF203
                attempts += 1
                if attempts >= max_attempts:
                    return "# LLM error: timeout"

                wait_time = base_backoff * (2 ** (attempts - 1))
                time.sleep(wait_time)

            except requests.exceptions.RequestException:
                attempts += 1
                if attempts >= max_attempts:
                    return "# LLM error: request failed"

                wait_time = base_backoff * (2 ** (attempts - 1))
                time.sleep(wait_time)

            except Exception:  # noqa: BLE001
                return "# LLM error: unable to generate code"

        return "# LLM retries exhausted"

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
