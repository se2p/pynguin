#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a representation for a branch-coverage goal inside a module under test."""
from dataclasses import dataclass
from types import CodeType
from typing import Any, Optional

from bytecode import BasicBlock, Instr

import pynguin.coverage.controlflowdistance as cfd
from pynguin.testcase.execution.executionresult import ExecutionResult


@dataclass
class Branch:
    """Implements a representation for a branch inside the module under test."""

    actual_branch_id: int
    basic_block: BasicBlock
    code_object_id: int
    compare_op: Optional[Instr]
    predicate_id: Optional[int]
    code_object_data: CodeType


class BranchCoverageGoal:
    """A single branch-coverage goal.

    Either the true/false evaluation of a jump condition, or a method entry
    """

    def __init__(
        self,
        *,
        branch: Optional[Branch] = None,
        value: bool,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> None:
        self._branch = branch
        self._value = value
        self._module_name = module_name
        self._class_name = class_name
        self._function_name = function_name

    @property
    def branch(self) -> Optional[Branch]:
        """Provides the branch of this goal.

        If the value is `None`, this branch represents the root branch of the given
        function, i.e., just call the function.

        Returns:
            The optional branch
        """
        return self._branch

    @property
    def value(self) -> bool:
        """Provides whether to make the branch instruction jump.

        Returns:
            Whether to make the branch instruction jump
        """
        return self._value

    @property
    def module_name(self) -> Optional[str]:
        """Provides the name of the module the branch is declared in.

        Returns:
            The name of the module
        """
        return self._module_name

    @property
    def class_name(self) -> Optional[str]:
        """Provides the name of the class the branch is declared in if any.

        Returns:
            The name of the class if any
        """
        return self._class_name

    @property
    def function_name(self) -> Optional[str]:
        """Provides the name of the function the branch is declared in.

        Returns:
            The name of the function if any
        """
        return self._function_name

    def get_distance(self, result: ExecutionResult) -> cfd.ControlFlowDistance:
        """Computes the control-flow distance of an execution result.

        Args:
            result: The execution result

        Returns:
            The control-flow distance
        """
        distance = cfd.calculate_control_flow_distance(
            result,
            branch=self._branch,
            value=self._value,
            function_name=self._function_name,
        )
        return distance

    def __str__(self) -> str:
        name = f"{self._function_name}:"
        if self._branch:
            name += f" {self._branch}"
            if self._value:
                name += " - True"
            else:
                name += " - False"
        else:
            name += " root-Branch"
        return name

    def __repr__(self) -> str:
        return (
            f"BranchCoverageGoal(branch={self._branch}, value={self._value}, "
            f"module_name={self._module_name}, class_name={self._class_name}, "
            f"function_name={self._function_name})"
        )

    def __hash__(self) -> int:
        prime = 31
        result = 1
        result = prime * result + hash(self._branch) if self._branch else 0
        result = prime * result + hash(self._module_name)
        result = prime * result + hash(self._class_name) if self._class_name else 0
        result = prime * result + hash(self._function_name)
        result = prime * result + 1337 if self._value else 2112
        return result

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, BranchCoverageGoal):
            return False
        return (
            self._branch == other.branch
            and self._value == other.value
            and self._module_name == other.module_name
            and self._class_name == other.class_name
            and self._function_name == other.function_name
        )
