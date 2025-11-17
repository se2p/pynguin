# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-License-Identifier: MIT
"""Implements type inference strategies as providers."""

from __future__ import annotations

import asyncio
import builtins
import inspect
import json
import logging
import time
import types
import typing
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, get_type_hints

try:
    from pydantic import SecretStr

    from pynguin.utils.llm import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import pynguin.configuration as config
from pynguin.large_language_model.parsing.type_str_parser import TypeStrParser
from pynguin.large_language_model.prompts.typeinferenceprompt import (
    TypeInferencePrompt,
    get_inference_system_prompt,
)
from pynguin.utils.llm import LLMProvider
from pynguin.utils.orderedset import OrderedSet

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from pynguin.analyses.typesystem import TypeSystem

from copy import deepcopy

_LOGGER = logging.getLogger(__name__)

ANY_STR = "typing.Any"


class InferenceProvider(ABC):
    """Abstract base class for type inference strategies working on callables."""

    def __init__(self) -> None:
        """Initializes the inference provider and its metrics."""
        self._metrics = {
            "failed_inferences": 0,
            "successful_inferences": 0,
            "sent_requests": 0,
            "total_setup_time": 0,
        }

    @abstractmethod
    def provide(self, method: Callable) -> dict[str, Any]:
        """Returns the parameter types for the given method."""

    def get_metrics(self) -> dict[str, Any]:
        """Return metrics about the inference process."""
        return self._metrics


