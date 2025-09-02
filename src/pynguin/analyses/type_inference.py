# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-License-Identifier: MIT
"""Implements type inference strategies as providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import builtins
from collections import OrderedDict
import collections
import inspect
import json
import logging
import os
import time
import types
from typing import Any, get_type_hints
import typing

from pydantic import SecretStr
from pynguin.large_language_model.prompts.typeinferenceprompt import (
    TypeInferencePrompt,
    get_inference_system_prompt,
)
from pynguin.utils.llm import LLMProvider, OpenAI

if typing.TYPE_CHECKING:
    from pynguin.analyses.typesystem import TypeSystem
    from collections.abc import Callable, Mapping, Sequence

_LOGGER = logging.getLogger(__name__)

OPENAI_API_KEY = SecretStr(os.environ.get("OPENAI_API_KEY", ""))
TEMPERATURE = 0.2
MODEL = "gpt-4.1-nano-2025-04-14"
ANY_STR = "typing.Any"


class InferenceProvider(ABC):
    """Abstract base class for type inference strategies working on callables."""

    @abstractmethod
    def provide(self, method: Callable) -> dict[str, Any]:
        """Return the provider of the type inference for the given method."""


class LLMInference(InferenceProvider):
    """LLM-based type inference strategy for plain Python callables."""

    def __init__(
        self,
        callables: Sequence[Callable[..., Any]],
        provider: LLMProvider,
        type_system: TypeSystem,
        max_parallel_calls: int = 20,
    ) -> None:
        """Initializes the LLM-based type inference strategy.

        Args:
            callables: The callables for which we want to infer types.
            provider: The LLM provider to use.
            max_parallel_calls: The maximum number of parallel calls to the LLM.
        """
        self._max_parallel_calls = max_parallel_calls
        self._types = types
        match provider:
            case LLMProvider.OPENAI:
                self._model = OpenAI(
                    OPENAI_API_KEY, TEMPERATURE, get_inference_system_prompt(), MODEL
                )
            case _:
                raise NotImplementedError(f"Unknown provider {provider}")

        self._callables: list[Callable[..., Any]] = list(callables)
        self._inference_by_callable: OrderedDict[Callable, dict[str, str]] = OrderedDict()
        self._type_system = type_system
        self._infer_all()

    def provide(self, method: Callable) -> dict[str, Any]:
        """Return the provider of the type inference for the given method."""
        string_hints: dict[str, str] = self._inference_by_callable.get(method, {})
        result: dict[str, Any] = {}
        for param, type_str in string_hints.items():
            if param in {"*args", "**kwargs"}:
                result[param] = Any
            else:
                resolved = self._string_to_type(type_str)
                if resolved is None:
                    # TODO: add statistics
                    _LOGGER.debug(
                        "Could not resolve type string '%s' for parameter '%s'",
                        type_str,
                        param,
                    )
                    resolved = Any
                result[param] = resolved
        return result

    def _infer_all(self) -> None:
        """Infer types for all callables in parallel at initialization time."""
        start = time.time()
        prompts = self._build_prompt_map(self._callables)
        raw = self._send_prompts(prompts)
        _LOGGER.debug("LLM raw responses collected for %d callables", len(raw))

        for func, response in raw.items():
            prior = self._prior_types(func)
            parsed = self._parse_json_response(response, prior)
            self._inference_by_callable[func] = parsed

        _LOGGER.debug("Inference completed in %.3fs", time.time() - start)

    # ---- prompt building ----
    def _build_prompt_map(
        self, funcs: Sequence[Callable[..., Any]]
    ) -> OrderedDict[Callable[..., Any], str]:
        prompts: OrderedDict[Callable[..., Any], str] = OrderedDict()
        for func in funcs:
            try:
                prompt = TypeInferencePrompt(func)
                prompts[func] = prompt.build_user_prompt()
            except Exception as exc:  # noqa: BLE001, PERF203
                _LOGGER.error("Skipping callable %r due to prompt build failure: %s", func, exc)
        return prompts

    # ---- LLM I/O (parallel) ----
    def _send_prompt(self, prompt: str) -> str:
        return self._model.chat(prompt)

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
    def _run_coro(coro: asyncio.coroutines.coroutine) -> Any:
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

    def _annotation_to_str(self, ann: Any) -> str:
        try:
            if getattr(ann, "__module__", "") and getattr(ann, "__qualname__", ""):
                return f"{ann.__module__}.{ann.__qualname__}"
            return str(ann)
        except Exception:  # noqa: BLE001
            return ANY_STR

    def _parse_json_response(self, response: str, prior: dict[str, str]) -> dict[str, str]:
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

    def _string_to_type(self, type_str: str) -> type | None:
        """Converts a string to a type object, if possible.

        Uses the typeSystem to resolve types.

        Args:
            type_str: The string representation of the type.

        Returns:
            The corresponding type object, or None if it cannot be resolved.
        """
        if self._is_any(type_str):
            # type_str could be "Any", "typing.Any", or "builtins.object"
            return None
        if self._is_none(type_str):
            # type_str could be "None", "NoneType", or "type(None)"
            return type(None)
        if self._is_tuple(type_str):
            # type_str could be e.g. "Tuple[int, str]", "tuple[int, str]", "typing.Tuple[int, str]"
            inner_types = self._get_inner_types(type_str)
            resolved_inner = [self._string_to_type(t) or builtins.object for t in inner_types]
            return tuple(resolved_inner)
        if self._is_dict(type_str):
            # type_str could be e.g. "Dict[str, int]", "dict[str, int]", "typing.Dict[str, int]"
            inner_types = self._get_inner_types(type_str)
            if len(inner_types) == 2:
                key_type = self._string_to_type(inner_types[0]) or builtins.object
                value_type = self._string_to_type(inner_types[1]) or builtins.object
                return dict[key_type, value_type]
            else:
                return dict[builtins.object, builtins.object]
        if self._is_set(type_str):
            # type_str could be e.g. "Set[int]", "set[int]", "typing.Set[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self._string_to_type(inner_type) if inner_type else None
            return set[resolved_inner or builtins.object]
        if self._is_list(type_str):
            # type_str could be e.g. "List[int]", "list[int]", "typing.List[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self._string_to_type(inner_type) if inner_type else None
            return list[resolved_inner or builtins.object]
        if self._is_union(type_str):
            # type_str could be e.g. "Union[int, str]", "typing.Union[int, str]", or "int | str"
            inner_types = self._get_union_inner_types(type_str)
            resolved_inner = [self._string_to_type(t) or builtins.object for t in inner_types]
            return typing.Union[tuple(resolved_inner)]  # noqa: UP007
        if self._is_optional(type_str):
            # type_str could be e.g. "Optional[int]", "typing.Optional[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self._string_to_type(inner_type)
            return typing.Optional[resolved_inner]  # noqa: UP045
        if self._is_deque(type_str):
            # type_str could be e.g. "Deque[int]", "deque[int]", "typing.Deque[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self._string_to_type(inner_type) if inner_type else None
            return collections.deque[resolved_inner or builtins.object]
        if self._is_iterable(type_str):
            # type_str could be e.g. "Iterable[int]", "iterable[int]", "typing.Iterable[int]"
            inner_type = self._get_list_inner_type(type_str)
            resolved_inner = self._string_to_type(inner_type) if inner_type else None
            return typing.Iterable[resolved_inner or builtins.object]
        # Try to resolve the type directly
        simple_types = self._type_system.get_all_types()
        for t in simple_types:
            if type_str in {t.qualname, t.name}:
                return t.raw_type
        return None

    # ---- type string parsing helpers ----
    def _is_any(self, hint: str) -> bool:
        return hint in {"Any", "typing.Any", "builtins.object"}

    def _is_none(self, hint: str) -> bool:
        return hint in {"None", "NoneType", "type(None)"}

    def _is_tuple(self, hint: str) -> bool:
        """Check if the hint represents a tuple type."""
        return hint.startswith(("Tuple", "tuple", "typing.Tuple", "collections.abc.Tuple"))

    def _is_list(self, hint: str) -> bool:
        """Check if the hint represents a list type."""
        return hint.startswith(("List", "list", "typing.List", "collections.abc.List"))

    def _is_union(self, hint: str) -> bool:
        """Check if the hint represents a union type."""
        return hint.startswith(("Union", "typing.Union")) or " | " in hint

    def _is_optional(self, hint: str) -> bool:
        """Check if the hint represents an optional type."""
        return hint.startswith(("Optional", "typing.Optional"))

    def _is_set(self, hint: str) -> bool:
        """Check if the hint represents a set type."""
        return hint.startswith(("Set", "set", "typing.Set", "collections.abc.Set"))

    def _is_dict(self, hint: str) -> bool:
        """Check if the hint represents a dict type."""
        return hint.startswith(("Dict", "dict", "typing.Dict", "collections.abc.Dict"))

    def _is_iterable(self, hint: str) -> bool:
        """Check if the hint represents an iterable type."""
        return hint.startswith((
            "Iterable",
            "iterable",
            "typing.Iterable",
            "collections.abc.Iterable",
        ))

    def _is_deque(self, hint: str) -> bool:
        """Check if the hint represents a deque type."""
        return hint.startswith((
            "Deque",
            "deque",
            "typing.Deque",
            "collections.deque",
            "collections.abc.Deque",
        ))

    def _get_inner_types(self, hint: str) -> list[str]:
        """Extract inner types from type hint.

        E.g. for "Tuple[int, str]" returns ["int", "str"].
        """
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return []
        inner = hint[start + 1 : end]
        return [t.strip() for t in inner.split(",")]

    def _get_list_inner_type(self, hint: str) -> str | None:
        """Extract inner type from a list type hint."""
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return None
        return hint[start + 1 : end].strip()

    def _get_union_inner_types(self, hint: str) -> list[str]:
        """Extract inner types from a union type hint."""
        if " | " in hint:
            return [t.strip() for t in hint.split(" | ")]
        start = hint.find("[")
        end = hint.rfind("]")
        if start == -1 or end == -1 or start >= end:
            return []
        inner = hint[start + 1 : end]
        return [t.strip() for t in inner.split(",")]


class NoInference(InferenceProvider):
    """No-op type inference strategy that always returns empty dicts."""

    def provide(self, method: Callable) -> dict[str, Any]:
        """Return the provider of the type inference for the given method."""
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
