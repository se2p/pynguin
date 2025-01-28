#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides strategies for higher order mutations.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/controller.py
and integrated in Pynguin.
"""

from __future__ import annotations

import abc

from typing import TYPE_CHECKING

from pynguin.utils import randomness


if TYPE_CHECKING:
    from collections.abc import Generator

    from pynguin.assertion.mutation_analysis.operators.base import Mutation


def remove_bad_mutations(
    mutations_to_apply: list[Mutation],
    available_mutations: list[Mutation],
    allow_same_operators: bool = True,  # noqa: FBT001, FBT002
) -> None:
    """Remove bad mutations from the available mutations.

    Args:
        mutations_to_apply: The mutations that are already selected.
        available_mutations: The mutations that are available.
        allow_same_operators: Whether the same operator should be allowed.

    Returns:
        The list of available mutations without the bad mutations.
    """
    for mutation_to_apply in mutations_to_apply:
        for available_mutation in available_mutations.copy():
            if (
                mutation_to_apply.node == available_mutation.node
                or mutation_to_apply.node in available_mutation.node.children  # type: ignore[attr-defined]
                or available_mutation.node in mutation_to_apply.node.children  # type: ignore[attr-defined]
                or (
                    not allow_same_operators
                    and mutation_to_apply.operator == available_mutation.operator
                )
            ):
                available_mutations.remove(available_mutation)


class HOMStrategy(abc.ABC):
    """A strategy for higher order mutations."""

    def __init__(self, order: int = 2) -> None:
        """Initialize the strategy.

        Args:
            order: The order of the mutations.
        """
        self.order = order

    @abc.abstractmethod
    def generate(self, mutations: list[Mutation]) -> Generator[list[Mutation]]:
        """Generate the mutations.

        Args:
            mutations: The mutations to generate from.

        Returns:
            A generator for the mutations.
        """


class FirstToLastHOMStrategy(HOMStrategy):
    """A strategy that selects the first mutation and then the last one."""

    def generate(  # noqa: D102
        self, mutations: list[Mutation]
    ) -> Generator[list[Mutation]]:
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
    """A strategy that selects the mutations in order."""

    def generate(  # noqa: D102
        self, mutations: list[Mutation]
    ) -> Generator[list[Mutation]]:
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
    """A strategy that selects mutations between different operators."""

    def generate(  # noqa: D102
        self, mutations: list[Mutation]
    ) -> Generator[list[Mutation]]:
        usage = dict.fromkeys(mutations, 0)
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
                remove_bad_mutations(
                    mutations_to_apply, available_mutations, allow_same_operators=False
                )
            yield mutations_to_apply


class RandomHOMStrategy(HOMStrategy):
    """A strategy that selects mutations randomly."""

    def __init__(self, order: int = 2) -> None:
        """Initialize the strategy.

        Args:
            order: The order of the mutations.
        """
        super().__init__(order)

    def generate(  # noqa: D102
        self, mutations: list[Mutation]
    ) -> Generator[list[Mutation]]:
        mutations = mutations.copy()
        randomness.RNG.shuffle(mutations)
        while mutations:
            mutations_to_apply: list[Mutation] = []
            available_mutations = mutations.copy()
            while len(mutations_to_apply) < self.order and available_mutations:
                mutation = available_mutations.pop(0)
                mutations_to_apply.append(mutation)
                mutations.remove(mutation)
                remove_bad_mutations(mutations_to_apply, available_mutations)
            yield mutations_to_apply
