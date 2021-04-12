#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements a fitness function for test cases."""
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstracttestcasefitnessfunction as atcff
import pynguin.ga.testcasechromosome as tcc
from pynguin.coverage.branch.branchcoveragegoal import AbstractBranchCoverageGoal
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


class BranchCoverageTestFitness(atcff.AbstractTestCaseFitnessFunction):
    """A branch coverage fitness implementation for test cases."""

    def __init__(self, executor: TestCaseExecutor, goal: AbstractBranchCoverageGoal):
        super().__init__(executor)
        self._goal = goal
        self._is_covered = False

    def compute_fitness_values(
        self, individual: tcc.TestCaseChromosome
    ) -> ff.FitnessValues:
        result = self._run_test_case_chromosome(individual)

        return ff.FitnessValues(fitness=self._get_fitness(result), coverage=0.0)

    def is_maximisation_function(self) -> bool:
        return False

    def _get_fitness(self, result: ExecutionResult) -> float:
        distance = self._goal.get_distance(result, self._executor.tracer)
        fitness = distance.get_resulting_branch_fitness()

        if fitness == 0.0:
            self._is_covered = True

        return fitness

    def __str__(self) -> str:
        return (
            f"BranchCoverageTestFitness for {self._goal} (covered: {self._is_covered})"
        )

    def __repr__(self) -> str:
        return (
            f"BranchCoverageTestFitness(executor={self._executor}, "
            f"goal={self._goal})"
        )

    @property
    def goal(self):
        """Provides the branch-coverage goal of this fitness function.

        Returns:
            The attached branch-coverage goal
        """
        return self._goal

    @property
    def is_covered(self) -> bool:
        """Whether or not this fitness goal is covered.

        Returns:
            Whether or not this fitness goal is covered
        """
        return self._is_covered
