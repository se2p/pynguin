#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Handles the execution of testcases during the the mutation-analysis approach."""
from types import ModuleType
from typing import List

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.configuration as config
import pynguin.testcase.execution.testcaseexecutor as ex
import pynguin.testcase.testcase as tc
import pynguin.utils.moduleloader as ml


class MutationAnalysisExecution:  # pylint: disable=too-few-public-methods
    """Class for handling the execution on the mutation analysis approach."""

    def __init__(
        self, executor: ex.TestCaseExecutor, mutated_modules: List[ModuleType]
    ):
        """
        Create new collector execution.

        Args:
            executor: the executor that will be used to execute the test cases.
            mutated_modules: list of mutated modules on which the tests should
                             be executed
        """
        self._executor = executor
        self._mutated_modules = mutated_modules

    def execute(self, test_cases: List[tc.TestCase]) -> None:
        """Executes the given list of test cases first on the not mutated module and
        then on every mutated module.
        """
        self._execute_on_default(test_cases)

        for mutated_module in self._mutated_modules:
            self._execute_on_mutated(test_cases, mutated_module)

    def _execute_on_default(self, test_cases: List[tc.TestCase]) -> None:
        # Iterate over all test cases and execute each test case
        for test_case in test_cases:
            ml.ModuleLoader.reload_module(config.configuration.module_name)
            self._executor.execute(test_case)

    def _execute_on_mutated(
        self, test_cases: List[tc.TestCase], mutated_module: ModuleType
    ) -> None:
        # Hand the mutated module over to the mutation module observer
        # which injects it to the execution context
        ml.ModuleLoader.add_mutated_version(
            module_name=config.configuration.module_name, mutated_module=mutated_module
        )

        # Create a new storage slot for the execution on the given mutated module
        cs.CollectorStorage.append_execution()

        # Execute the tests
        self._execute_on_default(test_cases)
