#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Unit tests for blending and lineage elitism of injected LLM test cases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import pynguin.configuration as config
from pynguin.ga.algorithms.llmlineage import BlendChannel
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


class _Chromosome:
    """A minimal stand-in for a test case chromosome."""

    def __init__(self, fitness=None, rank=0, distance=0.0, size=3):
        self.test_case = object()
        self.lineage = None
        self.changed = False
        self.rank = rank
        self.distance = distance
        self._fitness = fitness or {}
        self._size = size

    def clone(self):
        clone = _Chromosome(self._fitness, self.rank, self.distance, self._size)
        clone.test_case = self.test_case
        clone.lineage = self.lineage
        return clone

    def size(self):
        return self._size

    def mutate(self):
        self.test_case = object()
        self.changed = True

    def get_fitness_for(self, goal):
        return self._fitness.get(goal, 10.0)


@pytest.fixture
def algorithm():
    with patch("pynguin.ga.algorithms.llmosalgorithm.LLMAgent"):
        algorithm = LLMOSAAlgorithm()
    algorithm._logger = MagicMock()
    algorithm._archive = MagicMock()
    algorithm._archive.uncovered_goals = []
    algorithm._population = []
    algorithm._selection_function = MagicMock()
    algorithm._crossover_function = MagicMock()
    return algorithm


def _search_config(**values):
    return config.SearchAlgorithmConfiguration(**values)


def _injected(algorithm, count=1):
    chromosomes = [_Chromosome() for _ in range(count)]
    for chromosome in chromosomes:
        algorithm._lineage.inject(chromosome, algorithm._generation)
    return chromosomes


def test_register_without_blending_adds_raw_tests(algorithm):
    chromosomes = [_Chromosome(), _Chromosome()]
    config.configuration.search_algorithm.llm_blend_keep_raw = False

    added = algorithm._register_injected_chromosomes(chromosomes)

    assert added == chromosomes
    assert [c.lineage for c in chromosomes] == [0, 1]
    assert algorithm._blend_queue == []


def test_register_queues_brood_per_injected_test(algorithm):
    config.configuration.search_algorithm = _search_config(
        llm_blend_goal_crossovers=1, llm_blend_mutants=2
    )
    chromosome = _Chromosome()

    added = algorithm._register_injected_chromosomes([chromosome])

    assert added == [chromosome]
    assert algorithm._blend_queue == [
        (
            chromosome,
            [BlendChannel.GOAL_CROSSOVER, BlendChannel.MUTANT, BlendChannel.MUTANT],
        )
    ]


def test_register_drops_raw_tests_if_not_kept(algorithm):
    config.configuration.search_algorithm = _search_config(
        llm_blend_mutants=1, llm_blend_keep_raw=False
    )

    injected = _Chromosome()
    algorithm._archive.update = MagicMock()

    assert algorithm._register_injected_chromosomes([injected]) == []
    assert len(algorithm._blend_queue) == 1
    algorithm._archive.update.assert_called_once_with([injected])


def test_integrate_prepends_and_registers(algorithm):
    existing = _Chromosome()
    algorithm._population = [existing]
    injected = _Chromosome()

    algorithm._integrate_llm_chromosomes([injected])

    assert algorithm._population == [injected, existing]
    assert injected.lineage == 0


def test_breed_broods_respects_the_evaluation_cap(algorithm):
    config.configuration.search_algorithm = _search_config(
        llm_blend_mutants=2, llm_blend_max_evaluations=3
    )
    first, second = _Chromosome(), _Chromosome()
    algorithm._register_injected_chromosomes([first, second])

    brood = algorithm._breed_llm_broods()

    assert len(brood) == 3
    assert [algorithm._lineage.root_of(c) for c in brood] == [0, 0, 1]
    assert algorithm._blend_queue == [(second, [BlendChannel.MUTANT])]
    assert len(algorithm._breed_llm_broods()) == 1
    assert algorithm._blend_queue == []
    assert algorithm._breed_llm_broods() == []


