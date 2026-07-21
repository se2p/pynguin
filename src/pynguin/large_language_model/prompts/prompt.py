# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

"""Base class and utilities for Jinja2 template prompt configurations."""

from __future__ import annotations

import abc
import pathlib

import jinja2
import jinja2.meta

import pynguin.configuration as config
from pynguin.large_language_model.config_schema import PromptConfig
from pynguin.large_language_model.request import RenderedRequest

RESOURCES_DIR = pathlib.Path(__file__).parent / "resources"


def load_yaml_config(name: str) -> dict:
    """Loads a YAML file from the resources directory.

    Args:
        name: The base name of the YAML file.

    Returns:
        The configuration dictionary.
    """
    import yaml  # noqa: PLC0415

    path = RESOURCES_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content if isinstance(content, dict) else {}
    except Exception as exc:
        raise ValueError(f"Failed to load prompt config {path}: {exc}") from exc


class Prompt(abc.ABC):
    """Base LLM prompt class using Jinja2 templates and YAML configuration."""

    _resource_name: str | None = None

    def __init__(self) -> None:
        """Initializes the prompt by loading its YAML configuration."""
        defaults = load_yaml_config("defaults")
        specific = load_yaml_config(self._resource_name) if self._resource_name else {}

        # Merge, allowing specific to override defaults
        merged = {**defaults, **specific}
        self._config = PromptConfig.from_dict(merged)

        # Load-time validation of template variables
        self._validate_template_variables()

    @property
    def system_message(self) -> str:
        """Returns the system message template."""
        return (self._config.system_message or "").strip()

    @abc.abstractmethod
    def _template_vars(self) -> list[str]:
        """Declares the variables expected by the Jinja2 templates.

        Returns:
            A list of variable names.
        """

    def _validate_template_variables(self) -> None:
        """Asserts that template variables match declared variables."""
        env = jinja2.Environment()  # noqa: S701
        referenced = set()

        if self._config.user_message_template:
            ast = env.parse(self._config.user_message_template)
            referenced.update(jinja2.meta.find_undeclared_variables(ast))

        if self._config.system_message:
            ast = env.parse(self._config.system_message)
            referenced.update(jinja2.meta.find_undeclared_variables(ast))

        declared = set(self._template_vars())
        if referenced != declared:
            raise ValueError(
                f"Mismatch in {self.__class__.__name__}: "
                f"referenced template variables {referenced} do not match "
                f"declared variables {declared}"
            )

    def render(self, **kwargs) -> RenderedRequest:
        """Renders the templates with the provided variables.

        Args:
            **kwargs: Template variables matching _template_vars.

        Returns:
            The rendered RenderedRequest object.
        """
        declared = set(self._template_vars())
        provided = set(kwargs.keys())
        if declared != provided:
            raise ValueError(
                f"Provided variables {provided} do not match declared variables {declared}"
            )

        # Set up Jinja2 environment with StrictUndefined
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)  # noqa: S701

        user_content = ""
        if self._config.user_message_template:
            template = env.from_string(self._config.user_message_template)
            user_content = template.render(**kwargs).strip()

        system_content = ""
        if self._config.system_message:
            template = env.from_string(self._config.system_message)
            system_content = template.render(**kwargs).strip()

        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        if user_content:
            messages.append({"role": "user", "content": user_content})

        # Single source of truth:
        # - model comes ONLY from the run configuration.
        # - temperature / max_tokens / stop come ONLY from the per-prompt YAML.
        model = config.configuration.large_language_model.model_name

        temperature = self._config.temperature
        if temperature is None:
            raise ValueError("Prompt YAML must define 'temperature' (defaults.yaml provides it).")

        return RenderedRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=self._config.max_tokens,
            stop=self._config.stop,
        )

    def render_request(self) -> RenderedRequest:
        """Builds the fully-rendered request for this prompt.

        Subclasses override this to supply their template variables.

        Returns:
            The rendered request ready to send to the LLM.

        Raises:
            NotImplementedError: If the subclass does not implement it.
        """
        raise NotImplementedError

    def build_prompt(self) -> str:
        """Returns the user-message content of the rendered request.

        Returns:
            The rendered user prompt message.
        """
        return self.render_request().messages[-1]["content"]
