#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tracks the lineages of LLM test cases injected into a search population.

Every injected test case starts a lineage. Each blended offspring of it starts a
sub-lineage with the same root, so that admission and survival can be counted per
injected test case and per blend channel. A chromosome carries its lineage id in
``TestCaseChromosome.lineage``, which survives cloning, mutation and crossover.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import TYPE_CHECKING

from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pynguin.ga.testcasechromosome as tcc


class BlendChannel(enum.Enum):
    """How a lineage member entered the population."""

    RAW = "raw"
    """The injected LLM test case itself."""

    GOAL_CROSSOVER = "goal_crossover"
    """Crossover with the population member closest to the injected test's goal."""

    MUTANT = "mutant"
    """Mutation of the injected test case."""

    TOURNAMENT_CROSSOVER = "tournament_crossover"
    """Crossover with a partner picked by the selection operator."""


BLEND_CHANNELS: tuple[BlendChannel, ...] = (
    BlendChannel.GOAL_CROSSOVER,
    BlendChannel.MUTANT,
    BlendChannel.TOURNAMENT_CROSSOVER,
)

_BLEND_VARIABLES: dict[BlendChannel, tuple[RuntimeVariable, RuntimeVariable, RuntimeVariable]] = {
    BlendChannel.GOAL_CROSSOVER: (
        RuntimeVariable.LLMBlendGoalCrossoverBred,
        RuntimeVariable.LLMBlendGoalCrossoverAdmitted,
        RuntimeVariable.LLMBlendGoalCrossoverSurvived,
    ),
    BlendChannel.MUTANT: (
        RuntimeVariable.LLMBlendMutantBred,
        RuntimeVariable.LLMBlendMutantAdmitted,
        RuntimeVariable.LLMBlendMutantSurvived,
    ),
    BlendChannel.TOURNAMENT_CROSSOVER: (
        RuntimeVariable.LLMBlendTournamentCrossoverBred,
        RuntimeVariable.LLMBlendTournamentCrossoverAdmitted,
        RuntimeVariable.LLMBlendTournamentCrossoverSurvived,
    ),
}


@dataclasses.dataclass
class LineageRecord:
    """A lineage started by an injected test case or one of its blended offspring."""

    root: int
    """The lineage id of the injected test case this lineage stems from."""

    channel: BlendChannel
    """How the lineage's first member was created."""

    generation: int
    """The generation in which the lineage's first member was created."""

    admitted: bool | None = None
    """Whether a member was in the population after the first selection that followed
    the lineage's creation; None until that selection happened."""


class LineageTracker:
    """Assigns lineage ids and keeps the bookkeeping for injected LLM test cases.

    The tracker only reads and writes lineage ids; it never draws random numbers, so
    it does not change the search.
    """

    def __init__(self) -> None:  # noqa: D107
        self._records: dict[int, LineageRecord] = {}
        self.reinsertions = 0

    def inject(self, chromosome: tcc.TestCaseChromosome, generation: int) -> int:
        """Starts a new lineage for an injected test case.

        Args:
            chromosome: The injected test case.
            generation: The current generation.

        Returns:
            The new lineage id, which is also stored in the chromosome.
        """
        lineage = len(self._records)
        self._records[lineage] = LineageRecord(lineage, BlendChannel.RAW, generation)
        chromosome.lineage = lineage
        return lineage

    def derive(
        self,
        offspring: tcc.TestCaseChromosome,
        root: int,
        channel: BlendChannel,
        generation: int,
    ) -> int:
        """Starts a sub-lineage for an offspring blended from an injected test case.

        Args:
            offspring: The blended offspring.
            root: The lineage id of the injected test case.
            channel: The blend channel that bred the offspring.
            generation: The current generation.

        Returns:
            The new lineage id, which is also stored in the offspring.
        """
        lineage = len(self._records)
        self._records[lineage] = LineageRecord(root, channel, generation)
        offspring.lineage = lineage
        return lineage

    def root_of(self, chromosome: tcc.TestCaseChromosome) -> int | None:
        """Returns the id of the injected test case a chromosome descends from.

        Args:
            chromosome: The chromosome.

        Returns:
            The root lineage id, or None if the chromosome has no injected ancestor.
        """
        record = self._records.get(chromosome.lineage)  # type: ignore[arg-type]
        return None if record is None else record.root

    def roots_in(self, chromosomes: Iterable[tcc.TestCaseChromosome]) -> set[int]:
        """Returns the injected test cases that have a member among the chromosomes.

        Args:
            chromosomes: The chromosomes to look at.

        Returns:
            The root lineage ids present among the chromosomes.
        """
        roots = (self.root_of(chromosome) for chromosome in chromosomes)
        return {root for root in roots if root is not None}

    def observe(self, population: Iterable[tcc.TestCaseChromosome]) -> None:
        """Records admission after a selection step.

        Every lineage that was created before this selection and has not been
        observed yet counts as admitted if one of its members is in the population.

        Args:
            population: The population after selection.
        """
        present = {chromosome.lineage for chromosome in population}
        for lineage, record in self._records.items():
            if record.admitted is None:
                record.admitted = lineage in present

    def young_roots(self, generation: int, max_age: int) -> list[int]:
        """Returns the injected test cases younger than a number of generations.

        Args:
            generation: The current generation.
            max_age: The number of generations a lineage counts as young.

        Returns:
            The root lineage ids, oldest first.
        """
        return [
            lineage
            for lineage, record in self._records.items()
            if record.channel is BlendChannel.RAW and generation - record.generation < max_age
        ]

    def statistics(
        self, population: Iterable[tcc.TestCaseChromosome]
    ) -> dict[RuntimeVariable, int]:
        """Summarises injection, admission and survival.

        Args:
            population: The final population.

        Returns:
            The value of each lineage output variable.
        """
        present = {chromosome.lineage for chromosome in population}
        surviving_roots = {
            record.root for lineage, record in self._records.items() if lineage in present
        }
        admitted_roots = {record.root for record in self._records.values() if record.admitted}
        injected = [
            lineage
            for lineage, record in self._records.items()
            if record.channel is BlendChannel.RAW
        ]
        values = {
            RuntimeVariable.LLMInjectedTests: len(injected),
            RuntimeVariable.LLMInjectedAdmitted: len(admitted_roots),
            RuntimeVariable.LLMInjectedSurvived: len(surviving_roots),
            RuntimeVariable.LLMLineageElitismReinsertions: self.reinsertions,
        }
        for channel, (bred, admitted, survived) in _BLEND_VARIABLES.items():
            lineages = [
                lineage for lineage, record in self._records.items() if record.channel is channel
            ]
            values[bred] = len(lineages)
            values[admitted] = sum(1 for lineage in lineages if self._records[lineage].admitted)
            values[survived] = sum(1 for lineage in lineages if lineage in present)
        return values
