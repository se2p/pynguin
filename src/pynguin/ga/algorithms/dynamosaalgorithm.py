#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the DynaMOSA test-generation strategy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot

import pynguin.configuration as config
import pynguin.ga.coveragegoals as bg
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.abstractmosaalgorithm import AbstractMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.testcase.localsearch import TestSuiteLocalSearch
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.computations as ff
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    from pynguin.ga.algorithms.archive import CoverageArchive
    from pynguin.instrumentation.tracer import SubjectProperties


class DynaMOSAAlgorithm(AbstractMOSAAlgorithm):
    """Implements the Dynamic Many-Objective Sorting Algorithm DynaMOSA."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self._goals_manager: _GoalsManager

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
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

        # Calculate dominance ranks and crowding distance
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._goals_manager.current_goals
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i), self._goals_manager.current_goals
            )

        self.before_first_search_iteration(self.create_test_suite(self._archive.solutions))
        while self.resources_left() and len(self._archive.uncovered_goals) > 0:
            self.evolve()
            if config.configuration.local_search.local_search:
                self.local_search()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        self.after_search_finish()
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def evolve(self) -> None:
        """Runs one evolution step."""
        offspring_population: list[tcc.TestCaseChromosome] = self._breed_next_generation()

        # Create union of parents and offspring
        union: list[tcc.TestCaseChromosome] = []
        union.extend(self._population)
        union.extend(offspring_population)

        # Ranking the union
        self._logger.debug("Union Size = %d", len(union))
        # Ranking the union using the best rank algorithm
        fronts = self._ranking_function.compute_ranking_assignment(
            union, self._goals_manager.current_goals
        )

        # Form the next population using “preference sorting and non-dominated
        # sorting” on the updated set of goals
        remain = max(
            config.configuration.search_algorithm.population,
            len(fronts.get_sub_front(0)),
        )
        index = 0
        self._population.clear()

        # Obtain the first front
        front = fronts.get_sub_front(index)

        while remain > 0 and remain >= len(front) != 0:
            # Assign crowding distance to individuals
            fast_epsilon_dominance_assignment(front, self._goals_manager.current_goals)
            # Add the individuals of this front
            self._population.extend(front)
            # Decrement remain
            remain -= len(front)
            # Obtain the next front
            index += 1
            if remain > 0:
                front = fronts.get_sub_front(index)

        # Remain is less than len(front[index]), insert only the best one
        if remain > 0 and len(front) != 0:
            fast_epsilon_dominance_assignment(front, self._goals_manager.current_goals)
            front.sort(key=lambda t: t.distance, reverse=True)
            self._population.extend(front[k] for k in range(remain))

        self._goals_manager.update(self._population)

    def local_search(self) -> None:
        """Runs local search."""
        test_cases: OrderedSet[tcc.TestCaseChromosome] = OrderedSet()
        for chromosome in self._archive.solutions:
            test_cases.add(chromosome.clone())
        test_suite = self.create_test_suite(test_cases)
        global_search_coverage = test_suite.get_coverage()
        self._logger.debug("Starting local search")
        timer = LocalSearchTimer()
        timer.start_timer()

        TestSuiteLocalSearch.local_search(
            TestSuiteLocalSearch(),
            test_suite,
            self.test_factory,
            self.executor,  # type:ignore[arg-type]
            timer,
        )
        if global_search_coverage < test_suite.get_coverage():
            self._logger.info(
                "Local search complete, increased coverage from %f to %f",
                global_search_coverage,
                test_suite.get_coverage(),
            )
        else:
            self._logger.info("Local search complete, the coverage hasn't changed")

        self._goals_manager.update(test_suite.test_case_chromosomes)


class _GoalsManager:
    """Manages goals and provides dynamically selected ones for the generation."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        fitness_functions: OrderedSet[ff.FitnessFunction],
        archive: CoverageArchive,
        subject_properties: SubjectProperties,
    ) -> None:
        self._archive = archive
        branch_fitness_functions: OrderedSet[bg.BranchCoverageTestFitness] = OrderedSet()
        for fit in fitness_functions:
            assert isinstance(fit, bg.BranchCoverageTestFitness)
            branch_fitness_functions.add(fit)
        self._graph = _BranchFitnessGraph(branch_fitness_functions, subject_properties)
        self._current_goals: OrderedSet[bg.BranchCoverageTestFitness] = self._graph.root_branches
        self._archive.add_goals(self._current_goals)  # type: ignore[arg-type]

    @property
    def current_goals(self) -> OrderedSet[ff.FitnessFunction]:
        """Provides the set of current goals.

        Returns:
            The set of current goals
        """
        return self._current_goals  # type: ignore[return-value]

    def update(self, solutions: list[tcc.TestCaseChromosome]) -> None:
        """Updates the information on the current goals from the found solutions.

        Args:
            solutions: The previously found solutions
        """
        # We must keep iterating, as long as new goals are added.
        new_goals_added = True
        while new_goals_added:
            self._archive.update(solutions)
            covered = self._archive.covered_goals
            new_goals: OrderedSet[bg.BranchCoverageTestFitness] = OrderedSet()
            new_goals_added = False
            for old_goal in self._current_goals:
                if old_goal in covered:
                    children = self._graph.get_structural_children(old_goal)
                    for child in children:
                        if child not in self._current_goals and child not in covered:
                            new_goals.add(child)
                            new_goals_added = True
                else:
                    new_goals.add(old_goal)
            self._current_goals = new_goals
            self._archive.add_goals(self._current_goals)  # type: ignore[arg-type]
        self._logger.debug("current goals after update: %s", self._current_goals)


