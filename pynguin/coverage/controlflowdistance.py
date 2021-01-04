#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a data class to track the control-flow distances."""
from __future__ import annotations

from functools import total_ordering
from typing import Any, Dict, Optional, Set

import networkx as nx

import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchpool as bp
from pynguin.ga.fitnessfunctions.fitness_utilities import normalise
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontracer import CodeObjectMetaData


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
    function_name: str,
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
        return _get_root_distance(result, function_name)

    if value:
        if branch.actual_branch_id in result.execution_trace.true_distances:
            return ControlFlowDistance(0, 0.0)
    else:
        if branch.actual_branch_id in result.execution_trace.false_distances:
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
    if value:
        branch_distance = _predicate_fitness(branch.predicate_id, trace.true_distances)
    else:
        branch_distance = _predicate_fitness(branch.predicate_id, trace.false_distances)
    distance.branch_distance = branch_distance

    existing_code_objects: Dict[
        int, CodeObjectMetaData
    ] = tracer.get_known_data().existing_code_objects
    executed_code_objects: Set[int] = tracer.get_trace().executed_code_objects
    branch_code_object_id = branch.code_object_id
    if branch_code_object_id not in executed_code_objects:
        distance.approach_level = _approach_level(
            branch_code_object_id, existing_code_objects, executed_code_objects
        )

    return distance


def _predicate_fitness(predicate: int, branch_distances: Dict[int, float]) -> float:
    if predicate in branch_distances and branch_distances[predicate] == 0.0:
        return 0.0
    return normalise(branch_distances[predicate])


def _approach_level(
    branch_code_object_id: int,
    existing_code_objects: Dict[int, CodeObjectMetaData],
    executed_code_objects: Set[int],
) -> int:
    # Use the maximum CFG diameter as approach level, as the real value cannot be
    # larger than this value
    approach_level = max([meta.cfg.diameter for meta in existing_code_objects.values()])
    if branch_code_object_id not in executed_code_objects:
        return approach_level

    code_object_meta_data = existing_code_objects[branch_code_object_id]
    control_dependence_graph = code_object_meta_data.cdg
    cdg_nodes = {node.index: node for node in control_dependence_graph.nodes}
    branch_cdg_node = cdg_nodes[branch_code_object_id]
    for executed_code_object in executed_code_objects:
        # Search minimal distance between the node of this branch and the executed
        # branches in the control-dependence graph to know how far the “best”
        # execution was away from the target branch node.
        code_object_cdg_node = cdg_nodes[executed_code_object]
        length = nx.shortest_path_length(
            control_dependence_graph,
            source=branch_cdg_node,
            target=code_object_cdg_node,
        )
        approach_level = min(length, approach_level)

    return approach_level
