#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a pool to hold all available information concerning branches."""
import logging
from typing import Dict, Iterable, List, Optional, Set, Tuple

from bytecode import BasicBlock, Instr

import pynguin.coverage.branch.branchcoveragegoal as bcg
from pynguin.testcase.execution.executiontracer import ExecutionTracer


# pylint: disable=too-many-arguments
class _BranchPool:
    """Holds all available information concerning branches."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._branch_counter: int = 0
        self._branch_id_map: Dict[int, bcg.Branch] = {}
        self._branchless_functions: Dict[str, int] = {}
        self._registered_normal_branches: List[Tuple[BasicBlock, int]] = []
        self._tracer: Optional[ExecutionTracer] = None

    def register_branchless_function(
        self, function_name: str, line_number: int
    ) -> None:
        """Registers a function without branches to the pool.

        Args:
            function_name: The name of the branchless function
            line_number: The starting line number of the function
        """
        self._branchless_functions[function_name] = line_number

    def register_branch(
        self,
        block: BasicBlock,
        code_object_id: int,
        predicate_id: int,
        line_no: int,
        compare_op: Optional[Instr] = None,
    ) -> None:
        """Registers a normal branch in the pool.

        Args:
            block: The basic block of the branch
            code_object_id: The ID of the code object
            predicate_id: The ID of the predicate
            line_no: The starting line number of the basic block
            compare_op: An optional compare instruction of the branch
        """
        if self._is_block_a_registered_normal_branch(block):
            raise ValueError("Basic block already registered as a normal branch")

        self._branch_counter += 1
        self._registered_normal_branches.append((block, self._branch_counter))

        branch = bcg.Branch(
            actual_branch_id=self._branch_counter,
            basic_block=block,
            code_object_id=code_object_id,
            compare_op=compare_op,
            predicate_id=predicate_id,
        )
        self._branch_id_map[self._branch_counter] = branch

        self._logger.info("Branch %d at line %d", self._branch_counter, line_no)

    def clear(self) -> None:
        """Clears all stored branch information."""
        self._branch_counter = 0
        self._branch_id_map.clear()
        self._branchless_functions.clear()
        self._registered_normal_branches.clear()
        self._tracer = None

    @property
    def branchless_functions(self) -> Set[str]:
        """Provides a set of all branchless function's names.

        Returns:
            A set of all branchless function's names
        """
        return set(self._branchless_functions.keys())

    def is_branchless_function(self, function_name: str) -> bool:
        """Returns whether or not a given function name is branchless function.

        Args:
            function_name: The function name to check

        Returns:
            Whether or not it is a branchless function
        """
        return function_name in self._branchless_functions

    def get_num_branchless_functions(self) -> int:
        """Provides the number of branchless functions.

        Returns:
            The number of branchless functions
        """
        return len(self._branchless_functions)

    def get_branchless_function_line_number(self, function_name: str) -> int:
        """Provides the line number for a branchless function.

        Args:
            function_name: The branchless function's name

        Raises:
            ValueError in case the function is not a branchless one
        """
        if not self.is_branchless_function(function_name):
            raise ValueError(f"No branchless method {function_name} registered")
        return self._branchless_functions[function_name]

    def is_known_as_branch(self, block: BasicBlock) -> bool:
        """Checks whether or not a basic block is known as referring to a branch.

        Args:
            block: The block to check

        Returns:
            Whether or not the block is referring to a branch
        """
        return self._is_block_a_registered_normal_branch(block)

    def get_actual_branch_id_for_normal_branch(self, block: BasicBlock) -> int:
        """Provides the actual branch id for a normal branch.

        Args:
            block: The branch's basic block

        Returns:
            The branch's actual branch ID
        """
        if not self.is_known_as_branch(block):
            raise ValueError("Basic block not registered as a normal branch")
        return self._get_id_for_registered_block(block)

    def get_branch_for_block(self, block: BasicBlock) -> bcg.Branch:
        """Provides the branch object for a basic block.

        Args:
            block: The basic block

        Returns:
            The corresponding branch
        """
        if block is None:
            raise ValueError("None given")
        if not self.is_known_as_branch(block):
            raise ValueError("Expect given block to be known as normal branch")
        return self.get_branch(self._get_id_for_registered_block(block))

    def get_branch(self, branch_id: int) -> bcg.Branch:
        """Provides the branch with a certain ID.

        Args:
            branch_id: The branch ID

        Returns:
            The branch instance
        """
        return self._branch_id_map[branch_id]

    @property
    def all_branches(self) -> Iterable[bcg.Branch]:
        """Provides an iterable of all registered branches.

        Returns:
            An iterable of all registered branches
        """
        return list(self._branch_id_map.values())

    @property
    def branch_counter(self) -> int:
        """Provides the number of all registered branches.

        Returns:
            The number of all registered branches
        """
        return self._branch_counter

    def _is_block_a_registered_normal_branch(self, block: BasicBlock) -> bool:
        for basic_block, _ in self._registered_normal_branches:
            if block == basic_block:
                return True
        return False

    def _get_id_for_registered_block(self, block: BasicBlock) -> int:
        for basic_block, branch_id in self._registered_normal_branches:
            if block == basic_block:
                return branch_id
        raise ValueError("No ID found for block")

    @property
    def tracer(self) -> ExecutionTracer:
        """Provides the execution tracer.

        Returns:
            The execution tracer
        """
        assert self._tracer is not None
        return self._tracer

    @tracer.setter
    def tracer(self, tracer: ExecutionTracer):
        self._tracer = tracer


INSTANCE = _BranchPool()
