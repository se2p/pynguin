#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import itertools
import random
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.ga.algorithms.speciation as spec
from pynguin.testcase.execution_result import ExecutionResult
from pynguin.utils.exceptions import ConfigurationException

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc


def _chromosome_with_code(*lines: str) -> tcc.TestCaseChromosome:
    statements = [SimpleNamespace(node=cst.parse_statement(line)) for line in lines]
    chromosome = MagicMock()
    chromosome.test_case.statements.return_value = statements
    return cast("tcc.TestCaseChromosome", chromosome)


def _chromosome_with_trace(
    true_distances: dict[int, float],
    false_distances: dict[int, float],
    code_objects: tuple[int, ...] = (),
) -> tcc.TestCaseChromosome:
    result = ExecutionResult()
    result.execution_trace.true_distances.update(true_distances)
    result.execution_trace.false_distances.update(false_distances)
    result.execution_trace.executed_code_objects.update(code_objects)
    chromosome = MagicMock()
    chromosome.get_last_execution_result.return_value = result
    return cast("tcc.TestCaseChromosome", chromosome)


class _Individual:
    """A stand-in for a chromosome with a name, a species and a crowding distance."""

    def __init__(self, name: str, species: int, distance: float = 0.0) -> None:
        self.name = name
        self.species = species
        self.distance = distance

    def __repr__(self) -> str:
        return self.name


def _species_of(individual: Any) -> int:
    return individual.species


def _select(
    fronts: list[list[_Individual]],
    population_size: int,
    options: spec.SpeciationOptions | None = None,
    protected: frozenset[int] = frozenset(),
) -> spec.SelectionOutcome:
    return spec.select_next_population(
        cast("Any", fronts),
        population_size,
        _species_of,
        options or spec.SpeciationOptions(),
        protected,
    )


def _plain_dynamosa(fronts: list[list[_Individual]], population_size: int) -> list[_Individual]:
    """The front-filling loop of DynaMOSAAlgorithm.evolve, on pre-assigned distances."""
    population: list[_Individual] = []
    remain = max(population_size, len(fronts[0]) if fronts else 0)
    index = 0
    front = list(fronts[0]) if fronts else []
    while remain > 0 and remain >= len(front) != 0:
        population.extend(front)
        remain -= len(front)
        index += 1
        if remain > 0:
            front = list(fronts[index]) if index < len(fronts) else []
    if remain > 0 and len(front) != 0:
        front.sort(key=lambda t: t.distance, reverse=True)
        population.extend(front[k] for k in range(remain))
    return population


def test_method_call_features_use_simple_callee_names():
    chromosome = _chromosome_with_code(
        "int_0 = 42",
        "foo_0 = module_0.Foo(int_0)",
        "var_0 = foo_0.bar(baz(1))",
        "assert module_0.qux() == 3",
    )
    assert spec.method_call_features(chromosome) == frozenset({"Foo", "bar", "baz", "qux"})


def test_method_call_features_ignore_calls_of_call_results():
    chromosome = _chromosome_with_code("var_0 = make()()")
    assert spec.method_call_features(chromosome) == frozenset({"make"})


def test_method_call_features_of_empty_test():
    assert spec.method_call_features(_chromosome_with_code()) == frozenset()


def test_trace_branch_features():
    chromosome = _chromosome_with_trace({0: 0.0, 1: 2.0}, {0: 1.0, 1: 0.0}, code_objects=(5,))
    assert spec.trace_branch_features(chromosome) == frozenset({
        (0, True),
        (1, False),
        ("code_object", 5),
    })


def test_trace_branch_features_without_execution():
    chromosome = MagicMock()
    chromosome.get_last_execution_result.return_value = None
    assert spec.trace_branch_features(chromosome) == frozenset()


@pytest.mark.parametrize(
    "first, second, expected",
    [
        (frozenset(), frozenset(), 0.0),
        (frozenset({1}), frozenset(), 1.0),
        (frozenset({1, 2}), frozenset({1, 2}), 0.0),
        (frozenset({1, 2}), frozenset({2, 3}), 1.0 - 1.0 / 3.0),
        (frozenset({1}), frozenset({2}), 1.0),
    ],
)
def test_jaccard_distance(first, second, expected):
    assert spec.jaccard_distance(first, second) == pytest.approx(expected)


