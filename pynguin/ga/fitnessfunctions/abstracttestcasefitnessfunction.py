#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract fitness function for test suites."""
from abc import ABCMeta

import pynguin.ga.fitnessfunction as ff
from pynguin.testcase.execution.executionresult import ExecutionResult


# pylint: disable=abstract-method
class AbstractTestCaseFitnessFunction(ff.FitnessFunction, metaclass=ABCMeta):
    """Abstract fitness function for test case chromosomes."""

    def _run_test_case_chromosome(self, individual) -> ExecutionResult:
        """Runs a test suite and updates the execution results for
        all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        if individual.has_changed() or individual.get_last_execution_result() is None:
            individual.set_last_execution_result(
                self._executor.execute(individual.test_case)
            )
            individual.set_changed(False)
        result = individual.get_last_execution_result()
        assert result is not None
        return result
