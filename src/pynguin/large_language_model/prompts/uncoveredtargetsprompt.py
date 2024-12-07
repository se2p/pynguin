#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating tests for a module."""
from typing import List

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject, GenericMethod, \
    GenericFunction, GenericConstructor


class UncoveredTargetsPrompt(Prompt):
    """Implementation prompt for generating tests for a module."""

    def __init__(self, callables: list[GenericCallableAccessibleObject], module_code: str, module_path: str):
        """
        Initializes the prompt with uncovered callables, module path, and module code.

        Args:
            callables (list[GenericCallableAccessibleObject]): List of uncovered callables.
            module_path (str): Path to the module.
            module_code (str): Source code of the module.
        """
        super().__init__(module_code, module_path)
        self.callables: list[GenericCallableAccessibleObject] = callables
        self.module_path = module_path
        self.module_code = module_code

    def build_callables_prompt_section(self) -> list[str]:
        """
        Generates a list of function headers and their signatures for the uncovered callables.

        Returns:
            list[str]: A list of formatted function headers with their signatures.
        """
        function_headers = []

        for gao in self.callables:
            signature = str(gao.inferred_signature)  # Get the inferred signature as a string
            if gao.is_method():
                method_gao: GenericMethod = gao
                function_header = (
                    f"- The method {method_gao.method_name} of class {method_gao.owner.__name__}{signature}"
                )
            elif gao.is_function():
                fn_gao: GenericFunction = gao
                function_header = (
                    f"- The function {fn_gao.function_name}{signature}"
                )
            elif gao.is_constructor():
                constructor_gao: GenericConstructor = gao
                class_name = constructor_gao.owner.name
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