def _assigner(threshold: float) -> spec.SpeciesAssigner:
    return spec.SpeciesAssigner(config.SpeciationMetric.METHOD_CALL_JACCARD, threshold)


def test_assigner_groups_similar_tests():
    assigner = _assigner(0.5)
    first = _chromosome_with_code("a()", "b()")
    similar = _chromosome_with_code("a()", "b()", "c()")
    different = _chromosome_with_code("x()")
    assigner.assign([first, similar, different], generation=0)
    assert assigner.species_of(first) == 0
    assert assigner.species_of(similar) == 0
    assert assigner.species_of(different) == 1
    assert assigner.number_of_species_founded == 2


def test_assigner_joins_closest_species_lowest_id_on_ties():
    assigner = _assigner(1.0)
    founder_a = _chromosome_with_code("a()")
    assigner.assign([founder_a], generation=0)
    assigner.update_representatives([founder_a])
    # With threshold 1.0 everything joins species 0.
    other = _chromosome_with_code("z()")
    assigner.assign([other], generation=1)
    assert assigner.species_of(other) == 0


def test_assigner_threshold_zero_requires_identical_features():
    assigner = _assigner(0.0)
    first = _chromosome_with_code("a()")
    same = _chromosome_with_code("a()")
    superset = _chromosome_with_code("a()", "b()")
    assigner.assign([first, same, superset], generation=0)
    assert assigner.species_of(first) == assigner.species_of(same) == 0
    assert assigner.species_of(superset) == 1


def test_assigner_prefers_the_closest_species():
    assigner = _assigner(0.9)
    far = _chromosome_with_code("a()", "b()", "c()", "d()")
    near = _chromosome_with_code("x()", "y()")
    assigner.assign([far, near], generation=0)
    assert assigner.species_of(near) == 1
    candidate = _chromosome_with_code("x()", "y()", "a()")
    assigner.assign([candidate], generation=1)
    assert assigner.species_of(candidate) == 1


def test_assigner_keeps_ids_stable_and_drops_extinct_species():
    assigner = _assigner(0.5)
    first = _chromosome_with_code("a()")
    second = _chromosome_with_code("b()")
    assigner.assign([first, second], generation=0)
    assigner.update_representatives([second])
    assert set(assigner.species) == {1}
    assert assigner.species_of(first) is None
    third = _chromosome_with_code("b()")
    fourth = _chromosome_with_code("a()")
    assigner.assign([third, fourth], generation=1)
    assert assigner.species_of(third) == 1
    assert assigner.species_of(fourth) == 2
    assert assigner.species[2].founded_generation == 1


def test_assigner_moves_representative_to_first_survivor():
    assigner = _assigner(0.5)
    founder = _chromosome_with_code("a()", "b()")
    drifted = _chromosome_with_code("a()", "b()", "c()")
    assigner.assign([founder, drifted], generation=0)
    assigner.update_representatives([drifted])
    assert assigner.species[0].representative == frozenset({"a", "b", "c"})


def test_assigner_ignores_unassigned_individuals():
    assigner = _assigner(0.5)
    first = _chromosome_with_code("a()")
    assigner.assign([first], generation=0)
    stranger = _chromosome_with_code("a()")
    assigner.update_representatives([stranger, first])
    assert assigner.species_of(stranger) is None
    assert assigner.species_of(first) == 0


def test_assigner_newborn():
    assigner = _assigner(0.5)
    assigner.assign([_chromosome_with_code("a()")], generation=3)
    assert assigner.is_newborn(0, generation=4, protection=2)
    assert not assigner.is_newborn(0, generation=5, protection=2)
    assert not assigner.is_newborn(0, generation=3, protection=0)


def test_assigner_trace_metric():
    assigner = spec.SpeciesAssigner(config.SpeciationMetric.TRACE_BRANCH_JACCARD, 0.0)
    first = _chromosome_with_trace({0: 0.0}, {})
    second = _chromosome_with_trace({0: 0.0}, {})
    third = _chromosome_with_trace({}, {0: 0.0})
    assigner.assign([first, second, third], generation=0)
    assert assigner.species_of(first) == assigner.species_of(second) == 0
    assert assigner.species_of(third) == 1


