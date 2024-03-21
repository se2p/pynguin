#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/controller.py.
"""
from __future__ import annotations

import ast
import inspect
import types

from typing import Generator

from pynguin.assertion.mutation_analysis import utils
from pynguin.assertion.mutation_analysis.operators.base import Mutation
from pynguin.assertion.mutation_analysis.mutators import Mutator


class MutationController:

    def __init__(self, mutant_generator: Mutator) -> None:
        self.mutant_generator = mutant_generator

    def mutate_module(
        self,
        target_module: types.ModuleType,
        target_ast: ast.AST,
    ) -> Generator[tuple[types.ModuleType | None, list[Mutation]], None, None]:
        for mutations, mutant_ast in self.mutant_generator.mutate(
            target_ast,
            module=target_module,
        ):
            yield self.create_mutant_module(target_module, mutant_ast), mutations

    def create_target_ast(self, target_module: types.ModuleType) -> ast.AST:
        target_source_code = inspect.getsource(target_module)
        return utils.create_ast(target_source_code)

    def create_mutant_module(self, target_module: types.ModuleType, mutant_ast: ast.Module) -> types.ModuleType | None:
        try:
            return utils.create_module(
                ast_node=mutant_ast,
                module_name=target_module.__name__
            )
        except BaseException:
            return None
