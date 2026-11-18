#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides a prompt that asks the LLM to repair its previous answer in the same chat."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from pynguin.large_language_model.prompts.prompt import Prompt

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


class ConversationRepairPrompt(Prompt):
    """Continues a conversation with the error that the previous response caused.

    The rendered request repeats the previous request's messages, adds the previous
    response as the assistant's turn, and appends a user message describing the
    error.  Model and sampling settings are those of the previous request.
    """

    _resource_name = "conversation_repair"

    def __init__(
        self,
        previous_prompt: Prompt,
        previous_response: str,
        error_message: str,
    ):
        """Creates a new prompt.

        Args:
            previous_prompt: The prompt whose response is to be repaired; it may itself
                be a repair prompt, so repeated repairs extend one conversation.
            previous_response: The response to be repaired.
            error_message: Why the response could not be used.
        """
        self.previous_prompt = previous_prompt
        self.previous_response = previous_response
        self.error_message = error_message
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["error_message"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        previous_request = self.previous_prompt.render_request()
        follow_up = self.render(error_message=self.error_message).messages[-1]
        return dataclasses.replace(
            previous_request,
            messages=[
                *previous_request.messages,
                {"role": "assistant", "content": self.previous_response},
                {"role": "user", "content": follow_up["content"]},
            ],
        )
