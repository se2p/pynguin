#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Groups test cases into species to preserve diversity in DynaMOSA.

A species is a set of test cases whose features (called names or covered
branches) are within a Jaccard distance threshold of the species' representative.
Species-capped selection limits the share of the next population a single species
can take, so that one family of similar tests cannot take over the population.
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

import libcst as cst

import pynguin.configuration as config
from pynguin.utils.exceptions import ConfigurationException

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Sequence

    import pynguin.ga.testcasechromosome as tcc

Features = frozenset["Hashable"]


class _CallNameCollector(cst.CSTVisitor):
    """Collects the simple names of all called callees in a CST node."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Call(self, node: cst.Call) -> None:  # noqa: N802
        func = node.func
        if isinstance(func, cst.Name):
            self.names.add(func.value)
        elif isinstance(func, cst.Attribute):
            self.names.add(func.attr.value)


def method_call_features(chromosome: tcc.TestCaseChromosome) -> Features:
    """Provides the names called in a test case.

    The callee's simple name is used (``module_0.foo(x)`` and ``foo(x)`` both give
    ``foo``, ``obj.bar()`` gives ``bar``, ``Foo()`` gives ``Foo``), so generated
    statements and LLM-written statements are compared on the same terms.

    Args:
        chromosome: The test case chromosome.

    Returns:
        The set of called names.
    """
    collector = _CallNameCollector()
    for statement in chromosome.test_case.statements():
        statement.node.visit(collector)
    return frozenset(collector.names)


def trace_branch_features(chromosome: tcc.TestCaseChromosome) -> Features:
    """Provides the branches covered by the last execution of a test case.

    Args:
        chromosome: The test case chromosome.

    Returns:
        The covered branches as (predicate id, outcome) pairs, plus the executed
        code objects as ("code_object", id) pairs; empty if it was not executed.
    """
    result = chromosome.get_last_execution_result()
    if result is None:
        return frozenset()
    trace = result.execution_trace
    features: set[Hashable] = {
        (predicate, True) for predicate, distance in trace.true_distances.items() if distance == 0.0
    }
    features.update(
        (predicate, False)
        for predicate, distance in trace.false_distances.items()
        if distance == 0.0
    )
    features.update(("code_object", code_object) for code_object in trace.executed_code_objects)
    return frozenset(features)


def jaccard_distance(first: Features, second: Features) -> float:
    """Computes the Jaccard distance of two sets.

    Args:
        first: The first set.
        second: The second set.

    Returns:
        1 - |intersection| / |union| of both sets; 0.0 for two empty sets.
    """
    union = len(first | second)
    if union == 0:
        return 0.0
    return 1.0 - len(first & second) / union


_FEATURE_EXTRACTORS: dict[config.SpeciationMetric, Callable[[tcc.TestCaseChromosome], Features]] = {
    config.SpeciationMetric.METHOD_CALL_JACCARD: method_call_features,
    config.SpeciationMetric.TRACE_BRANCH_JACCARD: trace_branch_features,
}


@dataclasses.dataclass
class Species:
    """A species with a stable id, its representative's features, and its birth."""

    species_id: int
    representative: Features
    founded_generation: int


