#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Handles the execution of testcases during the the mutation-analysis approach."""
from types import ModuleType
from typing import List

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.configuration as config
import pynguin.testcase.execution as ex
import pynguin.testcase.testcase as tc


class MutationAnalysisExecution:  # pylint: disable=too-few-public-methods
    """Class for handling the execution on the mutation analysis approach."""

    def __init__(
        self,
        executor: ex.TestCaseExecutor,
        mutated_modules: List[ModuleType],
        storage: cs.CollectorStorage,
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
        self._storage = storage

    def execute(self, test_cases: List[tc.TestCase]) -> None:
        """Executes the given list of test cases first on the not mutated module and
        then on every mutated module.
        """
        self._execute_on_default(test_cases)

        for mutated_module in self._mutated_modules:
            self._execute_on_mutated(test_cases, mutated_module)

    def _execute_on_default(self, test_cases: List[tc.TestCase]) -> None:
        # Expand the storage by one
        self._storage.append_execution()
        for test_case in test_cases:
            # Reload the module under test
            self._executor.module_provider.reload_module(
                config.configuration.module_name
            )
            # Execute
            self._executor.execute(test_case)

    def _execute_on_mutated(
        self, test_cases: List[tc.TestCase], mutated_module: ModuleType
    ) -> None:
        # Hand the mutated module over to the mutation module observer
        # which injects it to the execution context
        self._executor.module_provider.add_mutated_version(
            module_name=config.configuration.module_name, mutated_module=mutated_module
        )

        # Execute the tests
        self._execute_on_default(test_cases)
