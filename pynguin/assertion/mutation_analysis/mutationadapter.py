#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an adapter for the MutPy mutation testing framework."""
from __future__ import annotations

import logging
from types import ModuleType
from typing import Callable

import mutpy.controller as mc
import mutpy.operators as mo
import mutpy.operators.loop as mol
import mutpy.utils as mu
import mutpy.views as mv

import pynguin.configuration as config
from pynguin.utils.exceptions import ConfigurationException

_LOGGER = logging.getLogger(__name__)


class MutationAdapter:  # pylint: disable=too-few-public-methods
    """Adapter class for interactions with the MutPy mutation testing framework."""

    _strategies: dict[config.MutationStrategy, Callable[[int], mc.HOMStrategy]] = {
        config.MutationStrategy.FIRST_TO_LAST: mc.FirstToLastHOMStrategy,
        config.MutationStrategy.BETWEEN_OPERATORS: mc.BetweenOperatorsHOMStrategy,
        config.MutationStrategy.RANDOM: mc.RandomHOMStrategy,
        config.MutationStrategy.EACH_CHOICE: mc.EachChoiceHOMStrategy,
    }

    def __init__(self):
        self.target_loader: mu.ModulesLoader | None = None

    def mutate_module(self) -> list[tuple[ModuleType, list[mo.Mutation]]]:
        """Mutates the modules specified in the configuration by using MutPys'
        mutation procedure.

        Returns:
            A list of tuples where the first entry is the mutated module and the second
            part is a list of all the mutations operators applied.
        """
        controller = self._build_mutation_controller()
        controller.score = mc.MutationScore()

        mutants = []

        if self.target_loader is not None:
            for target_module, to_mutate in self.target_loader.load():
                _LOGGER.info("Build AST for %s", target_module.__name__)
                target_ast = controller.create_target_ast(target_module)
                _LOGGER.info("Mutate module %s", target_module.__name__)
                mutant_modules = controller.mutate_module(
                    target_module=target_module,
                    to_mutate=to_mutate,
                    target_ast=target_ast,
                )
                for mutant_module, mutations in mutant_modules:
                    mutants.append((mutant_module, mutations))
        _LOGGER.info("Generated %d mutants", len(mutants))
        return mutants

    def _build_mutation_controller(self) -> mc.MutationController:
        _LOGGER.info("Setup mutation controller")
        built_views = self._get_views()
        mutant_generator = self._get_mutant_generator()
        self.target_loader = mu.ModulesLoader(
            [config.configuration.module_name], config.configuration.project_path
        )

        return mc.MutationController(
            runner_cls=None,
            target_loader=self.target_loader,
            test_loader=None,
            views=built_views,
            mutant_generator=mutant_generator,
        )

    def _get_mutant_generator(self) -> mc.FirstOrderMutator:
        operators_set = set()
        operators_set |= mo.standard_operators

        # Only use a selected set of the experimental operators.
        operators_set |= {
            mol.OneIterationLoop,
            mol.ReverseIterationLoop,
            mol.ZeroIterationLoop,
        }

        # percentage of the generated mutants (mutation sampling)
        percentage = 100

        mutation_strategy = config.configuration.test_case_output.mutation_strategy

        if mutation_strategy == config.MutationStrategy.FIRST_ORDER_MUTANTS:
            return mc.FirstOrderMutator(operators_set, percentage)

        order = config.configuration.test_case_output.mutation_order
        if order <= 0:
            raise ConfigurationException("Mutation order should be > 0.")

        if mutation_strategy in self._strategies:
            hom_strategy = self._strategies[mutation_strategy](order)
            return mc.HighOrderMutator(operators_set, percentage, hom_strategy)
        raise ConfigurationException("No suitable mutation strategy found.")

    @staticmethod
    def _get_views() -> list[mv.QuietTextView]:
        # We do not want any output from MutPy here
        return [mv.QuietTextView()]
