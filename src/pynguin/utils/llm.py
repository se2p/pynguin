#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a basic API to communicate with LLMs."""

from __future__ import annotations

import abc
import enum
import logging
import os
import re
import typing


if typing.TYPE_CHECKING:
    from collections.abc import Iterable


try:
    import openai

    from openai.types.chat import ChatCompletionAssistantMessageParam
    from openai.types.chat import ChatCompletionDeveloperMessageParam
    from openai.types.chat import ChatCompletionFunctionMessageParam
    from openai.types.chat import ChatCompletionSystemMessageParam
    from openai.types.chat import ChatCompletionToolMessageParam
    from openai.types.chat import ChatCompletionUserMessageParam
    from pydantic import SecretStr

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


class LLMProvider(str, enum.Enum):
    """An enum for the available LLM service providers."""

    OPENAI = "openai"


class LLM(abc.ABC):
    """An abstract interface for LLM communications."""

    def __init__(self, api_key: SecretStr, temperature: float, system_prompt: str) -> None:
        """Initialises the LLM communication interface.

        Args:
            api_key: the API key to authenticate with the LLM
            temperature: the temperature setting for the LLM
            system_prompt: the system prompt for the LLM
        """
        self._api_key = api_key
        self._temperature = temperature
        self._system_prompt = system_prompt

    @abc.abstractmethod
    def chat(self, prompt: str, system_prompt: str | None = None) -> str | None:
        """Sends a message to the LLM and returns its raw answer.

        Args:
            prompt: the (user) prompt send to the LLM
            system_prompt: the system prompt send to the LLM, if empty use the one from the
                           constructor of this class.

        Returns:
            The raw answer from the LLM or None
        """

    @classmethod
    def create(cls, provider: LLMProvider) -> LLM:
        """Creates the LLM communication interface based on the given provider.

        Args:
            provider: the provider of the LLM

        Returns:
            The concrete LLM communication interface
        """
        match provider:
            case LLMProvider.OPENAI:
                if not OPENAI_AVAILABLE:
                    raise ValueError(
                        "OpenAI API library is not available. You can install it with poetry "
                        "install --with openai."
                    )
                return OpenAI()
            case _:
                raise NotImplementedError(f"Unknown provider {provider}")


def extract_code(llm_response: str) -> str:
    """Takes the response from the LLM and attempts to extract the answer.

    Args:
        llm_response: the response from the LLM

    Returns:
        the extracted answer, i.e., the extracted pytest code
    """
    md_source_block_pattern = r"^```(?:\w+)?\s*\n(.*?)(?=^```)```"
    result = re.findall(md_source_block_pattern, llm_response, re.DOTALL | re.MULTILINE)
    return "\n".join(result)


if OPENAI_AVAILABLE:
    OPENAI_SYSTEM_PROMPT = """You are a senior level Python developer with a focus on testing
    with the pytest framework. Provide the generated tests in the style of the pytest framework.
    Provide the generated tests inside a Markdown-style code block."""
    OPENAI_API_KEY = SecretStr(os.environ.get("OPENAI_API_KEY", ""))

    MessageTypes: typing.TypeAlias = (
        ChatCompletionDeveloperMessageParam
        | ChatCompletionSystemMessageParam
        | ChatCompletionUserMessageParam
        | ChatCompletionAssistantMessageParam
        | ChatCompletionToolMessageParam
        | ChatCompletionFunctionMessageParam
    )

    class OpenAI(LLM):
        """An interface for communication with OpenAI."""

        def __init__(  # noqa: D107
            self,
            api_key: SecretStr = OPENAI_API_KEY,
            temperature: float = 0.2,
            system_prompt: str = OPENAI_SYSTEM_PROMPT,
            model: str = "gpt-4o",
        ) -> None:
            if not api_key:
                raise AssertionError(
                    "OpenAI API key not set, provide via the OPENAI_API_KEY environment variable."
                )
            super().__init__(api_key, temperature, system_prompt)
            self.__client = openai.OpenAI(api_key=api_key.get_secret_value())
            self.__model = model

        def chat(self, prompt: str, system_prompt: str | None = None) -> str | None:  # noqa: D102
            if not system_prompt:
                system_prompt = self._system_prompt

            messages: Iterable[MessageTypes] = [
                ChatCompletionDeveloperMessageParam(content=system_prompt, role="developer"),
                ChatCompletionUserMessageParam(content=prompt, role="user"),
            ]
            try:
                response = self.__client.chat.completions.create(
                    messages=messages,
                    model=self.__model,
                )
                return response.choices[0].message.content
            except openai.OpenAIError as e:
                LOGGER.exception(e)
            return None