def test_options_from_configuration():
    search = config.configuration.search_algorithm
    search.speciation_max_species_share = 0.3
    search.speciation_min_survivors = 2
    search.speciation_newborn_protection = 4
    search.speciation_fitness_sharing = True
    assert spec.SpeciationOptions.from_configuration() == spec.SpeciationOptions(
        max_species_share=0.3, min_survivors=2, newborn_protection=4, fitness_sharing=True
    )


@pytest.mark.parametrize(
    "field, value",
    [
        ("speciation_threshold", -0.1),
        ("speciation_threshold", 1.1),
        ("speciation_max_species_share", 0.0),
        ("speciation_max_species_share", 1.5),
        ("speciation_min_survivors", -1),
        ("speciation_newborn_protection", -1),
    ],
)
def test_options_reject_values_out_of_range(field, value):
    setattr(config.configuration.search_algorithm, field, value)
    with pytest.raises(ConfigurationException):
        spec.SpeciationOptions.from_configuration()


def test_select_without_fronts():
    assert _select([], 4).population == []


def test_select_caps_species_from_second_front_on():
    front_0 = [_Individual("a0", 0)]
    front_1 = [_Individual(f"a{i}", 0) for i in range(1, 4)] + [_Individual("b0", 1)]
    front_2 = [_Individual("c0", 2), _Individual("c1", 2)]
    outcome = _select([front_0, front_1, front_2], 4, spec.SpeciationOptions(0.5))
    # Cap = 2: a0 and a1 fill species 0, b0 and c0 the rest.
    assert [ind.name for ind in outcome.population] == ["a0", "a1", "b0", "c0"]
    assert outcome.reserved == []


def test_select_cap_is_not_raised_by_float_rounding():
    # 0.14 * 50 = 7.000000000000001 must give a cap of 7, not 8.
    front_0 = [_Individual("a0", 0)]
    front_1 = [_Individual(f"a{i}", 0) for i in range(1, 20)]
    front_1 += [_Individual(f"o{i}", i) for i in range(1, 50)]
    outcome = _select([front_0, front_1], 50, spec.SpeciationOptions(0.14))
    assert sum(1 for ind in outcome.population if ind.species == 0) == 7


def test_select_keeps_first_front_whole_even_above_the_cap():
    front_0 = [_Individual(f"a{i}", 0) for i in range(3)]
    front_1 = [_Individual("a3", 0), _Individual("b0", 1)]
    outcome = _select([front_0, front_1], 4, spec.SpeciationOptions(0.25))
    assert [ind.name for ind in outcome.population] == ["a0", "a1", "a2", "b0"]


def test_select_fills_with_deferred_individuals_when_nothing_else_is_left():
    front_0 = [_Individual("a0", 0)]
    front_1 = [_Individual("a1", 0), _Individual("a2", 0), _Individual("b0", 1)]
    outcome = _select([front_0, front_1], 4, spec.SpeciationOptions(0.25))
    assert [ind.name for ind in outcome.population] == ["a0", "b0", "a1", "a2"]
    # Population is ordered by front, so the deferred ones stay in front 1.
    assert len(outcome.population) == 4


def test_select_cuts_front_by_distance_with_cap():
    front_0 = [_Individual("a0", 0)]
    front_1 = [
        _Individual("a1", 0, distance=0.9),
        _Individual("b0", 1, distance=0.1),
        _Individual("b1", 1, distance=0.8),
        _Individual("c0", 2, distance=0.5),
    ]
    outcome = _select([front_0, front_1], 3, spec.SpeciationOptions(0.34))
    # Cap = 2, the cut order is a1, b1, c0, b0; a1 fits, b1 fits.
    assert [ind.name for ind in outcome.population] == ["a0", "a1", "b1"]


