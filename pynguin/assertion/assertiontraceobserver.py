#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract observer that can be used to generate assertions."""

from abc import ABC
from typing import Generic, TypeVar

import pynguin.assertion.outputtrace as ot
import pynguin.assertion.outputtraceentry as ote
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executionobserver import ExecutionObserver

# pylint:disable=invalid-name
T = TypeVar("T", bound=ote.OutputTraceEntry)


class AssertionTraceObserver(Generic[T], ExecutionObserver, ABC):
    """Abstract base class for assertion observers.
    Observes the execution of a test case and generates assertions from it."""

    def __init__(self) -> None:
        self._trace: ot.OutputTrace[T] = ot.OutputTrace()

    def clear(self) -> None:
        """Clear the existing gathered trace."""
        self._trace.clear()

    def get_trace(self) -> ot.OutputTrace[T]:
        """Get a copy of the gathered trace.

        Returns:
            A copy of the gathered trace.

        """
        return self._trace.clone()

    def before_test_case_execution(self, test_case: tc.TestCase):
        self.clear()

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: res.ExecutionResult
    ):
        result.add_output_trace(type(self), self.get_trace())
