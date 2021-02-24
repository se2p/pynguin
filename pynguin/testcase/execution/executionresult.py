#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides the result of an execution run."""
from typing import Dict, Optional, Type

import pynguin.assertion.outputtrace as ot
from pynguin.testcase.execution.executiontrace import ExecutionTrace


class ExecutionResult:
    """Result of an execution."""

    def __init__(self, timeout: bool = False) -> None:
        self._exceptions: Dict[int, Exception] = {}
        self._output_traces: Dict[Type, ot.OutputTrace] = {}
        self._execution_trace: Optional[ExecutionTrace] = None
        self._timeout = timeout

    @property
    def timeout(self) -> bool:
        """Did a timeout occur during the execution?

        Returns:
            True, if a timeout occurred.
        """
        return self._timeout

    @property
    def exceptions(self) -> Dict[int, Exception]:
        """Provide a map of statements indices that threw an exception.

        Returns:
             A map of statement indices to their raised exception
        """
        return self._exceptions

    @property
    def output_traces(self) -> Dict[Type, ot.OutputTrace]:
        """Provides the gathered output traces.

        Returns:
            the gathered output traces.

        """
        return self._output_traces

    @property
    def execution_trace(self) -> ExecutionTrace:
        """The trace for this execution.

        Returns:
            The execution race
        """
        assert self._execution_trace, "No trace provided"
        return self._execution_trace

    @execution_trace.setter
    def execution_trace(self, trace: ExecutionTrace) -> None:
        """Set new trace.

        Args:
            trace: The new execution trace
        """
        self._execution_trace = trace

    def add_output_trace(self, trace_type: Type, trace: ot.OutputTrace) -> None:
        """Add the given trace to the recorded output traces.

        Args:
            trace_type: the type of trace.
            trace: the trace to store.

        """
        self._output_traces[trace_type] = trace

    def has_test_exceptions(self) -> bool:
        """Returns true if any exceptions were thrown during the execution.

        Returns:
            Whether or not the test has exceptions
        """
        return bool(self._exceptions)

    def report_new_thrown_exception(self, stmt_idx: int, ex: Exception) -> None:
        """Report an exception that was thrown during execution.

        Args:
            stmt_idx: the index of the statement, that caused the exception
            ex: the exception
        """
        self._exceptions[stmt_idx] = ex

    def get_first_position_of_thrown_exception(self) -> Optional[int]:
        """Provide the index of the first thrown exception or None.

        Returns:
            The index of the first thrown exception, if any
        """
        if self.has_test_exceptions():
            return min(self._exceptions.keys())
        return None

    def __str__(self) -> str:
        return (
            f"ExecutionResult(exceptions: {self._exceptions}, "
            + f"trace: {self._execution_trace})"
        )

    def __repr__(self) -> str:
        return self.__str__()