def test_select_min_survivors_reserves_best_members():
    front_0 = [_Individual("a0", 0)]
    front_1 = [_Individual(f"a{i}", 0, distance=1.0) for i in range(1, 4)]
    front_2 = [_Individual("b0", 1, distance=0.2), _Individual("b1", 1, distance=0.7)]
    front_3 = [_Individual("c0", 2)]
    outcome = _select(
        [front_0, front_1, front_2, front_3], 4, spec.SpeciationOptions(min_survivors=2)
    )
    # Level 1 gives every species its best member (a0 is already in), level 2
    # adds a1 and fills the population before b0 gets its turn.
    assert [ind.name for ind in outcome.population] == ["a0", "a1", "b1", "c0"]
    assert [ind.name for ind in outcome.reserved] == ["b1", "c0", "a1"]


def test_select_reservations_never_exceed_the_capacity():
    front_0 = [_Individual("a0", 0)]
    front_1 = [_Individual(f"s{i}", i + 1) for i in range(5)]
    outcome = _select([front_0, front_1], 3, spec.SpeciationOptions(min_survivors=3))
    assert len(outcome.population) == 3
    # Species are served in the order of their best member: first front, then order.
    assert [ind.name for ind in outcome.population] == ["a0", "s0", "s1"]


def test_select_newborn_protection_keeps_best_member_of_protected_species():
    front_0 = [_Individual("a0", 0)]
    front_1 = [_Individual(f"a{i}", 0) for i in range(1, 4)]
    front_2 = [_Individual("n0", 7, distance=0.1), _Individual("n1", 7, distance=0.9)]
    outcome = _select([front_0, front_1, front_2], 4, protected=frozenset({7}))
    assert [ind.name for ind in outcome.population] == ["a0", "a1", "a2", "n1"]
    assert [ind.name for ind in outcome.reserved] == ["n1"]


def test_select_fitness_sharing_divides_distance_by_species_size():
    front_0 = [_Individual("a0", 0)]
    front_1 = [
        _Individual("a1", 0, distance=0.9),
        _Individual("a2", 0, distance=0.9),
        _Individual("b0", 1, distance=0.5),
    ]
    outcome = _select([front_0, front_1], 2, spec.SpeciationOptions(fitness_sharing=True))
    # Shared distances: a1 = a2 = 0.3, b0 = 0.5.
    assert [ind.name for ind in outcome.population] == ["a0", "b0"]
    assert front_1[0].distance == pytest.approx(0.3)


def _random_fronts(rng: random.Random) -> list[list[_Individual]]:
    fronts = []
    counter = itertools.count()
    for _ in range(rng.randint(1, 5)):
        front = []
        for _ in range(rng.randint(1, 6)):
            number = next(counter)
            front.append(
                _Individual(f"i{number}", rng.randint(0, 3), distance=rng.choice([0.0, 0.5, 1.0]))
            )
        fronts.append(front)
    return fronts


@pytest.mark.parametrize("seed", range(200))
def test_select_with_defaults_equals_plain_dynamosa(seed):
    rng = random.Random(seed)  # noqa: S311
    fronts = _random_fronts(rng)
    population_size = rng.randint(1, 12)
    expected = _plain_dynamosa([list(front) for front in fronts], population_size)
    outcome = _select(fronts, population_size)
    assert outcome.population == expected


@pytest.mark.parametrize("seed", range(100))
def test_select_with_any_options_keeps_the_population_size(seed):
    rng = random.Random(seed)  # noqa: S311
    fronts = _random_fronts(rng)
    population_size = rng.randint(1, 12)
    options = spec.SpeciationOptions(
        max_species_share=rng.choice([0.1, 0.25, 0.5, 1.0]),
        min_survivors=rng.randint(0, 3),
        newborn_protection=0,
        fitness_sharing=rng.choice([False, True]),
    )
    protected = frozenset(rng.sample(range(4), rng.randint(0, 2)))
    union = [ind for front in fronts for ind in front]
    outcome = _select(fronts, population_size, options, protected)
    expected_size = min(len(union), max(population_size, len(fronts[0])))
    assert len(outcome.population) == expected_size
    assert len({id(ind) for ind in outcome.population}) == expected_size
    assert all(ind in outcome.population for ind in fronts[0])
