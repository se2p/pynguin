#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a controller for generating mutants."""

from __future__ import annotations

import ast
import logging

from typing import TYPE_CHECKING

from pynguin.assertion.mutation_analysis.transformer import create_module


if TYPE_CHECKING:
    import types

    from collections.abc import Generator
    from types import ModuleType

    import pynguin.assertion.mutation_analysis.mutators as mu

    from pynguin.assertion.mutation_analysis.operators.base import Mutation


_LOGGER = logging.getLogger(__name__)


class MutationController:
    """A controller that creates mutants."""

    def __init__(
        self,
        mutant_generator: mu.Mutator,
        module_ast: ast.Module,
        module: types.ModuleType,
    ) -> None:
        """Initialize the controller.

        Args:
            mutant_generator: The mutant generator to use.
            module_ast: The AST of the module to mutate.
            module: The module to mutate.
        """
        self._mutant_generator = mutant_generator
        self._module_ast = module_ast
        self._module = module

    def create_mutant(self, mutant_ast: ast.Module) -> ModuleType:
        """Creates a mutant of the module.

        Args:
            mutant_ast: The mutant AST.

        Returns:
            The created mutant module.
        """
        return create_module(mutant_ast, self._module.__name__)

    def create_mutants(
        self,
    ) -> Generator[tuple[ModuleType | None, list[Mutation]]]:
        """Creates mutants for the module.

        Returns:
            A generator of tuples where the first entry is the mutated module or None
            if the mutated module cannot be created and the second part is a list of
            all the mutations operators applied.
        """
        for mutations, mutant_ast in self._mutant_generator.mutate(self._module_ast, self._module):
            assert isinstance(mutant_ast, ast.Module)

            try:
                mutant_module = self.create_mutant(mutant_ast)
            except Exception as exception:  # noqa: BLE001
                _LOGGER.debug("Error creating mutant: %s", exception)
                mutant_module = None
            except SystemExit as exception:
                _LOGGER.debug("Caught SystemExit during mutant creation/execution: %s", exception)
                mutant_module = None

            yield mutant_module, mutations

    def mutant_count(self) -> int:
        """Calculates the number of mutants that can be created.

        Returns:
            The number of mutants that can be created.
        """
        return sum(1 for _ in self._mutant_generator.mutate(self._module_ast, self._module))
