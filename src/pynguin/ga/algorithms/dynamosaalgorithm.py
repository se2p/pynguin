# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
# SPDX-FileCopyrightText: 2026 Aditya Sinha
# SPDX-License-Identifier: MIT

"""Provides the DynaMOSA test-generation strategy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import networkx as nx

import pynguin.configuration as config
import pynguin.ga.coveragegoals as bg
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.abstractmosaalgorithm import AbstractMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    from pynguin.ga.algorithms.archive import CoverageArchive
    from pynguin.instrumentation.tracer import SubjectProperties


class DynaMOSAAlgorithm(AbstractMOSAAlgorithm):
    """Implements the Dynamic Many-Objective Sorting Algorithm (DynaMOSA)."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        """Initializes the DynaMOSA algorithm."""
        super().__init__()
        self._goals_manager: _GoalsManager

    def generate_tests(self) -> tsc.TestSuiteChromosome:
        """Generates a test suite using the DynaMOSA algorithm."""
        self.before_search_start()

        self._goals_manager = _GoalsManager(
            self._test_case_fitness_functions,  # type: ignore[arg-type]
            self._archive,
            self.executor.subject_properties,
        )

        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(RuntimeVariable.Goals, self._number_of_goals)

        self._population = self._get_random_population()
        self._goals_manager.update(self._population)

        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._goals_manager.current_goals
        )

        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i), self._goals_manager.current_goals
            )

        while self.resources_left() and len(self._archive.uncovered_goals) > 0:
            self.evolve()

        return self.create_test_suite(self._archive.solutions)

    def evolve(self) -> None:
        """Evolve the population by generating the next generation."""
        offspring_population = self._breed_next_generation()

        union = self._population + offspring_population

        fronts = self._ranking_function.compute_ranking_assignment(
            union, self._goals_manager.current_goals
        )

        remain = max(
            config.configuration.search_algorithm.population,
            len(fronts.get_sub_front(0)),
        )

        self._population.clear()
        index = 0
        front = fronts.get_sub_front(index)

        while remain > 0 and remain >= len(front):
            fast_epsilon_dominance_assignment(front, self._goals_manager.current_goals)
            self._population.extend(front)
            remain -= len(front)
            index += 1
            if remain > 0:
                front = fronts.get_sub_front(index)

        if remain > 0:
            fast_epsilon_dominance_assignment(front, self._goals_manager.current_goals)
            front.sort(key=lambda t: t.distance, reverse=True)
            self._population.extend(front[:remain])

        self._goals_manager.update(self._population)


class _GoalsManager:
    """Manages coverage goals for DynaMOSA."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        fitness_functions: OrderedSet[Any],
        archive: CoverageArchive,
        subject_properties: SubjectProperties,
    ) -> None:
        """Initializes the goals manager."""
        self._archive = archive

        branch_fitness_functions: OrderedSet[bg.BranchCoverageTestFitness] = OrderedSet()

        for fit in fitness_functions:
            if isinstance(fit, bg.BranchCoverageTestFitness):
                branch_fitness_functions.add(fit)

        self._graph: Any = _BranchFitnessGraph(branch_fitness_functions, subject_properties)

        self._current_goals: OrderedSet[Any] = OrderedSet()
        self._current_goals.update(branch_fitness_functions)

        for fit in fitness_functions:
            if not isinstance(fit, bg.BranchCoverageTestFitness):
                self._current_goals.add(fit)

        self._archive.add_goals(self._current_goals)  # type: ignore[arg-type]

    @property
    def current_goals(self) -> OrderedSet[Any]:
        """Returns the current set of goals."""
        return self._current_goals

    def update(self, solutions: list[tcc.TestCaseChromosome]) -> None:
        """Updates goal coverage based on solutions."""
        self._archive.update(solutions)


class _BranchFitnessGraph:
    """Represents dependency graph between branch fitness functions."""

    def __init__(
        self,
        fitness_functions: OrderedSet[bg.BranchCoverageTestFitness],
        subject_properties,
    ) -> None:
        """Initializes the branch fitness graph."""
        self._graph = nx.DiGraph()
        self._root_branches: OrderedSet[bg.BranchCoverageTestFitness] = OrderedSet()

        self._build_graph(fitness_functions, subject_properties)

    def _build_graph(self, fitness_functions, subject_properties) -> None:
        """Builds dependency graph."""
        for fitness in fitness_functions:
            self._graph.add_node(fitness)

        for fitness in fitness_functions:
            if fitness.goal.is_branchless_code_object:
                self._root_branches.add(fitness)
                continue

            branch_goal = fitness.goal
            predicate_meta_data = subject_properties.existing_predicates[branch_goal.predicate_id]

            code_object_meta_data = subject_properties.existing_code_objects[
                predicate_meta_data.code_object_id
            ]

            nodes_predicates = {
                meta_data.node: predicate_id
                for predicate_id, meta_data in subject_properties.existing_predicates.items()
                if meta_data.code_object_id == predicate_meta_data.code_object_id
            }

            if code_object_meta_data.cdg.is_control_dependent_on_root(predicate_meta_data.node):
                self._root_branches.add(fitness)

            dependencies = code_object_meta_data.cdg.get_control_dependencies(
                predicate_meta_data.node
            )

            for dependency in dependencies:
                goal = bg.BranchGoal(
                    predicate_meta_data.code_object_id,
                    nodes_predicates[dependency.node],
                    value=dependency.branch_value,
                )

                dependent_ff = self._goal_to_fitness_function(fitness_functions, goal)
                self._graph.add_edge(dependent_ff, fitness)

    @property
    def root_branches(self):
        """Returns root branches."""
        return OrderedSet(self._root_branches)

    def get_structural_children(self, fitness_function):
        """Returns structural children of a fitness function."""
        return OrderedSet(self._graph.successors(fitness_function))

    @staticmethod
    def _goal_to_fitness_function(search_in, goal):
        """Finds fitness function for a given goal."""
        for fitness in search_in:
            if fitness.goal == goal:
                return fitness
        raise RuntimeError(f"Goal not found: {goal}")
