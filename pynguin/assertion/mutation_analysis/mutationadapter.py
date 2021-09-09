#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an adapter for the MutPy mutation testing framework."""
from types import ModuleType
from typing import List, Optional, Tuple

import mutpy.controller as mc
import mutpy.operators as mo
import mutpy.utils as mu
import mutpy.views as mv

import pynguin.configuration as config


class MutationAdapter:  # pylint: disable=too-few-public-methods
    """ "Adapter class for interactions with the MutPy mutation testing framework."""

    def __init__(self):
        self.target_loader: Optional[mu.ModulesLoader] = None

    def mutate_module(self) -> List[Tuple[ModuleType, List[mo.Mutation]]]:
        """ "Mutates the modules specified in the configuration by using MutPys'
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
                target_ast = controller.create_target_ast(target_module)
                mutant_modules = controller.mutate_module(
                    target_module=target_module,
                    to_mutate=to_mutate,
                    target_ast=target_ast,
                )
                for mutant_module, mutations in mutant_modules:
                    mutants.append((mutant_module, mutations))
        return mutants

    def _build_mutation_controller(self) -> mc.MutationController:
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

    @staticmethod
    def _get_mutant_generator() -> mc.FirstOrderMutator:
        operators_set = set()
        # TODO(fs) Some of these mess up everything
        # operators_set |= mo.experimental_operators
        operators_set |= mo.standard_operators

        # percentage of the generated mutants (mutation sampling)
        percentage = 100

        # TODO(fs) Add HOM strategies later on
        return mc.FirstOrderMutator(operators_set, percentage)

    @staticmethod
    def _get_views() -> List[mv.QuietTextView]:
        # We do not want any output from MutPy here
        return [mv.QuietTextView()]
