#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating tests for a module."""

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod


class UncoveredTargetsPrompt(Prompt):
    """Implementation prompt for generating tests for a module."""

    def __init__(
        self,
        callables: list[GenericCallableAccessibleObject],
        module_code: str,
        module_path: str,
    ):
        """Initializes the prompt.

        Args:
            callables (list[GenericCallableAccessibleObject]): List of
             uncovered callables.
            module_path (str): Path to the module.
            module_code (str): Source code of the module.
        """
        super().__init__(module_code, module_path)
        self.callables: list[GenericCallableAccessibleObject] = callables
        self.module_path = module_path
        self.module_code = module_code

    def build_callables_prompt_section(self) -> list[str]:
        """Generates a list of function headers and their signatures.

        Returns:
            list[str]: A list of formatted function headers with their signatures.
        """
        function_headers = []

        for gao in self.callables:
            signature = str(gao.inferred_signature)
            if gao.is_method() and isinstance(gao, GenericMethod):
                method_gao: GenericMethod = gao
                function_header = (
                    f"- The method {method_gao.method_name} of class"
                    f" {method_gao.owner.name}{signature}"
                )
            elif gao.is_function() and isinstance(gao, GenericFunction):
                fn_gao: GenericFunction = gao
                function_header = f"- The function {fn_gao.function_name}{signature}"
            elif gao.is_constructor() and isinstance(gao, GenericConstructor):
                constructor_gao: GenericConstructor = gao
                class_name = constructor_gao.owner.name  # type:ignore[union-attr]
                function_header = (
                    f"- The constructor of the class {class_name} {signature}"
                )
            else:
                continue  # Skip unknown callable types

            function_headers.append(function_header)

        return function_headers

    def build_prompt(self) -> str:
        """Builds prompt message."""
        function_headers = self.build_callables_prompt_section()
        callables_section = "\n".join(function_headers)

        return f"""You are a Python developer tasked with writing unit tests
         for a the following callables that Pynguin failed to cover:
            {callables_section}
        Source code:
        `{self.module_code}`
            """
