#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an observer that can be used to calculate the checked lines of a test."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pynguin.testcase.execution as ex
import pynguin.testcase.testcase as tc

if TYPE_CHECKING:
    from pynguin.slicer.dynamicslicer import SlicingCriterion

# Note: checked-coverage / slicing per-statement instrumentation was not yet ported
# to the per-statement libcst execution model (see Stage 3 of the per-statement
# execution refactor). The statement hooks below are therefore inert no-ops; only
# the (already empty) checked-lines trace is populated so downstream consumers keep
# working.


class RemoteStatementSlicingObserver(ex.RemoteExecutionObserver):
    """Remote observer that updates the checked lines of a testcase.

    Currently inert: real per-statement slicing has not been restored yet
    under the libcst-based per-statement execution model.
    """

    _STORE_INSTRUCTION_OFFSET = 2

    class RemoteSlicingLocalState(threading.local):
        """Stores thread-local slicing data."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.slicing_criteria: dict[int, SlicingCriterion] = {}

    def __init__(self) -> None:
        """Initializes the observer."""
        super().__init__()
        self._slicing_local_state = RemoteStatementSlicingObserver.RemoteSlicingLocalState()

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_test_case_execution(
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ) -> None:
        """Not used.

        Args:
            executor: Not used
            test_case: Not used
            result: Not used
        """