class LLMInference(InferenceProvider):
    """LLM-based type inference strategy for plain Python callables."""

    DEFAULT_MAX_PARALLEL_CALLS = 20

    def __init__(
        self,
        callables: Sequence[Callable[..., Any]],
        provider: LLMProvider,
        type_system: TypeSystem,
        max_parallel_calls: int = DEFAULT_MAX_PARALLEL_CALLS,
    ) -> None:
        """Initializes the LLM-based type inference strategy.

        Args:
            callables: The callables for which we want to infer types.
            provider: The LLM provider to use.
            type_system: The type system to use for resolving types.
            max_parallel_calls: The maximum number of parallel calls to the LLM.
        """
        self._max_parallel_calls = max_parallel_calls
        self._types = types

        self._subtypes: OrderedSet[str] = OrderedSet([
            t.name for t in type_system.get_subclasses(type_system.to_type_info(str))
        ])
        match provider:
            case LLMProvider.OPENAI:
                self._model = OpenAI(
                    api_key=SecretStr(config.configuration.large_language_model.api_key),
                    system_prompt=get_inference_system_prompt(),
                    model=config.configuration.large_language_model.model_name,
                )
            case _:
                raise NotImplementedError(f"Unknown provider {provider}")

        self._callables: list[Callable[..., Any]] = list(callables)
        self._inference_by_callable: OrderedDict[Callable, dict[str, str]] = OrderedDict()
        self._type_string_parser = TypeStrParser(type_system)
        super().__init__()
        start = time.time_ns()
        self._infer_all()
        self._metrics["total_setup_time"] = time.time_ns() - start
        _LOGGER.debug(
            "Inference completed in %.3fs",
            self._metrics["total_setup_time"],
        )

    def provide(self, method: Callable) -> dict[str, Any]:
        """Return the provider of the type inference for the given method."""
        string_hints: dict[str, str] = self._inference_by_callable.get(method, {})
        result: dict[str, Any] = {}
        for param, type_str in string_hints.items():
            if param in {"*args", "**kwargs"}:
                result[param] = Any
            else:
                resolved = self._type_string_parser.parse(type_str)
                if resolved is None or resolved is type(builtins.object):
                    _LOGGER.debug(
                        "Could not resolve type string '%s' for parameter '%s'",
                        type_str,
                        param,
                    )
                    self._metrics["failed_inferences"] += 1
                    resolved = builtins.object
                else:
                    self._metrics["successful_inferences"] += 1
                result[param] = resolved
        return result

    def _infer_all(self) -> None:
        """Infer types for all callables in parallel at initialization time."""
        prompts = self._build_prompt_map(self._callables)
        _LOGGER.debug("Sending %d prompts to LLM", len(prompts))
        raw = self._send_prompts(prompts)
        _LOGGER.debug("Received %d responses from LLM", len(raw))
        self._metrics["sent_requests"] = len(raw)
        for func, response in raw.items():
            prior = self._prior_types(func)
            parsed = self._parse_json_response(response, prior)
            self._inference_by_callable[func] = parsed

    # ---- prompt building ----
    def _build_prompt_map(
        self, funcs: Sequence[Callable[..., Any]]
    ) -> OrderedDict[Callable[..., Any], str]:
        prompts: OrderedDict[Callable[..., Any], str] = OrderedDict()
        for func in funcs:
            try:
                prompt = TypeInferencePrompt(func, subtypes=self._subtypes)
                prompts[func] = prompt.build_user_prompt()
            except Exception as exc:  # noqa: BLE001, PERF203
                _LOGGER.error("Skipping callable %r due to prompt build failure: %s", func, exc)
        return prompts

    # ---- LLM I/O (parallel) ----
    def _send_prompt(self, prompt: str) -> str:
        return self._model.chat(prompt) or ""

    def _send_prompts(
        self, prompts: Mapping[Callable[..., Any], str]
    ) -> OrderedDict[Callable[..., Any], str]:
        coro = self._gather_prompts_async(prompts)
        return self._run_coro(coro)

    async def _gather_prompts_async(
        self, prompts: Mapping[Callable[..., Any], str]
    ) -> OrderedDict[Callable[..., Any], str]:
        sem = asyncio.Semaphore(self._max_parallel_calls)
        tasks = [
            asyncio.create_task(self._prompt_worker(func, prompt, sem))
            for func, prompt in prompts.items()
        ]

        results: dict[Callable[..., Any], str] = {}
        for task in asyncio.as_completed(tasks):
            try:
                func, resp = await task
                results[func] = resp
            except Exception as exc:  # noqa: PERF203
                _LOGGER.exception("Prompt failed: %s", exc)

        return OrderedDict((f, results.get(f, "")) for f in prompts)

    async def _prompt_worker(
        self,
        func: Callable[..., Any],
        prompt: str,
        sem: asyncio.Semaphore,
    ) -> tuple[Callable[..., Any], str]:
        async with sem:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, self._send_prompt, prompt)
            return func, resp

    @staticmethod
    def _run_coro(coro: typing.Coroutine) -> Any:
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(coro)

    # ---- utilities ----
    def _prior_types(self, func: Callable[..., Any]) -> dict[str, str]:
        """Build a default type map from existing annotations/signature."""
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            return {"*args": ANY_STR, "**kwargs": ANY_STR}

        result: dict[str, str] = {}
        params = list(sig.parameters.values())

        for i, p in enumerate(params):
            if i == 0 and p.name in {"self", "cls"}:
                continue
            ann = p.annotation
            if ann is inspect._empty:  # noqa: SLF001
                result[p.name] = ANY_STR
            else:
                result[p.name] = self._annotation_to_str(ann)
        return result

    @staticmethod
    def _annotation_to_str(ann: Any) -> str:
        try:
            if getattr(ann, "__module__", "") and getattr(ann, "__qualname__", ""):
                return f"{ann.__module__}.{ann.__qualname__}"
            return str(ann)
        except Exception:  # noqa: BLE001
            return ANY_STR

    @staticmethod
    def _parse_json_response(response: str, prior: dict[str, str]) -> dict[str, str]:
        """Parse LLM JSON; on failure, return `prior` untouched."""
        if not response:
            return prior
        try:
            data = json.loads(response)
            if not isinstance(data, dict):
                return prior

            merged: dict[str, str] = dict(prior)

            for k in list(prior.keys()):
                if k == "return":
                    continue
                if k in data and isinstance(data[k], str) and data[k].strip():
                    merged[k] = data[k].strip()

            return merged
        except json.JSONDecodeError as exc:
            _LOGGER.error("Failed to parse JSON response from LLM: %s", exc)
            return prior

    # ---- metrics/collection ----
    def get_inference_map(self) -> OrderedDict[Callable[..., Any], dict[str, str]]:
        """Return the mapping from callables to parsed inference strings.

        This is exposed for metrics collection.
        """
        return OrderedDict(deepcopy(self._inference_by_callable))

    def get_callables(self) -> list[Callable[..., Any]]:
        """Return the list of callables that were provided to this inference provider."""
        return deepcopy(self._callables)

    def prior_types_for(self, func: Callable[..., Any]) -> dict[str, str]:
        """Return the prior/annotated type strings for the given callable.

        This wraps the internal _prior_types helper so external code does not
        access private members.
        """
        return deepcopy(self._prior_types(func))


class NoInference(InferenceProvider):
    """No-op type inference strategy that always returns empty dicts."""

    def provide(self, method: Callable) -> dict[str, Any]:
        """Returns an empty dict for any method."""
        return {}


class HintInference(InferenceProvider):
    """Type inference strategy that uses user-provided hints."""

    def provide(self, method: Callable) -> dict[str, Any]:
        """Provides PEP484-style type information, if available.

        Args:
            method: The method for which we want type hints.

        Returns:
            A dict mapping parameter names to type hints.
        """
        try:
            hints = get_type_hints(method)
            # Sadly there is no guarantee that resolving the type hints actually works.
            # If the developers annotated something with an erroneous type hint we fall
            # back to no type hints, i.e., use Any.
            # The import used in the type hint could also be conditional on
            # typing.TYPE_CHECKING, e.g., to avoid circular imports, in which case this
            # also fails.
        except (AttributeError, NameError, TypeError) as exc:
            _LOGGER.debug("Could not retrieve type hints for %s", method)
            _LOGGER.debug(exc)
            hints = {}
        return hints
