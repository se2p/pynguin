#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a representation for a branch-coverage goal inside a module under test."""
from abc import abstractmethod
from typing import Any

import pynguin.coverage.controlflowdistance as cfd
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontracer import ExecutionTracer


# pylint: disable=too-few-public-methods
class AbstractBranchCoverageGoal:
    """Abstract base class for branch coverage goal."""

    @abstractmethod
    def get_distance(
        self, result: ExecutionResult, tracer: ExecutionTracer
    ) -> cfd.ControlFlowDistance:
        """Computes the control-flow distance of an execution result.

        Args:
            result: The execution result
            tracer: The execution tracer

        Returns:
            The control-flow distance
        """


class NonRootBranchCoverageGoal(AbstractBranchCoverageGoal):
    """A single branch-coverage goal.

    The true/false evaluation of a jump condition.
    """

    def __init__(self, predicate_id: int, value: bool) -> None:
        self._predicate_id = predicate_id
        self._value = value

    @property
    def predicate_id(self) -> int:
        """Provides the predicate id of this goal.

        Returns:
            The predicate id
        """
        return self._predicate_id

    @property
    def value(self) -> bool:
        """Provides whether to make the branch instruction jump.

        Returns:
            Whether to make the branch instruction jump
        """
        return self._value

    def get_distance(
        self, result: ExecutionResult, tracer: ExecutionTracer
    ) -> cfd.ControlFlowDistance:
        return cfd.get_non_root_control_flow_distance(
            result, self._predicate_id, self._value, tracer
        )

    def __str__(self) -> str:
        return f"{self._predicate_id} - {self._value}"

    def __repr__(self) -> str:
        return (
            f"NonRootBranchCoverageGoal(branch={self._predicate_id}, "
            f"value={self._value})"
        )

    def __hash__(self) -> int:
        prime = 31
        result = 1
        result = prime * result + self._predicate_id
        result = prime * result + 1337 if self._value else 2112
        return result

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, NonRootBranchCoverageGoal):
            return False
        return self.predicate_id == other.predicate_id and self._value == other.value


class RootBranchCoverageGoal(AbstractBranchCoverageGoal):
    """A single branch-coverage goal.

    Entry into a code object without branches.
    """

    def __init__(self, code_object_id: int) -> None:
        self._code_object_id = code_object_id

    @property
    def code_object_id(self) -> int:
        """Provides the id of the code object whose entry is the goal.

        Returns:
            The id of the code object.
        """
        return self._code_object_id

    def get_distance(
        self, result: ExecutionResult, tracer: ExecutionTracer
    ) -> cfd.ControlFlowDistance:
        return cfd.get_root_control_flow_distance(result, self._code_object_id, tracer)

    def __str__(self) -> str:
        return f"Root-branch for Code-Object: {self._code_object_id}"

    def __repr__(self) -> str:
        return f"RootBranchCoverageGoal({self._code_object_id})"

    def __hash__(self) -> int:
        return 31 + self._code_object_id

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, RootBranchCoverageGoal):
            return False
        return self._code_object_id == other._code_object_id
