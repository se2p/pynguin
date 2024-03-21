#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an adapter for the MutPy mutation testing framework."""
from __future__ import annotations

import importlib
import logging

from typing import TYPE_CHECKING

import pynguin.assertion.mutation_analysis.controller as mc
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.assertion.mutation_analysis.operators.loop as mol
import pynguin.assertion.mutation_analysis.stategies as ms
import pynguin.assertion.mutation_analysis.mutators as mu

import pynguin.configuration as config

from pynguin.utils.exceptions import ConfigurationException


if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
    from typing import ClassVar


_LOGGER = logging.getLogger(__name__)


class MutationAdapter:
    """Adapter class for interactions with the MutPy mutation testing framework."""

    _strategies: ClassVar[
        dict[config.MutationStrategy, Callable[[int], ms.HOMStrategy]]
    ] = {
        config.MutationStrategy.FIRST_TO_LAST: ms.FirstToLastHOMStrategy,
        config.MutationStrategy.BETWEEN_OPERATORS: ms.BetweenOperatorsHOMStrategy,
        config.MutationStrategy.RANDOM: ms.RandomHOMStrategy,
        config.MutationStrategy.EACH_CHOICE: ms.EachChoiceHOMStrategy,
    }

    def mutate_module(self) -> list[tuple[ModuleType, list[mo.Mutation]]]:
        """Mutates the modules specified in the configuration.

        Uses MutPy's mutation procedure.

        Returns:
            A list of tuples where the first entry is the mutated module and the second
            part is a list of all the mutations operators applied.
        """
        controller = self._build_mutation_controller()

        mutants = []

        target_module = importlib.import_module(config.configuration.module_name)

        _LOGGER.info("Build AST for %s", target_module.__name__)
        target_ast = controller.create_target_ast(target_module)
        _LOGGER.info("Mutate module %s", target_module.__name__)
        mutant_modules = controller.mutate_module(
            target_module=target_module,
            target_ast=target_ast,
        )

        for mutant_module, mutations in mutant_modules:
            mutants.append((mutant_module, mutations))

        _LOGGER.info("Generated %d mutants", len(mutants))
        return mutants

    def _build_mutation_controller(self) -> mc.MutationController:
        _LOGGER.info("Setup mutation controller")
        mutant_generator = self._get_mutant_generator()
        return mc.MutationController(mutant_generator)

    def _get_mutant_generator(self) -> mu.FirstOrderMutator:
        operators_set = set()
        operators_set |= mo.standard_operators
        operators_set |= mo.experimental_operators

        # percentage of the generated mutants (mutation sampling)
        percentage = 100

        mutation_strategy = config.configuration.test_case_output.mutation_strategy

        if mutation_strategy == config.MutationStrategy.FIRST_ORDER_MUTANTS:
            return mu.FirstOrderMutator(operators_set, percentage)

        order = config.configuration.test_case_output.mutation_order
        if order <= 0:
            raise ConfigurationException("Mutation order should be > 0.")

        if mutation_strategy in self._strategies:
            hom_strategy = self._strategies[mutation_strategy](order)
            return mu.HighOrderMutator(operators_set, percentage, hom_strategy)
        raise ConfigurationException("No suitable mutation strategy found.")