def test_breed_next_generation_appends_brood(algorithm):
    config.configuration.search_algorithm = _search_config(llm_blend_mutants=1)
    algorithm._register_injected_chromosomes([_Chromosome()])
    regular = _Chromosome()
    algorithm._chromosome_factory = MagicMock()
    with patch(
        "pynguin.ga.algorithms.mosaalgorithm.MOSAAlgorithm._breed_next_generation",
        return_value=[regular],
    ):
        offspring = algorithm._breed_next_generation()

    assert offspring[0] is regular
    assert len(offspring) == 2
    assert algorithm._last_offspring is offspring


def test_blend_mutant_unchanged_is_dropped(algorithm):
    (injected,) = _injected(algorithm)
    with patch.object(LLMOSAAlgorithm, "_mutate"):
        assert algorithm._blend(injected, BlendChannel.MUTANT) is None


def test_blend_tournament_crossover_uses_selection(algorithm):
    (injected,) = _injected(algorithm)
    partner = _Chromosome()
    algorithm._population = [partner]
    algorithm._selection_function.select.return_value = [partner]

    def cross_over(offspring, _other):
        offspring.test_case = object()

    algorithm._crossover_function.cross_over.side_effect = cross_over

    offspring = algorithm._blend(injected, BlendChannel.TOURNAMENT_CROSSOVER)

    assert offspring is not None
    assert offspring.lineage == injected.lineage


def test_blend_crossover_failure_is_dropped(algorithm):
    (injected,) = _injected(algorithm)
    algorithm._selection_function.select.return_value = [_Chromosome()]
    algorithm._crossover_function.cross_over.side_effect = ConstructionFailedException()

    assert algorithm._blend(injected, BlendChannel.TOURNAMENT_CROSSOVER) is None


def test_blend_empty_offspring_is_dropped(algorithm):
    injected = _Chromosome(size=0)
    algorithm._lineage.inject(injected, 0)

    def mutate(offspring):
        offspring.test_case = object()

    with patch.object(LLMOSAAlgorithm, "_mutate", side_effect=mutate):
        assert algorithm._blend(injected, BlendChannel.MUTANT) is None


def test_goal_crossover_partner_is_closest_to_the_injected_tests_goal(algorithm):
    near, far = "near", "far"
    algorithm._archive.uncovered_goals = [far, near]
    injected = _Chromosome({near: 1.0, far: 5.0})
    algorithm._lineage.inject(injected, 0)
    sibling = _Chromosome({near: 0.0})
    algorithm._lineage.derive(sibling, 0, BlendChannel.MUTANT, 0)
    best = _Chromosome({near: 0.5, far: 9.0})
    other = _Chromosome({near: 2.0, far: 0.1})
    algorithm._population = [injected, sibling, other, best]

    assert algorithm._goal_crossover_partner(injected) is best


@pytest.mark.parametrize("goals,population", [([], True), (["goal"], False)])
def test_goal_crossover_partner_none(algorithm, goals, population):
    (injected,) = _injected(algorithm)
    algorithm._archive.uncovered_goals = goals
    algorithm._population = [injected, _Chromosome()] if population else [injected]

    assert algorithm._goal_crossover_partner(injected) is None


def test_goal_crossover_falls_back_to_selection(algorithm):
    (injected,) = _injected(algorithm)
    partner = _Chromosome()
    algorithm._selection_function.select.return_value = [partner]

    def cross_over(offspring, _other):
        offspring.test_case = object()

    algorithm._crossover_function.cross_over.side_effect = cross_over

    assert algorithm._blend(injected, BlendChannel.GOAL_CROSSOVER) is not None
    algorithm._selection_function.select.assert_called_once()


def test_evolve_observes_and_counts_generations(algorithm):
    (injected,) = _injected(algorithm)
    with patch("pynguin.ga.algorithms.mosaalgorithm.MOSAAlgorithm.evolve"):
        algorithm._population = [injected]
        algorithm.evolve()

    assert algorithm._generation == 1
    assert algorithm._lineage.statistics([])[RuntimeVariable.LLMInjectedAdmitted] == 1


