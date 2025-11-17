#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutating ASTs.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/controller.py
and integrated in Pynguin.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from pynguin.assertion.mutation_analysis.strategies import FirstToLastHOMStrategy, HOMStrategy

if TYPE_CHECKING:
    import ast
    import types
    from collections.abc import Generator

    from pynguin.assertion.mutation_analysis.operators.base import Mutation, MutationOperator


class Mutator(abc.ABC):
    """A mutator is responsible for mutating an AST."""

    @abc.abstractmethod
    def mutate(
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> Generator[tuple[list[Mutation], ast.AST]]:
        """Mutate the given AST.

        Args:
            target_ast: The AST to mutate.
            module: The module to mutate.

        Yields:
            A generator of mutations and the mutated AST.
        """


class FirstOrderMutator(Mutator):
    """A mutator that applies first order mutations."""

    def __init__(self, operators: list[type[MutationOperator]]) -> None:
        """Initialize the mutator.

        Args:
            operators: The operators to use for mutation.
        """
        self.operators = operators

    def mutate(  # noqa: D102
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> Generator[tuple[list[Mutation], ast.AST]]:
        for op in self.operators:
            for mutation, mutant in op.mutate(target_ast, module):
                yield [mutation], mutant


class HighOrderMutator(FirstOrderMutator):
    """A mutator that applies high order mutations."""

    def __init__(
        self,
        operators: list[type[MutationOperator]],
        hom_strategy: HOMStrategy | None = None,
    ) -> None:
        """Initialize the mutator.

        Args:
            operators: The operators to use for mutation.
            hom_strategy: The strategy to use for higher order mutations.
        """
        super().__init__(operators)
        self.hom_strategy = hom_strategy or FirstToLastHOMStrategy()

    def mutate(  # noqa: D102
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> Generator[tuple[list[Mutation], ast.AST]]:
        mutations = self._generate_all_mutations(module, target_ast)
        for mutations_to_apply in self.hom_strategy.generate(mutations):
            generators = []
            applied_mutations = []
            mutant = target_ast
            for mutation in mutations_to_apply:
                generator = mutation.operator.mutate(mutant, module, mutation)
                next_value = next(generator, None)
                assert next_value is not None
                new_mutation, mutant = next_value
                applied_mutations.append(new_mutation)
                generators.append(generator)
            yield applied_mutations, mutant
            self._finish_generators(generators)

    def _generate_all_mutations(
        self,
        module: types.ModuleType,
        target_ast: ast.AST,
    ) -> list[Mutation]:
        mutations: list[Mutation] = []
        for op in self.operators:
            for mutation, _ in op.mutate(target_ast, module):
                mutations.append(mutation)
        return mutations

    @staticmethod
    def _finish_generators(generators: list[Generator]) -> None:
        for generator in reversed(generators):
            value = next(generator, None)
            assert value is None, "too many mutations!"
