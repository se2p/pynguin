#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factory for branch-coverage fitness functions."""
from typing import List

import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchcoveragetestfitness as bctf
import pynguin.coverage.branch.branchpool as bp
import pynguin.ga.fitnessfunction as ff
import pynguin.testcase.execution.testcaseexecutor as tce


# pylint: disable=too-few-public-methods
class BranchCoverageFactory:
    """A factory class for branch-coverage fitness functions."""

    def __init__(self, executor: tce.TestCaseExecutor) -> None:
        self._executor = executor

    def get_coverage_goals(self) -> List[ff.FitnessFunction]:
        """Computes the coverage goals, i.e., the fitness functions for each branch.

        Returns:
            A list of fitness functions
        """
        return self._compute_coverage_goals()

    def _compute_coverage_goals(self) -> List[ff.FitnessFunction]:
        goals: List[ff.FitnessFunction] = []
        branch_pool = bp.INSTANCE

        # Branchless methods
        for function_name in branch_pool.branchless_functions:
            goals.append(self._create_root_branch_test_fitness(function_name))

        # Branches
        for branch in branch_pool.all_branches:
            goals.append(self._create_branch_coverage_test_fitness(branch, True))
            goals.append(self._create_branch_coverage_test_fitness(branch, False))

        return goals

    def _create_root_branch_test_fitness(
        self, function_name: str
    ) -> ff.FitnessFunction:
        return bctf.BranchCoverageTestFitness(
            self._executor,
            bcg.BranchCoverageGoal(value=True, function_name=function_name),
        )

    def _create_branch_coverage_test_fitness(
        self, branch: bcg.Branch, branch_expression_value: bool
    ) -> ff.FitnessFunction:
        return bctf.BranchCoverageTestFitness(
            self._executor,
            bcg.BranchCoverageGoal(branch=branch, value=branch_expression_value),
        )
