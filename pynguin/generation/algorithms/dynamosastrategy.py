#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
"""Provides the DynaMOSA test-generation strategy."""
import logging
import queue
from typing import Dict, List, Set, Tuple

import pynguin.analyses.controlflow.programgraph as pg
import pynguin.configuration as config
import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchcoveragetestfitness as bctf
import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.statistics as stat
from pynguin.analyses.controlflow import cfg
from pynguin.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pynguin.ga.operators.ranking.crowdingdistance import (
    fast_epsilon_dominance_assignment,
)
from pynguin.generation.algorithms.abstractmosastrategy import AbstractMOSATestStrategy
from pynguin.generation.algorithms.archive import Archive
from pynguin.testcase.execution.executiontracer import KnownData
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


class DynaMOSATestStrategy(AbstractMOSATestStrategy):
    """Implements the Dynamic Many-Objective Sorting Algorithm DynaMOSA."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._goals_manager: _GoalsManager

    def generate_tests(self) -> chrom.Chromosome:
        self._logger.info("Start generating tests")
        self._archive = Archive(set(self._fitness_functions))
        self._goals_manager = _GoalsManager(self._archive, self.executor)
        self._number_of_goals = len(self._fitness_functions)
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.Goals, self._number_of_goals
        )

        self._current_iteration = 0
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

        while (
            not self._stopping_condition.is_fulfilled()
            and len(self._goals_manager.uncovered_goals) > 0
        ):
            self.evolve()
            self._notify_iteration()
            self._current_iteration += 1

        stat.track_output_variable(
            RuntimeVariable.AlgorithmIterations, self._current_iteration
        )
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def evolve(self) -> None:
        """Runs one evolution step."""
        offspring_population: List[
            tcc.TestCaseChromosome
        ] = self._breed_next_generation()

        # Create union of parents and offspring
        union: List[tcc.TestCaseChromosome] = []
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
            for k in range(remain):
                self._population.append(front[k])

        self._goals_manager.update(self._population)


class _GoalsManager:
    """Manages goals and provides dynamically selected ones for the generation."""

    def __init__(self, archive: Archive, executor: TestCaseExecutor) -> None:
        self._archive = archive
        self._graph = _create_branch_fitness_graph(
            archive.uncovered_goals, executor.tracer.get_known_data()
        )
        self._current_goals: Set[ff.FitnessFunction] = self._graph.root_branches

    @property
    def current_goals(self) -> Set[ff.FitnessFunction]:
        """Provides the set of current goals.

        Returns:
            The set of current goals
        """
        return self._current_goals

    @property
    def uncovered_goals(self) -> Set[ff.FitnessFunction]:
        """Provides the set of yet uncovered goals.

        Returns:
            The set of yet uncovered goals
        """
        return self._archive.uncovered_goals

    def update(self, solutions: List[tcc.TestCaseChromosome]) -> None:
        """Updates the information on the current goals from the found solutions.

        Args:
            solutions: The previously found solutions
        """
        # Update the archive
        self._archive.update(solutions)

        # Update the set of current goals
        new_goals = self._graph.retrieve_new_goals(self._current_goals)  # type: ignore
        self._current_goals = new_goals  # type: ignore


class _BranchFitnessGraph:
    """Implements a dynamic search for yet-to-cover targets."""

    def __init__(self) -> None:
        self._control_dependence_graphs: Dict[int, ControlDependenceGraph] = {}
        self._root_branches: Set[bctf.BranchCoverageTestFitness] = set()
        self._branchless_code_objects: Set[int] = set()
        self._edge_predicate_map: Dict[
            int,
            Dict[
                Tuple[pg.ProgramGraphNode, pg.ProgramGraphNode],
                bctf.BranchCoverageTestFitness,
            ],
        ] = {}

    @property
    def root_branches(self) -> Set[ff.FitnessFunction]:
        """Provides the root branches.

        The root branches are those branches that are not control dependent on
        another branch.

        Returns:
            The set of root branches
        """
        return self._root_branches  # type: ignore

    def build_graph(
        self, goals: Set[bctf.BranchCoverageTestFitness], known_data: KnownData
    ) -> None:
        """Builds the data structure.

        Args:
            goals: The set of fitness functions
            known_data: All known data from the tracer
        """
        code_objects = known_data.existing_code_objects
        predicates = known_data.existing_predicates

        for code_object_id, code_object in code_objects.items():
            # Handle root branches if any
            self._handle_root_branches(code_object_id, goals)

            # Create partial map of edges and targets based on control-flow graph
            edge_predicate_map: Dict[
                Tuple[pg.ProgramGraphNode, pg.ProgramGraphNode],
                bctf.BranchCoverageTestFitness,
            ] = self._get_edge_predicate_map_from_cfg(code_object.cfg, goals)

            seen_goals: Set[bctf.BranchCoverageTestFitness] = set()

            # Collect those targets that are control dependent
            for edge in code_object.cdg.graph.edges:
                goal = edge_predicate_map.get(edge, None)
                if goal is not None:
                    seen_goals.add(goal)

            # Collect those target that are actually relevant for this code object
            goals_for_code_object = {
                goal
                for goal in goals
                if isinstance(goal.goal, bcg.NonRootBranchCoverageGoal)
                and predicates[goal.goal.predicate_id].code_object_id == code_object_id
            }

            # The remaining goals that are relevant for this object but not have a
            # control dependency
            remaining_goals = goals_for_code_object.difference(
                seen_goals, self._root_branches
            )

            # Update the goals sets
            self._root_branches.update(remaining_goals)
            self._edge_predicate_map[code_object_id] = edge_predicate_map
            self._control_dependence_graphs[code_object_id] = code_object.cdg

    def _get_edge_predicate_map_from_cfg(
        self, graph: cfg.CFG, goals: Set[bctf.BranchCoverageTestFitness]
    ) -> Dict[
        Tuple[pg.ProgramGraphNode, pg.ProgramGraphNode], bctf.BranchCoverageTestFitness
    ]:
        edge_predicate_map: Dict[
            Tuple[pg.ProgramGraphNode, pg.ProgramGraphNode],
            bctf.BranchCoverageTestFitness,
        ] = {}
        for edge in graph.graph.edges:
            start_node = edge[0]
            if start_node.predicate_id is not None:
                targets = list(graph.graph.neighbors(start_node))
                current_goals = self._find_goals_for_predicate(
                    goals, start_node.predicate_id
                )
                for merged in zip(targets, current_goals):
                    edge_predicate_map[(start_node, merged[0])] = merged[1]
        return edge_predicate_map

    @staticmethod
    def _find_goals_for_predicate(
        goals: Set[bctf.BranchCoverageTestFitness], predicate_id: int
    ) -> List[bctf.BranchCoverageTestFitness]:
        goals_for_predicate = [
            goal
            for goal in goals
            if isinstance(goal.goal, bcg.NonRootBranchCoverageGoal)
            and goal.goal.predicate_id == predicate_id
        ]
        # Make sure that True branch is always first!  This is a (shitty) implicit
        # convention from goal creation (see branchcoveragefactory.py), but there is
        # no more elegant solution to map CFG edges and goals afterwards...
        goals_for_predicate.sort(key=lambda g: g.goal.value, reverse=True)
        return goals_for_predicate

    def _handle_root_branches(
        self, code_object_id: int, goals: Set[bctf.BranchCoverageTestFitness]
    ) -> None:
        for goal in goals:
            if (
                isinstance(goal.goal, bcg.RootBranchCoverageGoal)
                and goal.goal.code_object_id == code_object_id
            ):
                self._root_branches.add(goal)
                self._branchless_code_objects.add(code_object_id)

    def retrieve_new_goals(
        self, old_goals: Set[bctf.BranchCoverageTestFitness]
    ) -> Set[bctf.BranchCoverageTestFitness]:
        """Retrieves the set of new goals.

        Args:
            old_goals: The previously selected goals

        Returns:
            A set of new goals to consider for the search
        """
        new_goals: Set[bctf.BranchCoverageTestFitness] = set()

        # Re-add those that were not covered in previous iteration
        for old_goal in old_goals:
            if not old_goal.is_covered:
                new_goals.add(old_goal)

        for (
            code_object_id,
            control_dependence_graph,
        ) in self._control_dependence_graphs.items():
            if code_object_id in self._branchless_code_objects:
                new_goals.update(
                    self._retrieve_goals_for_branchless_code_object(code_object_id)
                )
            else:
                new_goals.update(
                    self._retrieve_goals_from_control_dependence_graph(
                        control_dependence_graph, code_object_id
                    )
                )

        return new_goals

    def _retrieve_goals_for_branchless_code_object(
        self, code_object_id: int
    ) -> Set[bctf.BranchCoverageTestFitness]:
        result: Set[bctf.BranchCoverageTestFitness] = set()
        for root_branch in self._root_branches:
            if (
                isinstance(root_branch.goal, bcg.RootBranchCoverageGoal)
                and not root_branch.is_covered
                and root_branch.goal.code_object_id == code_object_id
            ):
                result.add(root_branch)
        return result

    def _retrieve_goals_from_control_dependence_graph(
        self, control_dependence_graph: ControlDependenceGraph, code_object_id: int
    ) -> Set[bctf.BranchCoverageTestFitness]:
        result: Set[bctf.BranchCoverageTestFitness] = set()
        visited: Set[pg.ProgramGraphNode] = set()
        wait_list: queue.Queue = queue.Queue()
        wait_list.put(control_dependence_graph.entry_node)
        while not wait_list.empty():
            element = wait_list.get()
            if element in visited:
                continue
            visited.add(element)
            for child in control_dependence_graph.get_successors(element):
                edge = (element, child)
                goal = self._edge_predicate_map[code_object_id].get(edge)
                if goal is not None:
                    if goal.is_covered:
                        wait_list.put(child)
                    else:
                        result.add(goal)
                else:
                    wait_list.put(child)
        return result


def _create_branch_fitness_graph(
    goals: Set[ff.FitnessFunction], known_data: KnownData
) -> _BranchFitnessGraph:
    assert all(isinstance(goal, bctf.BranchCoverageTestFitness) for goal in goals)
    graph = _BranchFitnessGraph()
    graph.build_graph(goals, known_data)  # type: ignore  # We know types are correct!
    return graph
