#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract fitness function for test suites."""
from abc import ABCMeta
from typing import List

import pynguin.ga.fitnessfunction as ff
from pynguin.testcase.execution.executionresult import ExecutionResult


# pylint: disable=abstract-method
class AbstractTestSuiteFitnessFunction(ff.FitnessFunction, metaclass=ABCMeta):
    """Abstract fitness function for test suite chromosomes."""

    def _run_test_suite_chromosome(self, individual) -> List[ExecutionResult]:
        """Runs a test suite and updates the execution results for
        all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        results: List[ExecutionResult] = []
        for test_case_chromosome in individual.test_case_chromosomes:
            if (
                test_case_chromosome.has_changed()
                or test_case_chromosome.get_last_execution_result() is None
            ):
                test_case_chromosome.set_last_execution_result(
                    self._executor.execute(test_case_chromosome.test_case)
                )
                test_case_chromosome.set_changed(False)
                test_case_chromosome.invalidate_fitness_values()
            result = test_case_chromosome.get_last_execution_result()
            assert result is not None
            results.append(result)
        return results