def test_elitism_disabled_does_nothing(algorithm):
    (injected,) = _injected(algorithm)
    algorithm._population = [_Chromosome()]

    algorithm._apply_lineage_elitism([injected])

    assert injected not in algorithm._population


def test_elitism_reinserts_best_member_in_place_of_the_worst(algorithm):
    config.configuration.search_algorithm = _search_config(
        population=4, llm_lineage_elitism_generations=2, llm_lineage_elitism_max_fraction=0.5
    )
    goal = MagicMock()
    algorithm._archive.uncovered_goals = [goal]
    (injected,) = _injected(algorithm)
    injected._fitness = {goal: 5.0}
    # Rank and distance are stale or unset (-1) for dropped members and are ignored.
    unranked = _Chromosome(fitness={goal: 4.0}, rank=-1)
    better = _Chromosome(fitness={goal: 2.0}, rank=3, distance=0.0)
    best = _Chromosome(fitness={goal: 1.0}, rank=5)
    for offspring in (unranked, better, best):
        algorithm._lineage.derive(offspring, 0, BlendChannel.MUTANT, 0)
    population = [_Chromosome() for _ in range(4)]
    algorithm._population = list(population)
    algorithm._archive.update = MagicMock()

    algorithm._apply_lineage_elitism([*population, injected, unranked, better, best])

    assert algorithm._population == [*population[:3], best]
    algorithm._archive.update.assert_called_once_with([best])
    assert algorithm._lineage.reinsertions == 1


def test_elitism_keeps_present_and_old_lineages(algorithm):
    config.configuration.search_algorithm = _search_config(
        population=4, llm_lineage_elitism_generations=1, llm_lineage_elitism_max_fraction=1.0
    )
    old, present = _injected(algorithm, 2)
    algorithm._generation = 1
    (young,) = _injected(algorithm)
    algorithm._lineage._records[1].generation = 1
    algorithm._population = [present, _Chromosome()]

    algorithm._apply_lineage_elitism([old, present, young])

    assert algorithm._population == [present, young]


def test_elitism_respects_the_fraction_cap(algorithm):
    config.configuration.search_algorithm = _search_config(
        population=4, llm_lineage_elitism_generations=1, llm_lineage_elitism_max_fraction=0.25
    )
    first, second = _injected(algorithm, 2)
    algorithm._population = [_Chromosome() for _ in range(4)]

    algorithm._apply_lineage_elitism([first, second])

    assert algorithm._lineage.roots_in(algorithm._population) == {0}


def test_elitism_appends_if_every_member_is_protected(algorithm):
    config.configuration.search_algorithm = _search_config(
        population=2, llm_lineage_elitism_generations=1, llm_lineage_elitism_max_fraction=1.0
    )
    first, second = _injected(algorithm, 2)
    algorithm._population = [first]

    algorithm._apply_lineage_elitism([first, second])

    assert algorithm._population == [first, second]


def test_elitism_skips_lineage_without_members_in_the_union(algorithm):
    config.configuration.search_algorithm = _search_config(
        population=2, llm_lineage_elitism_generations=1, llm_lineage_elitism_max_fraction=1.0
    )
    _injected(algorithm)
    population = [_Chromosome()]
    algorithm._population = list(population)

    algorithm._apply_lineage_elitism(population)

    assert algorithm._population == population


def test_after_search_finish_reports_lineage_statistics(algorithm):
    (injected,) = _injected(algorithm)
    algorithm._population = [injected]
    with patch("pynguin.ga.algorithms.llmosalgorithm.stat") as mock_stat:
        algorithm.after_search_finish()

    tracked = {
        call.args[0]: call.args[1] for call in mock_stat.track_output_variable.call_args_list
    }
    assert tracked[RuntimeVariable.LLMInjectedTests] == 1
    assert tracked[RuntimeVariable.LLMInjectedSurvived] == 1
