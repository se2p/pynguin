# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Implements type inference strategies."""

from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import date
import inspect
import json
import logging
import os
import textwrap

from pydantic import SecretStr

from pynguin.analyses.module import CallableData, TestCluster
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericCallableAccessibleObject,
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

    def __init__(self, test_cluster: TestCluster, provider: LLMProvider) -> None:
        """Initialise the strategy with a reference to the test cluster and an LLM."""
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
        prompts = self._build_prompt_map()
        inferences: OrderedDict[GenericCallableAccessibleObject, dict[str, str]] = OrderedDict()
        for call in prompts:
            res = self._send_prompt(prompts[call])
            inferences[call] = json.JSONDecoder().decode(res)
        _LOGGER.debug("inferred: %s", inferences)

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

    def _build_user_prompt(self, src_code: str, class_module_name: str) -> str:
        return _USER_PROMPT_TEMPLATE.format(
            _ROLE_USER=_ROLE_USER,
            module=class_module_name,
            src=src_code.rstrip(),
        )

    def _build_prompt(self, src_code: str, class_module_name: str) -> str:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(src_code, class_module_name)
        return f"{system_prompt}\n{user_prompt}"

    def _send_prompt(self, prompt: str) -> str:
        res = self._model.chat(prompt)
        _LOGGER.debug("LLM responded with: %s", res)
        return res

    def _build_prompt_map(self) -> OrderedDict[GenericCallableAccessibleObject, str]:
        """Return an *OrderedDict* {callable ➔ prompt} for the whole cluster."""
        prompts: OrderedDict[GenericCallableAccessibleObject, str] = OrderedDict()
        for callable_obj in self._test_cluster.function_data_for_accessibles:
            try:
                src_code = self._get_src_code(callable_obj)
                src_module = self._get_src_class_module(callable_obj)
                prompt = self._build_prompt(src_code, src_module)
            except Exception as exc:
                _LOGGER.warning("Skipping %s - unable to build prompt: %s", callable_obj, exc)
                continue
            prompts[callable_obj] = prompt
        return prompts