class SpeciesAssigner:
    """Assigns test cases to species with stable species ids.

    The assignment is deterministic and consumes no randomness.
    """

    def __init__(
        self,
        metric: config.SpeciationMetric,
        threshold: float,
    ) -> None:
        """Creates a new species assigner.

        Args:
            metric: The distance metric.
            threshold: The maximum distance to a representative to join its species.
        """
        self._features = _FEATURE_EXTRACTORS[metric]
        self._threshold = threshold
        self._species: dict[int, Species] = {}
        self._next_id = 0
        # Maps id(chromosome) to (chromosome, species id); the chromosome is kept
        # so that its id stays unique while it is mapped.
        self._assignment: dict[int, tuple[tcc.TestCaseChromosome, int]] = {}

    @property
    def species(self) -> dict[int, Species]:
        """Provides the living species by id.

        Returns:
            The living species.
        """
        return self._species

    @property
    def number_of_species_founded(self) -> int:
        """Provides the number of species founded so far.

        Returns:
            The number of species founded so far.
        """
        return self._next_id

    def species_of(self, chromosome: tcc.TestCaseChromosome) -> int | None:
        """Provides the species id of an assigned chromosome.

        Args:
            chromosome: The chromosome.

        Returns:
            Its species id, or None if it is not assigned.
        """
        entry = self._assignment.get(id(chromosome))
        if entry is None or entry[0] is not chromosome:
            return None
        return entry[1]

    def assign(self, individuals: Sequence[tcc.TestCaseChromosome], generation: int) -> None:
        """Assigns every individual to a species, founding species where needed.

        Individuals are processed in the given order. Each joins the closest species
        within the threshold (the lowest id on ties), otherwise it founds a new
        species and becomes its representative.

        Args:
            individuals: The individuals to assign, e.g., the ranked union.
            generation: The current generation.
        """
        self._assignment = {}
        for individual in individuals:
            features = self._features(individual)
            best_id: int | None = None
            best_distance = math.inf
            for species in self._species.values():
                distance = jaccard_distance(features, species.representative)
                if distance <= self._threshold and distance < best_distance:
                    best_id = species.species_id
                    best_distance = distance
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
                self._species[best_id] = Species(best_id, features, generation)
            self._assignment[id(individual)] = (individual, best_id)

    def update_representatives(self, population: Sequence[tcc.TestCaseChromosome]) -> None:
        """Keeps only species with members in the population and moves representatives.

        The new representative of a species is its first member in the population,
        which is ordered from the best front to the worst. Individuals of the
        population that were not assigned (e.g., added from outside) are ignored.

        Args:
            population: The population after selection.
        """
        new_representatives: dict[int, Features] = {}
        assignment: dict[int, tuple[tcc.TestCaseChromosome, int]] = {}
        for individual in population:
            species_id = self.species_of(individual)
            if species_id is None:
                continue
            assignment[id(individual)] = (individual, species_id)
            if species_id not in new_representatives:
                new_representatives[species_id] = self._features(individual)
        self._species = {
            species_id: dataclasses.replace(species, representative=new_representatives[species_id])
            for species_id, species in self._species.items()
            if species_id in new_representatives
        }
        self._assignment = assignment

    def is_newborn(self, species_id: int, generation: int, protection: int) -> bool:
        """Checks whether a species was founded within the last generations.

        Args:
            species_id: The species id.
            generation: The current generation.
            protection: The number of generations a new species is protected.

        Returns:
            Whether the species is younger than `protection` generations.
        """
        return generation - self._species[species_id].founded_generation < protection


@dataclasses.dataclass
class SpeciationOptions:
    """The selection options of speciation."""

    max_species_share: float = 1.0
    min_survivors: int = 0
    newborn_protection: int = 0
    fitness_sharing: bool = False

    @staticmethod
    def from_configuration() -> SpeciationOptions:
        """Reads and validates the options from the configuration.

        Returns:
            The options.

        Raises:
            ConfigurationException: If an option is out of range.
        """
        search = config.configuration.search_algorithm
        if not 0.0 <= search.speciation_threshold <= 1.0:
            raise ConfigurationException("speciation_threshold must be in [0, 1].")
        if not 0.0 < search.speciation_max_species_share <= 1.0:
            raise ConfigurationException("speciation_max_species_share must be in (0, 1].")
        if search.speciation_min_survivors < 0:
            raise ConfigurationException("speciation_min_survivors must not be negative.")
        if search.speciation_newborn_protection < 0:
            raise ConfigurationException("speciation_newborn_protection must not be negative.")
        return SpeciationOptions(
            max_species_share=search.speciation_max_species_share,
            min_survivors=search.speciation_min_survivors,
            newborn_protection=search.speciation_newborn_protection,
            fitness_sharing=search.speciation_fitness_sharing,
        )


@dataclasses.dataclass
class SelectionOutcome:
    """The result of a species-capped selection."""

    population: list[tcc.TestCaseChromosome]
    reserved: list[tcc.TestCaseChromosome]


class _PopulationBuilder:
    """Collects the next population and the species count of its members."""

    def __init__(
        self,
        capacity: int,
        species_of: Callable[[tcc.TestCaseChromosome], int],
    ) -> None:
        self.capacity = capacity
        self.species_of = species_of
        self.selected: list[tcc.TestCaseChromosome] = []
        self.selected_ids: set[int] = set()
        self.species_count: dict[int, int] = {}

    @property
    def full(self) -> bool:
        return len(self.selected) >= self.capacity

    @property
    def remaining(self) -> int:
        return self.capacity - len(self.selected)

    def contains(self, individual: tcc.TestCaseChromosome) -> bool:
        return id(individual) in self.selected_ids

    def count(self, individual: tcc.TestCaseChromosome) -> int:
        return self.species_count.get(self.species_of(individual), 0)

    def add(self, individual: tcc.TestCaseChromosome) -> None:
        self.selected.append(individual)
        self.selected_ids.add(id(individual))
        species_id = self.species_of(individual)
        self.species_count[species_id] = self.species_count.get(species_id, 0) + 1


