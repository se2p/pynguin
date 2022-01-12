#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract observer that can be used to generate assertions."""
from __future__ import annotations

from abc import ABC
from typing import TypeVar

import pynguin.assertion.statetrace as ot
import pynguin.assertion.statetraceentry as ote
import pynguin.testcase.execution as ex
import pynguin.testcase.testcase as tc

# pylint:disable=invalid-name
T = TypeVar("T", bound=ote.StateTraceEntry)


class AssertionTraceObserver(ex.ExecutionObserver, ABC):
    """Abstract base class for assertion observers.
    Observes the execution of a test case and generates assertions from it."""

    def __init__(self) -> None:
        self._trace: ot.StateTrace = ot.StateTrace()

    def clear(self) -> None:
        """Clear the existing gathered trace."""
        self._trace.clear()

    def get_trace(self) -> ot.StateTrace:
        """Get a copy of the gathered trace.

        Returns:
            A copy of the gathered trace.

        """
        return self._trace.clone()

    def before_test_case_execution(self, test_case: tc.TestCase):
        self.clear()

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ):
        result.add_output_trace(type(self), self.get_trace())
