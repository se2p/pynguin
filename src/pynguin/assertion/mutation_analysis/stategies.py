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

import random

from typing import Generator, Callable

from pynguin.assertion.mutation_analysis.operators.base import Mutation


def remove_bad_mutations(
    mutations_to_apply: list[Mutation],
    available_mutations: list[Mutation],
    allow_same_operators: bool = True
) -> None:
    for mutation_to_apply in mutations_to_apply:
        for available_mutation in available_mutations.copy():
            if (
                mutation_to_apply.node == available_mutation.node
                or mutation_to_apply.node in getattr(available_mutation.node, "children")
                or available_mutation.node in getattr(mutation_to_apply.node, "children")
                or (
                    not allow_same_operators
                    and mutation_to_apply.operator == available_mutation.operator
                )
            ):
                available_mutations.remove(available_mutation)


class HOMStrategy:

    def __init__(self, order: int = 2) -> None:
        self.order = order


class FirstToLastHOMStrategy(HOMStrategy):

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        mutations = mutations.copy()
        while mutations:
            mutations_to_apply: list[Mutation] = []
            index = 0
            available_mutations = mutations.copy()
            while len(mutations_to_apply) < self.order and available_mutations:
                mutation = available_mutations.pop(index)
                mutations_to_apply.append(mutation)
                mutations.remove(mutation)
                index = 0 if index == -1 else -1
                remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply


class EachChoiceHOMStrategy(HOMStrategy):

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        mutations = mutations.copy()
        while mutations:
            mutations_to_apply: list[Mutation] = []
            available_mutations = mutations.copy()
            while len(mutations_to_apply) < self.order and available_mutations:
                mutation = available_mutations.pop(0)
                mutations_to_apply.append(mutation)
                mutations.remove(mutation)
                remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply


class BetweenOperatorsHOMStrategy(HOMStrategy):

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        usage = {mutation: 0 for mutation in mutations}
        not_used = mutations.copy()
        while not_used:
            mutations_to_apply: list[Mutation] = []
            available_mutations = mutations.copy()
            available_mutations.sort(key=lambda x: usage[x])
            while len(mutations_to_apply) < self.order and available_mutations:
                mutation = available_mutations.pop(0)
                mutations_to_apply.append(mutation)
                if usage[mutation] == 0:
                    not_used.remove(mutation)
                usage[mutation] += 1
                remove_bad_mutations(mutations_to_apply, available_mutations, allow_same_operators=False)
            yield mutations_to_apply


class RandomHOMStrategy(HOMStrategy):

    def __init__(self, order: int = 2, shuffler: Callable = random.shuffle) -> None:
        super().__init__(order)
        self.shuffler = shuffler

    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation], None, None]:
        mutations = mutations.copy()
        self.shuffler(mutations)
        while mutations:
            mutations_to_apply: list[Mutation] = []
            available_mutations = mutations.copy()
            while len(mutations_to_apply) < self.order and available_mutations:
                mutation = available_mutations.pop(0)
                mutations_to_apply.append(mutation)
                mutations.remove(mutation)
                remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply
