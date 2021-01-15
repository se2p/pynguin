#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements a fitness function for test cases."""
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstracttestcasefitnessfunction as atcff
import pynguin.ga.testcasechromosome as tcc
from pynguin.coverage.branch.branchcoveragegoal import BranchCoverageGoal
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


class BranchCoverageTestFitness(atcff.AbstractTestCaseFitnessFunction):
    """A branch coverage fitness implementation for test cases."""

    def __init__(self, executor: TestCaseExecutor, goal: BranchCoverageGoal):
        super().__init__(executor)
        self._goal = goal

    def compute_fitness_values(
        self, individual: tcc.TestCaseChromosome
    ) -> ff.FitnessValues:
        result = self._run_test_case_chromosome(individual)

        return ff.FitnessValues(fitness=self._get_fitness(result), coverage=0.0)

    def is_maximisation_function(self) -> bool:
        return False

    def _get_fitness(self, result: ExecutionResult) -> float:
        distance = self._goal.get_distance(result)
        fitness = distance.get_resulting_branch_fitness()

        if fitness == 0.0:
            # TODO mark goal as covered?
            pass

        return fitness

    def __str__(self) -> str:
        return f"BranchCoverageTestFitness for {self._goal}"

    def __repr__(self) -> str:
        return (
            f"BranchCoverageTestFitness(executor={self._executor}, "
            f"goal={self._goal})"
        )
