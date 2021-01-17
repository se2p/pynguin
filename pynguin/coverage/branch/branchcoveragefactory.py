#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factory for branch-coverage fitness functions."""
from typing import List

import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchcoveragetestfitness as bctf
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
        tracer = self._executor.tracer

        # Branch-less code objects
        for code_object_id in tracer.get_known_data().branch_less_code_objects:
            goals.append(self._create_root_branch_test_fitness(code_object_id))

        # Branches
        for predicate_id in tracer.get_known_data().existing_predicates:
            goals.append(self._create_branch_coverage_test_fitness(predicate_id, True))
            goals.append(self._create_branch_coverage_test_fitness(predicate_id, False))

        return goals

    def _create_root_branch_test_fitness(
        self, code_object_id: int
    ) -> ff.FitnessFunction:
        return bctf.BranchCoverageTestFitness(
            self._executor,
            bcg.RootBranchCoverageGoal(code_object_id),
        )

    def _create_branch_coverage_test_fitness(
        self, predicate_id: int, branch_expression_value: bool
    ) -> ff.FitnessFunction:
        return bctf.BranchCoverageTestFitness(
            self._executor,
            bcg.NonRootBranchCoverageGoal(predicate_id, branch_expression_value),
        )
