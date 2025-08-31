# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-License-Identifier: MIT
"""
Implements type inference strategies for a list of Python callables.

Design:
- An inference strategy is initialized with a list of `Callable` objects.
- During initialization, the strategy infers parameter and return types for all callables.
- `get_inference(callable)` returns a dict mapping parameter names to inferred types plus "return".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import builtins
from collections import OrderedDict
import datetime
import inspect
import json
import logging
import os
import textwrap
import time
import types
from typing import Any, Callable, Dict, Mapping, Sequence, get_type_hints
import typing

from pydantic import SecretStr
from pynguin.utils.llm import LLMProvider, OpenAI

_LOGGER = logging.getLogger(__name__)

_ROLE_SYSTEM = "<|system|>"
_ROLE_USER = "<|user|>"

_SYS_GUIDELINES = textwrap.dedent(
    """
    You are an expert Python static-analysis engine that follows PEP 484.

    **Chain of thought:** First think *step by step* to infer the most precise
    types. Keep the entire reasoning to yourself - do **not** reveal it.

    **Output format:** After you have finished thinking, output **only** a JSON
    object that maps every explicit parameter to its type and includes the key
    `"return"` for the return type.

      • Ignore the first positional parameter if it is named `"self"` or `"cls"`.
      • Prefer concrete types; fall back to `typing.Any` only if no better
        union or superclass exists.
      • Use fully-qualified names where helpful (e.g., `"pathlib.Path"`).
      • Do not emit extra prose, markdown, or comments - just the JSON.
    """
).strip()

_USER_PROMPT_TEMPLATE = textwrap.dedent(
    """
    {_ROLE_USER}
    # Module: {module}

    ```python
    {src}
    ```

    Infer the parameter and return types now.
    """
).lstrip()

OPENAI_API_KEY = SecretStr(os.environ.get("OPENAI_API_KEY", ""))
TEMPERATURE = 0.2
MODEL = "gpt-4.1-nano-2025-04-14"
ANY_STR = "typing.Any"


# =========
# Abstract strategy
# =========
class InferenceProvider(ABC):
    """Abstract base class for type inference strategies working on callables."""

    @abstractmethod
    def provide(self, method: Callable) -> dict[str, Any]:
        """Return the provider of the type inference for the given method."""


# =========
# LLM-backed implementation
# =========
class LLMInference(InferenceProvider):
    """LLM-based type inference strategy for plain Python callables."""

    def __init__(
        self,
        callables: Sequence[Callable[..., Any]],
        provider: LLMProvider,
        max_parallel_calls: int = 20,
    ) -> None:
        self._max_parallel_calls = max_parallel_calls
        self._types = types
        match provider:
            case LLMProvider.OPENAI:
                self._model = OpenAI(
                    OPENAI_API_KEY, TEMPERATURE, self._build_system_prompt(), MODEL
                )
            case _:
                raise NotImplementedError(f"Unknown provider {provider}")

        self._callables: list[Callable[..., Any]] = list(callables)
        self._inference_by_callable: OrderedDict[Callable, dict[str, str]] = OrderedDict()
        self._infer_all()

    def provide(self, method: Callable) -> dict[str, Any]:
        """Return the provider of the type inference for the given method."""
        return self._as_get_type_hints(self._inference_by_callable.get(method, {}))

    # ---- public API (inherited) ----
    def _infer_all(self) -> None:
        """Infer types for all callables in parallel at initialization time."""
        start = time.time()
        prompts = self._build_prompt_map(self._callables)
        raw = self._send_prompts(prompts)
        _LOGGER.debug("LLM raw responses collected for %d callables", len(raw))

        # Parse and store; fall back to annotations/Any on errors
        for func, response in raw.items():
            prior = self._prior_types(func)
            parsed = self._parse_json_response(response, prior)
            self._inference_by_callable[func] = parsed

        _LOGGER.debug("Inference completed in %.3fs", time.time() - start)

    # ---- prompt building ----
    def _build_system_prompt(self) -> str:
        today = datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()
        header = f"{_ROLE_SYSTEM}\n## Static-Analysis Instructions ({today})"
        return f"{header}\n{_SYS_GUIDELINES}"

    def _build_user_prompt(self, src_code: str, module_name: str) -> str:
        return _USER_PROMPT_TEMPLATE.format(
            _ROLE_USER=_ROLE_USER,
            module=module_name,
            src=src_code.rstrip(),
        )

    def _build_prompt(self, src_code: str, module_name: str) -> str:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(src_code, module_name)
        return f"{system_prompt}\n{user_prompt}"

    def _build_prompt_map(
        self, funcs: Sequence[Callable[..., Any]]
    ) -> OrderedDict[Callable[..., Any], str]:
        prompts: OrderedDict[Callable[..., Any], str] = OrderedDict()
        for func in funcs:
            try:
                src = self._get_src_code(func)
                module = getattr(func, "__module__", "<unknown>")
                prompt = self._build_prompt(src, module)
                prompts[func] = prompt
            except Exception as exc:  # noqa: PERF203
                _LOGGER.exception("Skipping callable %r due to prompt build failure: %s", func, exc)
        return prompts

    # ---- LLM I/O (parallel) ----
    def _send_prompt(self, prompt: str) -> str:
        res = self._model.chat(prompt)
        _LOGGER.debug("LLM responded with: %s", res)
        return res

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

        # Preserve original order and fill missing with empty string
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
            _LOGGER.debug("Using existing event loop (%s) for parallel LLM calls", loop)
            return loop.run_until_complete(coro)

    # ---- utilities ----
    def _get_src_code(self, func: Callable[..., Any]) -> str:
        try:
            return inspect.getsource(func)
        except (OSError, TypeError):  # builtins/lambdas/interactive objects
            # Try best-effort reconstruction
            name = getattr(func, "__qualname__", getattr(func, "__name__", "<callable>"))
            _LOGGER.warning("Falling back to signature-only prompt for %s", name)
            sig = self._safe_signature_str(func)
            return f"def {name}{sig}:\n    pass\n"

    def _safe_signature_str(self, func: Callable[..., Any]) -> str:
        try:
            sig = inspect.signature(func)
            return str(sig)
        except (TypeError, ValueError):
            return "( *args, **kwargs )"

    def _prior_types(self, func: Callable[..., Any]) -> Dict[str, str]:
        """Build a default type map from existing annotations/signature."""
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            # Unknown signature; provide generic params
            return {"*args": ANY_STR, "**kwargs": ANY_STR, "return": ANY_STR}

        result: Dict[str, str] = {}
        params = list(sig.parameters.values())

        for i, p in enumerate(params):
            # Ignore first param if named self/cls
            if i == 0 and p.name in {"self", "cls"}:
                continue
            ann = p.annotation
            if ann is inspect._empty:  # type: ignore[attr-defined]
                result[p.name] = ANY_STR
            else:
                result[p.name] = self._annotation_to_str(ann)

        # Return annotation
        if sig.return_annotation is inspect._empty:  # type: ignore[attr-defined]
            result["return"] = ANY_STR
        else:
            result["return"] = self._annotation_to_str(sig.return_annotation)

        return result

    def _annotation_to_str(self, ann: Any) -> str:
        try:
            # typing objects often have nice reprs; try to normalize into fully-qualified strings
            if getattr(ann, "__module__", "") and getattr(ann, "__qualname__", ""):
                return f"{ann.__module__}.{ann.__qualname__}"
            return str(ann)
        except Exception:
            return ANY_STR

    def _parse_json_response(self, response: str, prior: Dict[str, str]) -> Dict[str, str]:
        """Parse LLM JSON; on failure, return `prior` untouched."""
        if not response:
            return prior
        try:
            data = json.loads(response)
            if not isinstance(data, dict):
                return prior

            merged: Dict[str, str] = dict(prior)

            # parameters: copy across only known params; ignore "self"/"cls" (LLM is told to)
            for k in list(prior.keys()):
                if k == "return":
                    continue
                if k in data and isinstance(data[k], str) and data[k].strip():
                    merged[k] = data[k].strip()

            # return type
            if "return" in data and isinstance(data["return"], str) and data["return"].strip():
                merged["return"] = data["return"].strip()

            return merged
        except json.JSONDecodeError as exc:
            _LOGGER.debug("Failed to parse JSON response from LLM: %s", exc)
            return prior

    def _as_get_type_hints(
        self,
        mapping: dict[str, str],
        *,
        globalns: dict[str, Any] | None = None,
        localns: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert {'param': 'TypeExpr', 'return': 'TypeExpr'} -> {'param': <type>, 'return': <type>}.

        Behaves like typing.get_type_hints regarding evaluation and None handling.
        """
        # Build a safe, helpful eval namespace (no __import__ or builtins overrides).
        ns: dict[str, Any] = {}

        # Builtins (int, str, list, dict, etc.)
        ns.update(vars(builtins))
        ns["builtins"] = builtins  # allow 'builtins.int' etc.

        # typing names, both qualified (typing.X) and unqualified (X)
        ns["typing"] = typing
        for name in getattr(typing, "__all__", ()):
            ns[name] = getattr(typing, name)

        # Common stdlib packages often used in type strings (optional)
        import collections, collections.abc, datetime, pathlib  # noqa: F401

        ns["collections"] = collections
        ns["collections.abc"] = collections.abc
        ns["datetime"] = datetime
        ns["pathlib"] = pathlib

        # Handle None / NoneType like get_type_hints
        NONE_TYPE = getattr(
            types, "NoneType", type(None)
        )  # Python docs call this out. :contentReference[oaicite:1]{index=1}

        def _eval_type(txt: str) -> Any:
            t = (txt or "").strip().strip('"').strip("'")
            if t in {"None", "types.NoneType", "NoneType"}:
                return NONE_TYPE
            try:
                # Evaluate type expression (e.g., list[str], dict[str, int], Optional[int], "MyCls")
                return eval(t, {**ns, **(globalns or {})}, localns or {})
            except Exception:
                # Best-effort fallback: bare name present in ns? else Any.
                return ns.get(t, typing.Any)

        out: dict[str, Any] = {}
        for name, type_str in mapping.items():
            out[name] = _eval_type(type_str)

        # Match get_type_hints detail: ensure 'return' of 'None' is NoneType, not value None. :contentReference[oaicite:2]{index=2}
        if "return" in out and out["return"] is None:
            out["return"] = NONE_TYPE

        return out


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