class _BranchFitnessGraph:
    """Best effort re-implementation of EvoSuite's BranchFitnessGraph.

    Arranges the fitness functions for all branches according to their control
    dependencies in the CDG. Each node represents a fitness function. A directed edge
    (u -> v) states that fitness function v should be added for consideration
    only when fitness function u has been covered.
    """

    def __init__(
        self,
        fitness_functions: OrderedSet[bg.BranchCoverageTestFitness],
        subject_properties: SubjectProperties,
    ):
        self._graph: nx.DiGraph[bg.BranchCoverageTestFitness] = nx.DiGraph()
        # Branch less code objects and branches that are not control dependent on other
        # branches.
        self._root_branches: OrderedSet[bg.BranchCoverageTestFitness] = OrderedSet()
        self._build_graph(fitness_functions, subject_properties)

    def _build_graph(
        self,
        fitness_functions: OrderedSet[bg.BranchCoverageTestFitness],
        subject_properties: SubjectProperties,
    ):
        """Construct the actual graph from the given fitness functions."""
        for fitness in fitness_functions:
            self._graph.add_node(fitness)

        for fitness in fitness_functions:
            if fitness.goal.is_branchless_code_object:
                self._root_branches.add(fitness)
                continue
            assert fitness.goal.is_branch
            branch_goal = cast("bg.BranchGoal", fitness.goal)
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
                predicate_meta_data.node,
            )

            for dependency in dependencies:
                goal = bg.BranchGoal(
                    predicate_meta_data.code_object_id,
                    nodes_predicates[dependency.node],
                    value=dependency.branch_value,
                )
                dependent_ff = self._goal_to_fitness_function(fitness_functions, goal)
                self._graph.add_edge(dependent_ff, fitness)

        # Sanity check
        assert {n for n in self._graph.nodes if self._graph.in_degree(n) == 0}.issubset(
            self._root_branches
        ), "Root branches cannot depend on other branches."

    @property
    def dot(self):
        """Return DOT representation of this graph."""
        dot = to_pydot(self._graph)
        return dot.to_string()

    @property
    def root_branches(self) -> OrderedSet[bg.BranchCoverageTestFitness]:
        """Return the root branches, i.e., the fitness functions without conditions."""
        return OrderedSet(self._root_branches)

    @staticmethod
    def _goal_to_fitness_function(
        search_in: OrderedSet[bg.BranchCoverageTestFitness], goal: bg.BranchGoal
    ) -> bg.BranchCoverageTestFitness:
        """Little helper to find the fitness function associated with a certain goal.

        Args:
            search_in: The list to search in
            goal: The goal to search for

        Returns:
            The found fitness function.
        """
        for fitness in search_in:
            if fitness.goal == goal:
                return fitness
        raise RuntimeError(f"Could not find fitness function for goal: {goal}")

    def get_structural_children(
        self, fitness_function: bg.BranchCoverageTestFitness
    ) -> OrderedSet[bg.BranchCoverageTestFitness]:
        """Get the fitness functions that are structural children of the given one.

        Args:
            fitness_function: The fitness function whose structural children should be
            returned.

        Returns:
            The structural children fitness functions of the given fitness function.
        """
        return OrderedSet(self._graph.successors(fitness_function))
