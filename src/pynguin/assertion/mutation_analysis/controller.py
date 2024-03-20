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
import random
import types

from typing import Generator, Callable

from pynguin.assertion.mutation_analysis import utils
from pynguin.assertion.mutation_analysis.operators.base import Mutation, MutationOperator


class MutationController:

    def __init__(self, target_loader: utils.ModulesLoader, mutant_generator: FirstOrderMutator) -> None:
        self.target_loader = target_loader
        self.mutant_generator = mutant_generator

    def mutate_module(
        self,
        target_module: types.ModuleType,
        to_mutate: str | None,
        target_ast: ast.AST,
    ) -> Generator[tuple[types.ModuleType | None, list[Mutation]], None, None]:
        for mutations, mutant_ast in self.mutant_generator.mutate(
            target_ast,
            to_mutate,
            module=target_module,
        ):
            yield self.create_mutant_module(target_module, mutant_ast), mutations

    def create_target_ast(self, target_module: types.ModuleType) -> ast.AST:
        with open(target_module.__file__) as target_file:
            return utils.create_ast(target_file.read())

    def create_mutant_module(self, target_module: types.ModuleType, mutant_ast: ast.Module) -> types.ModuleType | None:
        try:
            return utils.create_module(
                ast_node=mutant_ast,
                module_name=target_module.__name__
            )
        except BaseException:
            return None


class HOMStrategy:

    def __init__(self, order: int = 2) -> None:
        self.order = order

    def remove_bad_mutations(
        self,
        mutations_to_apply: list[Mutation],
        available_mutations: list[Mutation],
        allow_same_operators: bool = True
    ) -> None:
        for mutation_to_apply in mutations_to_apply:
            for available_mutation in available_mutations[:]:
                if mutation_to_apply.node == available_mutation.node or \
                        mutation_to_apply.node in available_mutation.node.children or \
                        available_mutation.node in mutation_to_apply.node.children or \
                        (not allow_same_operators and mutation_to_apply.operator == available_mutation.operator):
                    available_mutations.remove(available_mutation)


class FirstToLastHOMStrategy(HOMStrategy):
    name = 'FIRST_TO_LAST'

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        mutations = mutations[:]
        while mutations:
            mutations_to_apply: list[Mutation] = []
            index = 0
            available_mutations = mutations[:]
            while len(mutations_to_apply) < self.order and available_mutations:
                try:
                    mutation = available_mutations.pop(index)
                    mutations_to_apply.append(mutation)
                    mutations.remove(mutation)
                    index = 0 if index == -1 else -1
                except IndexError:
                    break
                self.remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply


class EachChoiceHOMStrategy(HOMStrategy):
    name = 'EACH_CHOICE'

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        mutations = mutations[:]
        while mutations:
            mutations_to_apply: list[Mutation] = []
            available_mutations = mutations[:]
            while len(mutations_to_apply) < self.order and available_mutations:
                try:
                    mutation = available_mutations.pop(0)
                    mutations_to_apply.append(mutation)
                    mutations.remove(mutation)
                except IndexError:
                    break
                self.remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply


class BetweenOperatorsHOMStrategy(HOMStrategy):
    name = 'BETWEEN_OPERATORS'

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        usage = {mutation: 0 for mutation in mutations}
        not_used = mutations[:]
        while not_used:
            mutations_to_apply: list[Mutation] = []
            available_mutations = mutations[:]
            available_mutations.sort(key=lambda x: usage[x])
            while len(mutations_to_apply) < self.order and available_mutations:
                mutation = available_mutations.pop(0)
                mutations_to_apply.append(mutation)
                if not usage[mutation]:
                    not_used.remove(mutation)
                usage[mutation] += 1
                self.remove_bad_mutations(mutations_to_apply, available_mutations, allow_same_operators=False)
            yield mutations_to_apply


class RandomHOMStrategy(HOMStrategy):
    name = 'RANDOM'

    def __init__(self, order: int = 2, shuffler: Callable = random.shuffle) -> None:
        super().__init__(order)
        self.shuffler = shuffler

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        mutations = mutations[:]
        self.shuffler(mutations)
        while mutations:
            mutations_to_apply = []
            available_mutations = mutations[:]
            while len(mutations_to_apply) < self.order and available_mutations:
                try:
                    mutation = available_mutations.pop(0)
                    mutations_to_apply.append(mutation)
                    mutations.remove(mutation)
                except IndexError:
                    break
                self.remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply


hom_strategies = [
    BetweenOperatorsHOMStrategy,
    EachChoiceHOMStrategy,
    FirstToLastHOMStrategy,
    RandomHOMStrategy,
]


class FirstOrderMutator:

    def __init__(self, operators: list[type[MutationOperator]], percentage: int = 100) -> None:
        self.operators = operators
        self.sampler = utils.RandomSampler(percentage)

    def mutate(
        self,
        target_ast: ast.AST,
        to_mutate: str | None = None,
        module: types.ModuleType | None = None,
    ) -> Generator[tuple[list[Mutation], ast.Module], None, None]:
        for op in utils.sort_operators(self.operators):
            for mutation, mutant in op().mutate(target_ast, to_mutate, self.sampler, module=module):
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
        to_mutate: str | None = None,
        module: types.ModuleType | None = None,
    ) -> Generator[tuple[list[Mutation], ast.AST], None, None]:
        mutations = self.generate_all_mutations(module, target_ast, to_mutate)
        for mutations_to_apply in self.hom_strategy.generate(mutations):
            generators = []
            applied_mutations = []
            mutant = target_ast
            for mutation in mutations_to_apply:
                generator = mutation.operator().mutate(
                    mutant,
                    to_mutate=to_mutate,
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
        to_mutate: str | None,
    ) -> list[Mutation]:
        mutations: list[Mutation] = []
        for op in utils.sort_operators(self.operators):
            for mutation, _ in op().mutate(target_ast, to_mutate, None, module=module):
                mutations.append(mutation)
        return mutations

    def finish_generators(self, generators: list[Generator]) -> None:
        for generator in reversed(generators):
            try:
                generator.__next__()
            except StopIteration:
                continue
            assert False, 'too many mutations!'
