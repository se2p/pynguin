# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides the result of an execution run."""
import time
from typing import Dict, Optional

from pynguin.testcase.execution.executiontrace import ExecutionTrace


class ExecutionResult:
    """Result of an execution."""

    def __init__(self) -> None:
        self._exceptions: Dict[int, Exception] = {}
        self._time_stamp: int = time.time_ns()
        self._execution_trace: Optional[ExecutionTrace] = None

    @property
    def exceptions(self) -> Dict[int, Exception]:
        """Provide a map of statements indices that threw an exception.

        Returns:
             A map of statement indices to their raised exception
        """
        return self._exceptions

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
        self._time_stamp = time.time_ns()

    @property
    def time_stamp(self) -> int:
        """Provides the last update time of this result in nano seconds from epoch.

        Returns:
            The last update time
        """
        return self._time_stamp

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
            f"trace: {self._execution_trace})"
        )

    def __repr__(self) -> str:
        return self.__str__()
