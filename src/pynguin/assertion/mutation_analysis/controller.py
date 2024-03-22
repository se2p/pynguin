#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an adapter for the MutPy mutation testing framework."""
from __future__ import annotations

import ast
import importlib
import inspect
import logging
import types

from typing import TYPE_CHECKING

import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.assertion.mutation_analysis.stategies as ms
import pynguin.configuration as config

from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.utils.exceptions import ConfigurationException


if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
    from typing import ClassVar

    from pynguin.assertion.mutation_analysis.operators.base import Mutation
    from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


_LOGGER = logging.getLogger(__name__)


class MutationController:
    """Adapter class for interactions with the MutPy mutation testing framework."""

    _strategies: ClassVar[
        dict[config.MutationStrategy, Callable[[int], ms.HOMStrategy]]
    ] = {
        config.MutationStrategy.FIRST_TO_LAST: ms.FirstToLastHOMStrategy,
        config.MutationStrategy.BETWEEN_OPERATORS: ms.BetweenOperatorsHOMStrategy,
        config.MutationStrategy.RANDOM: ms.RandomHOMStrategy,
        config.MutationStrategy.EACH_CHOICE: ms.EachChoiceHOMStrategy,
    }

    def mutate_module(self) -> list[tuple[ModuleType, list[Mutation]]]:
        """Mutates the modules specified in the configuration.

        Returns:
            A list of tuples where the first entry is the mutated module and the second
            part is a list of all the mutations operators applied.
        """
        _LOGGER.info("Setup mutation generator")
        mutant_generator = self._get_mutant_generator()

        _LOGGER.info("Import module %s", config.configuration.module_name)
        target_module = importlib.import_module(config.configuration.module_name)

        _LOGGER.info("Build AST for %s", target_module.__name__)
        target_source_code = inspect.getsource(target_module)
        target_ast = ParentNodeTransformer.create_ast(target_source_code)

        _LOGGER.info("Mutate module %s", target_module.__name__)
        mutants = self.create_mutants(mutant_generator, target_ast, target_module)

        _LOGGER.info("Generated %d mutants", len(mutants))
        return mutants

    def create_mutants(
        self,
        mutant_generator: mu.FirstOrderMutator,
        target_ast: ast.Module,
        target_module: types.ModuleType,
    ) -> list[tuple[ModuleType, list[Mutation]]]:
        """Creates mutants for the given module.

        Args:
            mutant_generator: The mutant generator.
            target_ast: The AST of the target module.
            target_module: The target module.

        Returns:
            A list of tuples where the first entry is the mutated module and the second
            part is a list of all the mutations operators applied.
        """
        mutants: list[tuple[ModuleType, list[Mutation]]] = []

        for mutations, mutant_ast in mutant_generator.mutate(target_ast, target_module):
            assert isinstance(mutant_ast, ast.Module)

            try:
                mutant_module = self.create_module(mutant_ast, target_module.__name__)
            except Exception as exception:  # noqa: BLE001
                _LOGGER.debug("Error creating mutant: %s", exception)
                continue

            mutants.append((mutant_module, mutations))

        return mutants

    def create_module(self, ast_node: ast.Module, module_name: str) -> types.ModuleType:
        """Creates a module from an AST node.

        Args:
            ast_node: The AST node.
            module_name: The name of the module.

        Returns:
            The created module.
        """
        code = compile(ast_node, module_name, "exec")
        module = types.ModuleType(module_name)
        exec(code, module.__dict__)  # noqa: S102
        return module

    def _get_mutant_generator(self) -> mu.FirstOrderMutator:
        operators: list[type[MutationOperator]] = [
            *mo.standard_operators,
            *mo.experimental_operators,
        ]

        mutation_strategy = config.configuration.test_case_output.mutation_strategy

        if mutation_strategy == config.MutationStrategy.FIRST_ORDER_MUTANTS:
            return mu.FirstOrderMutator(operators)

        order = config.configuration.test_case_output.mutation_order

        if order <= 0:
            raise ConfigurationException("Mutation order should be > 0.")

        if mutation_strategy in self._strategies:
            hom_strategy = self._strategies[mutation_strategy](order)
            return mu.HighOrderMutator(operators, hom_strategy=hom_strategy)

        raise ConfigurationException("No suitable mutation strategy found.")
