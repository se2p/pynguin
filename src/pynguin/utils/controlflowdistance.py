#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
"""Provides a data class to track the control-flow distances."""

from __future__ import annotations

from functools import total_ordering
from math import inf
from typing import TYPE_CHECKING

import networkx as nx

import pynguin.ga.computations as ff


if TYPE_CHECKING:
    from pynguin.analyses.controlflow import ControlDependenceGraph
    from pynguin.analyses.controlflow import ProgramGraphNode
    from pynguin.instrumentation.tracer import ExecutionTracer
    from pynguin.testcase.execution import ExecutionResult


@total_ordering
class ControlFlowDistance:
    """Tracks control-flow distances."""

    def __init__(self, approach_level: int = 0, branch_distance: float = 0.0) -> None:
        """Initializes the control-flow distance.

        Args:
            approach_level: The approach level
            branch_distance: The branch distance
        """
        assert (  # noqa: PT018
            approach_level >= 0 and branch_distance >= 0.0
        ), "Expect approach_level and branch_distance to be non-negative"
        self._approach_level = approach_level
        self._branch_distance = branch_distance

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, ControlFlowDistance):
            return False
        return (self._approach_level, self._branch_distance) == (
            other.approach_level,
            other.branch_distance,
        )

    def __hash__(self) -> int:
        return hash((self._approach_level, self._branch_distance))

    def __lt__(self, other: ControlFlowDistance) -> bool:
        if not isinstance(other, ControlFlowDistance):
            raise TypeError(
                "'<' not supported between instances of 'ControlFlowDistance' and '%s'",
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
        return self._approach_level + ff.normalise(self._branch_distance)

    def __str__(self) -> str:
        return f"approach = {self._approach_level}, branch distance = {self._branch_distance}"

    def __repr__(self) -> str:
        return (
            f"ControlFlowDistance(approach_level={self._approach_level}, "
            f"branch_distance={self._branch_distance})"
        )


def get_root_control_flow_distance(
    result: ExecutionResult, code_object_id: int, tracer: ExecutionTracer
) -> ControlFlowDistance:
    """Computes the control flow distance for a root branch.

    Args:
        result: the execution result.
        code_object_id: The code object id for which we want to get the root distance.
        tracer: the execution tracer

    Returns:
        The control flow distance, (0.0, 0.0) if it was executed, otherwise (1.0, 0.0)
    """
    assert code_object_id in tracer.get_subject_properties().branch_less_code_objects

    distance = ControlFlowDistance()
    if code_object_id in result.execution_trace.executed_code_objects:
        # The code object was executed by the execution
        return distance

    distance.increase_approach_level()
    return distance


def get_non_root_control_flow_distance(
    result: ExecutionResult,
    predicate_id: int,
    value: bool,  # noqa: FBT001
    tracer: ExecutionTracer,
) -> ControlFlowDistance:
    """Computes the control flow distance for a predicate.

    Args:
        result: the execution result.
        predicate_id: The predicate id for which we want to get the root distance.
        value: compute distance to the true or the false branch?
        tracer: the execution tracer

    Returns:
        The control flow distance.
    """
    trace = result.execution_trace
    code_object_id = (
        tracer.get_subject_properties().existing_predicates[predicate_id].code_object_id
    )

    distance = ControlFlowDistance()
    # Code Object was not executed, simply use diameter as upper bound.
    if code_object_id not in trace.executed_code_objects:
        distance.approach_level = (
            tracer.get_subject_properties().existing_code_objects[code_object_id].cfg.diameter
        )
        return distance

    # Predicate was executed, simply use distance of correct branch.
    if predicate_id in trace.executed_predicates:
        if value:
            branch_distance = _predicate_fitness(predicate_id, trace.true_distances)
        else:
            branch_distance = _predicate_fitness(predicate_id, trace.false_distances)
        distance.branch_distance = branch_distance
        return distance

    cdg = tracer.get_subject_properties().existing_code_objects[code_object_id].cdg
    target_node = _get_node_with_predicate_id(cdg, predicate_id)

    # Choose diameter as upper bound
    distance.approach_level = (
        tracer.get_subject_properties().existing_code_objects[code_object_id].cfg.diameter
    )

    # We check for the closest predicate that was executed and compute the approach
    # level as the length of the path from such a predicate node to the desired
    # predicate node.
    for node in [
        node
        for node in cdg.nodes
        if node.predicate_id is not None and node.predicate_id in trace.executed_predicates
    ]:
        try:
            candidate = ControlFlowDistance()
            candidate.approach_level = nx.shortest_path_length(cdg.graph, node, target_node)
            # Predicate was executed but did not lead to execution of desired predicate
            # So the remaining branch distance to the true or false branch is
            # the desired distance, right?
            # One of them has to be zero, so we can simply add them.
            assert node.predicate_id is not None
            candidate.branch_distance = _predicate_fitness(
                node.predicate_id, trace.true_distances
            ) + _predicate_fitness(node.predicate_id, trace.false_distances)
            distance = min(distance, candidate)
        except nx.NetworkXNoPath:  # noqa: PERF203
            # No path from node to target.
            pass

    return distance


def _get_node_with_predicate_id(cdg: ControlDependenceGraph, predicate_id: int) -> ProgramGraphNode:
    cdg_nodes = [node for node in cdg.nodes if node.predicate_id == predicate_id]
    assert len(cdg_nodes) == 1
    return cdg_nodes.pop()


def _predicate_fitness(predicate: int, branch_distances: dict[int, float]) -> float:
    return branch_distances.get(predicate, inf)
