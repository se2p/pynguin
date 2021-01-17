#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a data class to track the control-flow distances."""
from __future__ import annotations

from functools import total_ordering
from math import inf
from typing import Any, Dict, Optional

import networkx as nx

import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchpool as bp
from pynguin.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pynguin.analyses.controlflow.programgraph import ProgramGraphNode
from pynguin.ga.fitnessfunctions.fitness_utilities import normalise
from pynguin.testcase.execution.executionresult import ExecutionResult


@total_ordering
class ControlFlowDistance:
    """Tracks control-flow distances."""

    def __init__(self, approach_level: int = 0, branch_distance: float = 0.0) -> None:
        assert (
            approach_level >= 0 and branch_distance >= 0.0
        ), "Expect approach_level and branch_distance to be non-negative"
        self._approach_level = approach_level
        self._branch_distance = branch_distance

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, ControlFlowDistance):
            return False
        return (self._approach_level, self._branch_distance) == (
            other.approach_level,
            other.branch_distance,
        )

    def __lt__(self, other: ControlFlowDistance) -> bool:
        if not isinstance(other, ControlFlowDistance):
            raise TypeError(  # pylint: disable=raising-format-tuple
                "'<' not supported between instances of "
                "'ControlFlowDistance' and '%s'",
                type(other),
            )
        return (self._approach_level, self._branch_distance) < (
            other.approach_level,
            other.branch_distance,
        )

    @property
    def approach_level(self) -> int:
        """Provides the approach level.

        Returns:
            The approach level
        """
        return self._approach_level

    @approach_level.setter
    def approach_level(self, approach_level: int):
        assert approach_level >= 0, "Expect approach_level to be non-negative"
        self._approach_level = approach_level

    @property
    def branch_distance(self) -> float:
        """Provides the branch distance.

        Returns:
            The branch distance
        """
        return self._branch_distance

    @branch_distance.setter
    def branch_distance(self, branch_distance: float) -> None:
        assert branch_distance >= 0, "Expect branch_distance to be non-negative"
        self._branch_distance = branch_distance

    def increase_approach_level(self) -> None:
        """Increases the approach level by one."""
        self._approach_level += 1

    def get_resulting_branch_fitness(self) -> float:
        """Computes the resulting branch fitness.

        Returns:
            The resulting branch fitness
        """
        return self._approach_level + normalise(self._branch_distance)

    def __str__(self) -> str:
        return (
            f"approach = {self._approach_level}, branch distance ="
            f" {self._branch_distance}"
        )

    def __repr__(self) -> str:
        return (
            f"ControlFlowDistance(approach_level={self._approach_level}, "
            f"branch_distance={self._branch_distance})"
        )


def calculate_control_flow_distance(
    result: ExecutionResult,
    branch: Optional[bcg.Branch],
    value: bool,
    function_name: Optional[str],
) -> ControlFlowDistance:
    """Calculates the control-flow distance for a given result.

    Args:
        result: The result of the execution
        branch: The branch to check for
        value: Whether we check for the True or the False branch
        function_name: The function name

    Returns:
        A control-flow distance
    """
    if branch is None:
        assert function_name is not None
        return _get_root_distance(result, function_name)

    if value:
        if (
            branch.predicate_id in result.execution_trace.true_distances
            and result.execution_trace.true_distances[branch.predicate_id] == 0.0
        ):
            return ControlFlowDistance(0, 0.0)
    else:
        if (
            branch.predicate_id in result.execution_trace.false_distances
            and result.execution_trace.false_distances[branch.predicate_id] == 0.0
        ):
            return ControlFlowDistance(0, 0.0)

    return _get_non_root_distance(result, branch, value)


def _get_root_distance(
    result: ExecutionResult, function_name: str
) -> ControlFlowDistance:
    branch_pool = bp.INSTANCE

    distance = ControlFlowDistance()
    if (
        branch_pool.is_branchless_function(function_name)
        and branch_pool.get_branchless_function_code_object_id(function_name)
        in result.execution_trace.executed_code_objects
    ):
        # The code object was executed by the execution
        return distance

    distance.increase_approach_level()
    return distance


def _get_non_root_distance(
    result: ExecutionResult, branch: bcg.Branch, value: bool
) -> ControlFlowDistance:
    assert (
        branch.predicate_id is not None
    ), "Cannot compute distance for branch without predicate ID"
    trace = result.execution_trace
    tracer = bp.INSTANCE.tracer

    distance = ControlFlowDistance()
    # Code Object was not executed, simply use diameter as upper bound.
    if branch.code_object_id not in trace.executed_code_objects:
        distance.approach_level = (
            tracer.get_known_data()
            .existing_code_objects[branch.code_object_id]
            .cfg.diameter
        )
        return distance

    # Predicate was executed, simply use distance of correct branch.
    if branch.predicate_id in trace.executed_predicates:
        if value:
            branch_distance = _predicate_fitness(
                branch.predicate_id, trace.true_distances
            )
        else:
            branch_distance = _predicate_fitness(
                branch.predicate_id, trace.false_distances
            )
        distance.branch_distance = branch_distance
        return distance

    cdg = tracer.get_known_data().existing_code_objects[branch.code_object_id].cdg
    target_node = _get_node_with_predicate_id(cdg, branch.predicate_id)

    distance.approach_level = (
        tracer.get_known_data()
        .existing_code_objects[branch.code_object_id]
        .cfg.diameter
    )
    for node in [
        node
        for node in cdg.nodes
        if node.predicate_id is not None
        and node.predicate_id in trace.executed_predicates
    ]:
        try:
            candidate = ControlFlowDistance()
            candidate.approach_level = nx.shortest_path_length(
                cdg.graph, node, target_node
            )
            # Predicate was executed but did not lead to execution of desired predicate
            # So the remaining branch distance to the true or false branch is
            # the desired distance, right?
            # One of them has to be zero, so we can simply add them.
            assert node.predicate_id is not None
            candidate.branch_distance = _predicate_fitness(
                node.predicate_id, trace.true_distances
            ) + _predicate_fitness(node.predicate_id, trace.false_distances)
            distance = min(distance, candidate)
        except nx.NetworkXNoPath:
            # No path from node to target.
            pass

    return distance


def _get_node_with_predicate_id(
    cdg: ControlDependenceGraph, predicate_id: int
) -> ProgramGraphNode:
    cdg_nodes = [node for node in cdg.nodes if node.predicate_id == predicate_id]
    assert len(cdg_nodes) == 1
    return cdg_nodes.pop()


def _predicate_fitness(predicate: int, branch_distances: Dict[int, float]) -> float:
    if predicate in branch_distances and branch_distances[predicate] == 0.0:
        return 0.0
    if predicate not in branch_distances:
        return inf
    return normalise(branch_distances[predicate])
