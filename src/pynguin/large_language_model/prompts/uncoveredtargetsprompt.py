#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating tests for a module."""

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.request import RenderedRequest
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)


class UncoveredTargetsPrompt(Prompt):
    """Implementation prompt for generating tests for a module."""

    _resource_name = "uncovered_targets"

    def __init__(
        self,
        callables: list[GenericCallableAccessibleObject],
        module_code: str,
        module_path: str,
        diagnostics: dict[GenericCallableAccessibleObject, str] | None = None,
    ):
        """Initializes the prompt.

        Args:
            callables (list[GenericCallableAccessibleObject]): List of
                uncovered callables.
            module_path (str): Path to the module.
            module_code (str): Source code of the module.
            diagnostics (dict): Optional per-callable diagnostic hints describing why
                a target is uncovered (e.g. never reached, one-sided branch). Used to
                give the LLM a targeted "problem card" per callable.
        """
        self.callables: list[GenericCallableAccessibleObject] = callables
        self.module_path = module_path
        self.module_code = module_code
        self.diagnostics: dict[GenericCallableAccessibleObject, str] = diagnostics or {}
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["uncovered_targets", "module_code", "module_path"]

    def build_callables_prompt_section(self) -> list[str]:
        """Generates a list of function headers and their signatures.

        Returns:
            list[str]: A list of formatted function headers with their signatures.
        """
        callables_list = []

        for gao in self.callables:
            signature = str(gao.inferred_signature)
            if gao.is_method() and isinstance(gao, GenericMethod):
                method_gao: GenericMethod = gao
                callable_list_item = (
                    f"- The method {method_gao.method_name} of class "
                    f"{method_gao.owner.name}{signature}"
                )
            elif gao.is_function() and isinstance(gao, GenericFunction):
                fn_gao: GenericFunction = gao
                callable_list_item = f"- The function {fn_gao.function_name}{signature}"
            elif gao.is_constructor() and isinstance(gao, GenericConstructor):
                constructor_gao: GenericConstructor = gao
                class_name = constructor_gao.owner.name  # type: ignore[union-attr]
                callable_list_item = f"- The constructor of the class {class_name}{signature}"
            else:
                continue  # Skip unknown callable types

            diagnostic = self.diagnostics.get(gao)
            if diagnostic:
                callable_list_item += f" [hint: {diagnostic}]"

            callables_list.append(callable_list_item)

        return callables_list

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        callables_list = self.build_callables_prompt_section()
        return self.render(
            uncovered_targets=callables_list,
            module_code=self.module_code,
            module_path=self.module_path,
        )
