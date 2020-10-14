#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an assertion generator"""

import pynguin.assertion.noneassertionobserver as nao
import pynguin.assertion.primitiveassertionobserver as pao
import pynguin.testcase.execution.testcaseexecutor as ex
import pynguin.testcase.testcase as tc


# pylint:disable=too-few-public-methods
class AssertionGenerator:
    """A simple assertion generator.
    Creates all regression assertions."""

    def __init__(self, executor: ex.TestCaseExecutor):
        """
        Create new assertion generator.

        Args:
            executor: the executor that will be used to execute the test cases.
        """
        self._executor = executor
        self._executor.add_observer(pao.PrimitiveTraceObserver())
        self._executor.add_observer(nao.NoneTraceObserver())

    def add_assertions(self, test_case: tc.TestCase) -> None:
        """Adds assertions to the given test case.

        Args:
            test_case: the test case for which assertions should be generated.
        """
        result = self._executor.execute(test_case)
        for _, trace in result.output_traces.items():
            trace.add_assertions(test_case)
