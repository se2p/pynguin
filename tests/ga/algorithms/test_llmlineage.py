#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.algorithms.llmlineage import BlendChannel, LineageTracker
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def _chromosome(lineage: int | None = None) -> tcc.TestCaseChromosome:
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.lineage = lineage
    return chromosome


@pytest.fixture
def tracker() -> LineageTracker:
    return LineageTracker()


def test_inject_and_derive_assign_fresh_ids(tracker):
    first, second, offspring = _chromosome(), _chromosome(), _chromosome()
    assert tracker.inject(first, 0) == 0
    assert tracker.inject(second, 0) == 1
    assert tracker.derive(offspring, 1, BlendChannel.MUTANT, 0) == 2
    assert (first.lineage, second.lineage, offspring.lineage) == (0, 1, 2)
    assert tracker.root_of(offspring) == 1


def test_root_of_unknown_lineage(tracker):
    assert tracker.root_of(_chromosome()) is None
    assert tracker.root_of(_chromosome(7)) is None


def test_roots_in(tracker):
    injected, offspring, other = _chromosome(), _chromosome(), _chromosome()
    tracker.inject(injected, 0)
    tracker.derive(offspring, 0, BlendChannel.MUTANT, 0)
    assert tracker.roots_in([offspring, other]) == {0}


def test_observe_only_sets_admission_once(tracker):
    injected = _chromosome()
    tracker.inject(injected, 0)
    tracker.observe([])
    tracker.observe([injected])
    assert tracker.statistics([])[RuntimeVariable.LLMInjectedAdmitted] == 0


def test_young_roots_only_injected_and_young(tracker):
    old, young, offspring = _chromosome(), _chromosome(), _chromosome()
    tracker.inject(old, 0)
    tracker.inject(young, 2)
    tracker.derive(offspring, 1, BlendChannel.MUTANT, 2)
    assert tracker.young_roots(3, 2) == [1]
    assert tracker.young_roots(3, 4) == [0, 1]


def test_statistics(tracker):
    injected = [_chromosome() for _ in range(3)]
    for chromosome in injected:
        tracker.inject(chromosome, 0)
    mutant, crossover = _chromosome(), _chromosome()
    tracker.derive(mutant, 1, BlendChannel.MUTANT, 0)
    tracker.derive(crossover, 2, BlendChannel.TOURNAMENT_CROSSOVER, 0)
    tracker.observe([injected[0], mutant, crossover])
    tracker.reinsertions = 2

    values = tracker.statistics([mutant])

    assert values[RuntimeVariable.LLMInjectedTests] == 3
    assert values[RuntimeVariable.LLMInjectedAdmitted] == 3
    assert values[RuntimeVariable.LLMInjectedSurvived] == 1
    assert values[RuntimeVariable.LLMLineageElitismReinsertions] == 2
    assert values[RuntimeVariable.LLMBlendMutantBred] == 1
    assert values[RuntimeVariable.LLMBlendMutantAdmitted] == 1
    assert values[RuntimeVariable.LLMBlendMutantSurvived] == 1
    assert values[RuntimeVariable.LLMBlendTournamentCrossoverBred] == 1
    assert values[RuntimeVariable.LLMBlendTournamentCrossoverAdmitted] == 1
    assert values[RuntimeVariable.LLMBlendTournamentCrossoverSurvived] == 0
    assert values[RuntimeVariable.LLMBlendGoalCrossoverBred] == 0
