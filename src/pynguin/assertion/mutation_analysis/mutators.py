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
import abc
import types

from typing import Generator

from pynguin.assertion.mutation_analysis import utils
from pynguin.assertion.mutation_analysis.operators.base import Mutation, MutationOperator
from pynguin.assertion.mutation_analysis.stategies import HOMStrategy, FirstToLastHOMStrategy


class Mutator(abc.ABC):
        @abc.abstractmethod
        def mutate(
            self,
            target_ast: ast.AST,
            module: types.ModuleType | None = None,
        ) -> Generator[tuple[list[Mutation], ast.AST], None, None]:
            """Mutate the given AST.

            Args:
                target_ast: The AST to mutate.
                module: The module to mutate.

            Returns:
                A generator of mutations and the mutated AST.
            """


class FirstOrderMutator(Mutator):

    def __init__(self, operators: list[type[MutationOperator]], percentage: int = 100) -> None:
        self.operators = operators
        self.sampler = utils.RandomSampler(percentage)

    def mutate(
        self,
        target_ast: ast.AST,
        module: types.ModuleType | None = None,
    ) -> Generator[tuple[list[Mutation], ast.Module], None, None]:
        for op in self.operators:
            for mutation, mutant in op().mutate(target_ast, self.sampler, module=module):
                yield [mutation], mutant


class HighOrderMutator(FirstOrderMutator):

    def __init__(
        self,
        operators: list[type[MutationOperator]],
        percentage: int = 100,
        hom_strategy: HOMStrategy | None = None,
    ) -> None:
        super().__init__(operators, percentage)
        self.hom_strategy = hom_strategy or FirstToLastHOMStrategy()

    def mutate(
        self,
        target_ast: ast.AST,
        module: types.ModuleType | None = None,
    ) -> Generator[tuple[list[Mutation], ast.AST], None, None]:
        mutations = self.generate_all_mutations(module, target_ast)
        for mutations_to_apply in self.hom_strategy.generate(mutations):
            generators = []
            applied_mutations = []
            mutant = target_ast
            for mutation in mutations_to_apply:
                generator = mutation.operator().mutate(
                    mutant,
                    sampler=self.sampler,
                    module=module,
                    only_mutation=mutation,
                )
                try:
                    new_mutation, mutant = generator.__next__()
                except StopIteration:
                    assert False, 'no mutations!'
                applied_mutations.append(new_mutation)
                generators.append(generator)
            yield applied_mutations, mutant
            self.finish_generators(generators)

    def generate_all_mutations(
        self,
        module: types.ModuleType | None,
        target_ast: ast.AST,
    ) -> list[Mutation]:
        mutations: list[Mutation] = []
        for op in self.operators:
            for mutation, _ in op().mutate(target_ast, None, module=module):
                mutations.append(mutation)
        return mutations

    def finish_generators(self, generators: list[Generator]) -> None:
        for generator in reversed(generators):
            try:
                generator.__next__()
            except StopIteration:
                continue
            assert False, 'too many mutations!'
