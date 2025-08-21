# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Implements type inference strategies."""

from abc import ABC, abstractmethod
import asyncio
import builtins
from collections import OrderedDict
from datetime import date
import importlib
import inspect
import json
import logging
import os
import textwrap
import time
from types import ModuleType
from typing import Any, TypeAlias
import typing

from pydantic import SecretStr
import pynguin.configuration as config

from pynguin.analyses.module import CallableData, TestCluster
from pynguin.analyses.typesystem import ANY, NONE_TYPE, UNSUPPORTED, InferredSignature, ProperType
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
    TypesOfCallables,
)
from pynguin.utils.llm import LLM, LLMProvider, OpenAI


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
    # Module and Class: {module}
    # Defined types: {types}

    ```python
    {src}
    ```

    Infer the parameter and return types now.
    """
).lstrip()

OPENAI_API_KEY = SecretStr(os.environ.get("OPENAI_API_KEY", ""))
TEMPERATURE = 0.2
MODEL = "gpt-4.1-nano-2025-04-14"


class InferenceStrategy(ABC):
    """Abstract base class for all inference strategies that modify the test cluster with inferred types."""

    def __init__(self, test_cluster: TestCluster) -> None:
        """Initialise the strategy with a reference to the test cluster."""
        self._test_cluster = test_cluster

    @abstractmethod
    def infer_types(self) -> None:
        """Perform type inference and update the test cluster accordingly."""


class LLMInference(InferenceStrategy):
    """LLM based type inference strategy for a testcluster."""

    def __init__(
        self, test_cluster: TestCluster, provider: LLMProvider, max_parallel_calls: int = 20
    ) -> None:
        """Initialise the strategy with a reference to the test cluster and an LLM."""
        self._max_parallel_calls = max_parallel_calls
        match provider:
            case LLMProvider.OPENAI:
                self._model = OpenAI(
                    OPENAI_API_KEY, TEMPERATURE, self._build_system_prompt(), MODEL
                )
            case _:
                raise NotImplementedError(f"Unknown provider {provider}")
        super().__init__(test_cluster)

    def infer_types(self) -> None:
        """Enriches the testcluster with type information using an LLM."""
        start = time.time()
        prompts = self._build_prompt_map()
        inferences = self._send_prompts(prompts)
        bench = time.time() - start
        _LOGGER.debug("in time: %s", bench)
        _LOGGER.debug("inferred: %s", inferences)
        for call in inferences:
            self._feed_into_test_cluster(inferences, call)
        _LOGGER.debug("resulting cluster: %s", self._test_cluster)

    def _feed_into_test_cluster(self, inferences, call):
        test_cluster_accessible = self._test_cluster.function_data_for_accessibles[call].accessible
        test_cluster_callable: GenericCallableAccessibleObject = test_cluster_accessible
        method_inference = json.loads(inferences[call])
        parameters: dict[str, ProperType] = {}
        parameters_for_statistics: dict[str, ProperType] = {}
        return_type: ProperType
        return_type_for_statistics: ProperType
        for key in method_inference:
            if key == "return":
                return_type = self._convert_type_hint_str(method_inference[key])
                return_type_for_statistics = self._convert_type_hint_str(
                    method_inference[key], unsupported=UNSUPPORTED
                )
                continue
            parameters[key] = self._convert_type_hint_str(method_inference[key])
            parameters_for_statistics[key] = self._convert_type_hint_str(
                method_inference[key], unsupported=UNSUPPORTED
            )
        inferred_signature: InferredSignature = InferredSignature(
            signature=test_cluster_callable.inferred_signature.signature,
            original_parameters=parameters,
            original_return_type=return_type,
            type_system=test_cluster_callable.inferred_signature.type_system,
            parameters_for_statistics=parameters_for_statistics,
            return_type_for_statistics=return_type_for_statistics,
        )
        if test_cluster_accessible.is_constructor():
            self._test_cluster.function_data_for_accessibles[call].accessible = GenericConstructor(
                test_cluster_callable.owner, inferred_signature
            )

        if test_cluster_accessible.is_classmethod() | test_cluster_accessible.is_method():
            test_cluster_method: GenericMethod = test_cluster_callable
            self._test_cluster.function_data_for_accessibles[call].accessible = GenericMethod(
                test_cluster_method.owner,
                test_cluster_method.callable,
                inferred_signature,
            )

        if test_cluster_accessible.is_function():
            self._test_cluster.function_data_for_accessibles[call].accessible = GenericFunction(
                test_cluster_callable.callable, inferred_signature
            )

    InferenceMap: TypeAlias = OrderedDict[GenericCallableAccessibleObject, str]

    def _get_src_code(self, accessible: GenericCallableAccessibleObject) -> str:
        call = accessible.callable
        try:
            src_code = inspect.getsource(call)
        except (OSError, TypeError):
            _LOGGER.error(
                "Failed to retrieve source code for accessible",
            )
            return ""
        return src_code

    def _get_src_class_module(self, accessible: GenericCallableAccessibleObject):
        return accessible.owner.full_name

    def _build_system_prompt(self) -> str:
        """Return the system-level instructions for the LLM."""
        today = date.today().isoformat()
        header = f"{_ROLE_SYSTEM}\n## Static-Analysis Instructions ({today})"
        return f"{header}\n{_SYS_GUIDELINES}"

    def _build_user_prompt(self, src_code: str, class_module_name: str, usable_types: str) -> str:
        return _USER_PROMPT_TEMPLATE.format(
            _ROLE_USER=_ROLE_USER,
            module=class_module_name,
            types=usable_types,
            src=src_code.rstrip(),
        )

    def _build_prompt(self, src_code: str, class_module_name: str, usable_types: list[str]) -> str:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(src_code, class_module_name, usable_types)
        return f"{system_prompt}\n{user_prompt}"

    def _send_prompt(self, prompt: str) -> str:
        res = self._model.chat(prompt)
        _LOGGER.debug("LLM responded with: %s", res)
        return res

    def _build_prompt_map(self) -> OrderedDict[GenericCallableAccessibleObject, str]:
        """Return an *OrderedDict* {callable -> prompt} for the whole cluster."""
        prompts: OrderedDict[GenericCallableAccessibleObject, str] = OrderedDict()
        for callable_obj in self._test_cluster.function_data_for_accessibles:
            try:
                src_code = self._get_src_code(callable_obj)
                src_module = self._get_src_class_module(callable_obj)
                src_usable_types: list[str] = [
                    t.full_name for t in self._test_cluster.type_system.get_all_types()
                ]
                prompt = self._build_prompt(src_code, src_module, src_usable_types)
            except Exception as exc:
                _LOGGER.warning("Skipping %s - unable to build prompt: %s", callable_obj, exc)
                continue
            prompts[callable_obj] = prompt
        return prompts

    def _send_prompts(
        self,
        prompts: dict[GenericCallableAccessibleObject, str],
    ) -> InferenceMap:
        """Return {callable -> raw LLM response}, sending prompts in parallel."""
        coro = self._gather_prompts_async(prompts)
        return self._run_coro(coro)

    async def _gather_prompts_async(
        self,
        prompts: dict[GenericCallableAccessibleObject, str],
    ) -> InferenceMap:
        sem = asyncio.Semaphore(self._max_parallel_calls)
        tasks = [
            asyncio.create_task(self._prompt_worker(acc, prompt, sem))
            for acc, prompt in prompts.items()
        ]

        results: dict[GenericCallableAccessibleObject, str] = OrderedDict()
        for task in asyncio.as_completed(tasks):
            try:
                acc, resp = await task
                results[acc] = resp
            except Exception as exc:  # noqa: PERF203
                _LOGGER.exception("Prompt for %s failed: %s", acc, exc)
        return OrderedDict((acc, results.get(acc, "")) for acc in prompts)

    async def _prompt_worker(
        self,
        acc: GenericCallableAccessibleObject,
        prompt: str,
        sem: asyncio.Semaphore,
    ) -> tuple[GenericCallableAccessibleObject, str]:
        async with sem:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, self._send_prompt, prompt)
            return acc, resp

    @staticmethod
    def _run_coro(coro: asyncio.coroutines.coroutine) -> Any:
        """Run *coro* no matter if an event loop is already running."""
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.get_running_loop()
            _LOGGER.debug("Using existing event loop (%s) for parallel LLM calls", loop)
            return loop.run_until_complete(coro)

    def _map_to_signature(
        self, inference: str
    ) -> dict[GenericCallableAccessibleObject, InferredSignature]:
        inf = json.loads(inference)
        params = {}
        for param in inf:
            if param == "return":
                return_type = self._resolve_type(inf[param])
            params[param] = self._test_cluster.type_system.convert_type_hint(
                self._resolve_type(inf[param])
            )
        _LOGGER.debug("resolved types: %s", params)

    _BUILTINS: dict[str, Any] = {  # noqa: RUF012
        t.__name__: t for t in vars(builtins).values() if isinstance(t, type)
    }

    _TYPING_GLOBALS: dict[str, Any] = {**vars(typing), **_BUILTINS, "None": type(None)}

    def _resolve_type(self, type_str: str) -> Any:
        """Best-effort conversion from *string* → *type object*."""
        # TODO: rethink/refactor this logic
        # 1. Explicit None
        if type_str == "None":
            return type(None)

        # 2. Plain built-in (int, float, list, …)
        builtin = self._BUILTINS.get(type_str)
        if builtin is not None:
            return builtin

        # 3. Parameterised typing expression, e.g. "list[int]"
        try:
            return eval(type_str, self._TYPING_GLOBALS)  # nosec B307 – controlled input
        except Exception:  # noqa: BLE001
            pass  # fall through to dotted-path import

        # 4. Dotted path to a user-defined class or alias
        try:
            module_path, attr_name = type_str.rsplit(".", 1)
            module: ModuleType = importlib.import_module(module_path)
            return getattr(module, attr_name)
        except Exception:  # noqa: BLE001
            # Last resort – unknown or ill-formed → Any
            return typing.Any

    def _convert_type_hint_str(self, hint_str: str, unsupported: ProperType = ANY) -> ProperType:
        """Like convert_type_hint, but takes the hint as a string.

        The string is evaluated (e.g. "int", "tuple[int, str]", "None") in a
        namespace containing builtins and typing symbols, and then passed
        to convert_type_hint.

        Args:
            hint_str: A string encoding of a Python type hint.
            unsupported: What to return if parsing or conversion fails.

        Returns:
            A ProperType, just like convert_type_hint would.
        """
        # Make best-effort parsing of LLM-provided type strings. We try the
        # following in order:
        #  - sanitize the string (strip markdown, quotes)
        #  - eval in a namespace that contains builtins, typing names and the
        #    module-under-test globals (so local classes resolve)
        #  - fallback to _resolve_type which handles dotted imports and typing eval
        # On any unrecoverable error, return the provided `unsupported` marker.
        # TODO: make custom types work (FibonacciHeapNode) more robustly.
        # Sanitize common LLM output artifacts
        if not isinstance(hint_str, str):
            return unsupported
        s = hint_str.strip()
        # remove markdown/code fences and backticks
        if s.startswith("```") and s.endswith("```"):
            # strip triple fences and optional leading language id
            inner = s.lstrip("`").rstrip("`")
            # remove leading language token like python
            inner = inner.split("\n", 1)[-1] if "\n" in inner else inner
            s = inner.strip()
        s = s.strip(' `"')

        # Build eval namespace with builtins and typing names
        namespace: dict[str, Any] = {
            **{k: getattr(builtins, k) for k in dir(builtins)},
            **{k: getattr(typing, k) for k in dir(typing)},
        }

        # Try to include the module-under-test globals so that local types
        # (declared in the SUT) can be resolved by name.
        try:
            module_name = getattr(config.configuration, "module_name", None)
            if module_name:
                try:
                    sut_mod = importlib.import_module(module_name)
                    # Import module dict but avoid private names
                    namespace.update({
                        k: v for k, v in sut_mod.__dict__.items() if not k.startswith("__")
                    })
                except Exception:
                    # ignore failures to import the module; we'll fallback later
                    _LOGGER.debug(
                        "Could not import module %s for eval namespace", module_name, exc_info=True
                    )
        except Exception:
            # If accessing configuration fails for any reason, continue without module globals
            _LOGGER.debug("Failed to enrich eval namespace with module globals", exc_info=True)

        # Try eval first (useful for expressions like 'list[int]' or 'Optional[int]').
        try:
            hint = eval(s, namespace)  # nosec B307 – controlled-ish input
        except Exception:
            # Fallback: try the resolver which handles dotted paths and other forms
            try:
                hint = self._resolve_type(s)
            except Exception:
                return unsupported

        try:
            return self._test_cluster.type_system.convert_type_hint(hint, unsupported=unsupported)
        except Exception:
            _LOGGER.debug("convert_type_hint failed for %s -> %s", s, hint, exc_info=True)
            return unsupported
