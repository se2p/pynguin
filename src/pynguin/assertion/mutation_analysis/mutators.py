#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutating ASTs.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/controller.py
and integrated in Pynguin.
"""

from __future__ import annotations

import abc
import itertools
from typing import TYPE_CHECKING

from pynguin.assertion.mutation_analysis.operators.loop import (
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
)
from pynguin.assertion.mutation_analysis.strategies import FirstToLastHOMStrategy, HOMStrategy
from pynguin.utils import randomness

if TYPE_CHECKING:
    import ast
    import types
    from collections.abc import Generator

    from pynguin.assertion.mutation_analysis.operators.base import Mutation, MutationOperator


# Operators whose mutations frequently turn terminating loops into non-terminating
# ones. When a bound on the mutation-analysis phase is active, these are scheduled
# last so a time budget cuts the expensive timeout tail first.
_TIMEOUT_PRONE_OPERATORS: frozenset[type[MutationOperator]] = frozenset({
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
})


def _round_robin(lists: list[list[Mutation]]) -> list[Mutation]:
    """Interleave several lists of mutations round-robin.

    Truncating a concatenation of per-operator mutation lists starves the
    operators near the end of the list. Interleaving keeps the operator mix
    representative under truncation.

    Args:
        lists: One mutation list per operator.

    Returns:
        The interleaved mutations.
    """
    result: list[Mutation] = []
    for group in itertools.zip_longest(*lists):
        result.extend(mutation for mutation in group if mutation is not None)
    return result


def _stratified_counts(sizes: list[int], cap: int) -> list[int]:
    """Distribute a cap over strata proportional to their sizes.

    Uses largest-remainder rounding so the counts sum to exactly ``cap`` (or to
    the total if the total is already below the cap).

    Args:
        sizes: The number of mutations available per operator.
        cap: The maximum total number of mutations to keep.

    Returns:
        The number of mutations to keep per operator, summing to
        ``min(cap, sum(sizes))``.
    """
    total = sum(sizes)
    if total <= cap:
        return list(sizes)
    exact = [size * cap / total for size in sizes]
    counts = [int(value) for value in exact]
    remainder = cap - sum(counts)
    order = sorted(range(len(sizes)), key=lambda i: exact[i] - counts[i], reverse=True)
    for i in order[:remainder]:
        counts[i] += 1
    return counts


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

    def mutation_count(
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> int:
        """Count the mutations the module yields before any truncation.

        Args:
            target_ast: The AST to mutate.
            module: The module to mutate.

        Returns:
            The pre-truncation number of mutations.
        """
        return sum(1 for _ in self.mutate(target_ast, module))


class FirstOrderMutator(Mutator):
    """A mutator that applies first order mutations."""

    def __init__(
        self,
        operators: list[type[MutationOperator]],
        *,
        maximum_mutants: int = -1,
        sampling_seed: int = 0,
        reorder: bool = False,
    ) -> None:
        """Initialize the mutator.

        Args:
            operators: The operators to use for mutation.
            maximum_mutants: If >= 0, keep at most this many mutants using a
                seeded, per-operator stratified sample (-1 = keep all).
            sampling_seed: Seed for the deterministic sampling.
            reorder: If True, interleave mutations by operator (round-robin) and
                schedule timeout-prone operators last, so a truncating bound cuts
                the expensive tail first while keeping the operator mix
                representative. When False and ``maximum_mutants`` is -1, the
                historical concatenated-operator-order behavior is preserved.
        """
        self.operators = operators
        self._maximum_mutants = maximum_mutants
        self._sampling_seed = sampling_seed
        self._reorder = reorder

    def mutate(  # noqa: D102
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> Generator[tuple[list[Mutation], ast.AST]]:
        if not self._reorder and self._maximum_mutants < 0:
            # Preserve the historical behavior: yield mutations in concatenated
            # operator-list order without sampling.
            for op in self.operators:
                for mutation, mutant in op.mutate(target_ast, module):
                    yield [mutation], mutant
            return

        for mutation in self._select_mutations(target_ast, module):
            generator = mutation.operator.mutate(target_ast, module, mutation)
            next_value = next(generator, None)
            assert next_value is not None, "Selected mutation could not be regenerated"
            new_mutation, mutant = next_value
            yield [new_mutation], mutant
            # Exhaust the generator so the operator restores the (shared) AST
            # before the next mutation is applied.
            assert next(generator, None) is None, "Mutation operator yielded more than once"

    def mutation_count(  # noqa: D102
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> int:
        # Pre-truncation total: every possible first-order mutation, ignoring any
        # sampling cap, so NumberOfCreatedMutants reflects the true module size.
        return sum(1 for op in self.operators for _ in op.mutate(target_ast, module))

    def _select_mutations(
        self,
        target_ast: ast.AST,
        module: types.ModuleType,
    ) -> list[Mutation]:
        """Enumerate, optionally sample, and order the mutations.

        Only the (cheap) mutation descriptors are enumerated here; the mutant
        modules themselves are created lazily by the caller.

        Args:
            target_ast: The AST to mutate.
            module: The module to mutate.

        Returns:
            The selected mutations in execution order.
        """
        per_operator: list[tuple[type[MutationOperator], list[Mutation]]] = [
            (op, [mutation for mutation, _ in op.mutate(target_ast, module)])
            for op in self.operators
        ]

        total = sum(len(mutations) for _, mutations in per_operator)
        if self._maximum_mutants >= 0 and total > self._maximum_mutants:
            per_operator = self._sample(per_operator)

        regular = [
            mutations for op, mutations in per_operator if op not in _TIMEOUT_PRONE_OPERATORS
        ]
        deferred = [mutations for op, mutations in per_operator if op in _TIMEOUT_PRONE_OPERATORS]
        return _round_robin(regular) + _round_robin(deferred)

    def _sample(
        self,
        per_operator: list[tuple[type[MutationOperator], list[Mutation]]],
    ) -> list[tuple[type[MutationOperator], list[Mutation]]]:
        rng = randomness.Random(self._sampling_seed)
        counts = _stratified_counts(
            [len(mutations) for _, mutations in per_operator],
            self._maximum_mutants,
        )
        sampled: list[tuple[type[MutationOperator], list[Mutation]]] = []
        for (op, mutations), keep in zip(per_operator, counts, strict=True):
            if keep >= len(mutations):
                sampled.append((op, list(mutations)))
            else:
                indices = sorted(rng.sample(range(len(mutations)), keep))
                sampled.append((op, [mutations[i] for i in indices]))
        return sampled


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
