#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating tests for a module."""

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.request import RenderedRequest
from pynguin.large_language_model.targets import TargetDiagnosis, describe
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
        *,
        diagnostics: dict[GenericCallableAccessibleObject, TargetDiagnosis] | None = None,
        visibility_instructions: str = "",
        tests_per_query: int = 0,
    ):
        """Initializes the prompt.

        Args:
            callables (list[GenericCallableAccessibleObject]): List of
                uncovered callables.
            module_path (str): Path to the module.
            module_code (str): Source code of the module.
            diagnostics (dict): Optional per-callable diagnosis: the uncovered lines
                and branch outcomes, and hints on why the callable is uncovered (e.g.
                never reached, one-sided branch).
            visibility_instructions: Optional prose describing which members of
                the module the generated tests may call (see
                ``llmagent.get_visibility_instructions``).
            tests_per_query: How many test functions to ask for; 0 asks for no
                particular number.
        """
        self.callables: list[GenericCallableAccessibleObject] = callables
        self.module_path = module_path
        self.module_code = module_code
        self.diagnostics: dict[GenericCallableAccessibleObject, TargetDiagnosis] = diagnostics or {}
        self.visibility_instructions = visibility_instructions
        self.tests_per_query = tests_per_query
        super().__init__()

    def _template_vars(self) -> list[str]:
        return [
            "uncovered_targets",
            "module_code",
            "module_path",
            "visibility_instructions",
            "tests_per_query",
        ]

    def build_callables_prompt_section(self) -> list[str]:
        """Generates one entry per callable: its header and what is uncovered in it.

        Returns:
            list[str]: Per callable, its header with signature, followed by one
            indented line per uncovered-goal list and hint.
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

            diagnosis = self.diagnostics.get(gao)
            if diagnosis:
                callable_list_item += "".join(f"\n  - {line}" for line in describe(diagnosis))

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
            visibility_instructions=self.visibility_instructions,
            tests_per_query=self.tests_per_query,
        )