def _reserve(
    builder: _PopulationBuilder,
    species_members: dict[int, list[tcc.TestCaseChromosome]],
    front_index: dict[int, int],
    quotas: dict[int, int],
) -> list[tcc.TestCaseChromosome]:
    """Reserves the best members of each species up to its quota.

    Reservation goes one level at a time, so that every species gets its first
    reserved member before any species gets its second. Species compete in the order
    of their best member (front, then crowding distance, then species id).

    Args:
        builder: The population under construction.
        species_members: The members of each species in the union.
        front_index: The front of each individual, by id.
        quotas: The number of members to reserve per species.

    Returns:
        The individuals added by the reservation.
    """
    ordered_members = {
        species_id: sorted(members, key=lambda ind: (front_index[id(ind)], -ind.distance))
        for species_id, members in species_members.items()
    }
    species_order = sorted(
        ordered_members,
        key=lambda sid: (
            front_index[id(ordered_members[sid][0])],
            -ordered_members[sid][0].distance,
            sid,
        ),
    )
    reserved: list[tcc.TestCaseChromosome] = []
    for level in range(max(quotas.values(), default=0)):
        for species_id in species_order:
            members = ordered_members[species_id]
            if builder.full or quotas[species_id] <= level or len(members) <= level:
                continue
            individual = members[level]
            if not builder.contains(individual):
                builder.add(individual)
                reserved.append(individual)
    return reserved


def _fill_capped(
    builder: _PopulationBuilder,
    fronts: Sequence[Sequence[tcc.TestCaseChromosome]],
    cap: int,
) -> None:
    """Fills the population front by front, deferring members of full species.

    A front that does not fit is cut by crowding distance. If slots remain after all
    fronts, the deferred individuals fill them in front order.

    Args:
        builder: The population under construction.
        fronts: The fronts to fill from, best first.
        cap: The maximum number of members per species before deferral.
    """
    deferred: list[tcc.TestCaseChromosome] = []
    for front in fronts:
        if builder.full:
            return
        candidates = [ind for ind in front if not builder.contains(ind)]
        if len(candidates) > builder.remaining:
            candidates.sort(key=lambda ind: ind.distance, reverse=True)
        for individual in candidates:
            if builder.full:
                return
            if builder.count(individual) >= cap:
                deferred.append(individual)
            else:
                builder.add(individual)
    for individual in deferred:
        if builder.full:
            return
        builder.add(individual)


def select_next_population(
    fronts: Sequence[Sequence[tcc.TestCaseChromosome]],
    population_size: int,
    species_of: Callable[[tcc.TestCaseChromosome], int],
    options: SpeciationOptions,
    protected_species: frozenset[int] = frozenset(),
) -> SelectionOutcome:
    """Selects the next population from ranked fronts with species constraints.

    The crowding distance of every individual must already be assigned.

    1. The first front is kept whole, as in DynaMOSA.
    2. Slots are reserved for the best members of each species, up to
       `min_survivors` per species and at least one per protected species, without
       exceeding the population size.
    3. The remaining fronts fill the population in order. An individual whose
       species already has ``ceil(max_species_share * population_size)`` members is
       deferred. A front that does not fit is cut by crowding distance.
    4. If slots remain, deferred individuals fill them in front order.

    With a share of 1.0, no reservations and no fitness sharing, the result is
    exactly the population plain DynaMOSA selection produces.

    Args:
        fronts: The ranked fronts, best first.
        population_size: The configured population size.
        species_of: Provides the species id of an individual.
        options: The speciation options.
        protected_species: Species protected as newborns.

    Returns:
        The next population, ordered by front, and the reserved individuals.
    """
    first_front = list(fronts[0]) if fronts else []
    builder = _PopulationBuilder(max(population_size, len(first_front)), species_of)
    # The tolerance keeps float products such as 0.14 * 50 = 7.000000000000001 at 7.
    cap = math.ceil(options.max_species_share * population_size - 1e-9)

    front_index: dict[int, int] = {}
    species_members: dict[int, list[tcc.TestCaseChromosome]] = {}
    for index, front in enumerate(fronts):
        for individual in front:
            front_index[id(individual)] = index
            species_members.setdefault(species_of(individual), []).append(individual)

    if options.fitness_sharing:
        for members in species_members.values():
            for individual in members:
                individual.distance /= len(members)

    for individual in first_front:
        builder.add(individual)

    quotas = {
        species_id: max(options.min_survivors, 1 if species_id in protected_species else 0)
        for species_id in species_members
    }
    reserved = _reserve(builder, species_members, front_index, quotas)

    _fill_capped(builder, fronts[1:], cap)

    population = sorted(builder.selected, key=lambda ind: front_index[id(ind)])
    return SelectionOutcome(population=population, reserved=reserved)
