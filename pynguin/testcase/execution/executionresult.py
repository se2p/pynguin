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


class ExecutionResult:
    """Result of an execution."""

    def __init__(self) -> None:
        self._exceptions: Dict[int, Exception] = {}
        self._branch_coverage = 0.0
        self._fitness: Optional[float] = None
        self._time_stamp: int = time.time_ns()

    @property
    def exceptions(self) -> Dict[int, Exception]:
        """Provide a map of statements indices that threw an exception. """
        return self._exceptions

    @property
    def branch_coverage(self) -> float:
        """Provides the branch coverage that was achieved by this execution."""
        return self._branch_coverage

    @branch_coverage.setter
    def branch_coverage(self, value: float) -> None:
        """Set the achieved branch coverage."""
        self._time_stamp = time.time_ns()
        self._branch_coverage = value

    @property
    def fitness(self) -> Optional[float]:
        """Get the achieved fitness"""
        return self._fitness

    @fitness.setter
    def fitness(self, value: float) -> None:
        """Set the achieved fitness"""
        self._time_stamp = time.time_ns()
        self._fitness = value

    @property
    def time_stamp(self) -> int:
        """Provides the last update time of this result in nano seconds from epoch."""
        return self._time_stamp

    def has_test_exceptions(self) -> bool:
        """
        Returns true if any exceptions were thrown during the execution.
        """
        return bool(self._exceptions)

    def report_new_thrown_exception(self, stmt_idx: int, ex: Exception) -> None:
        """
        Report an exception that was thrown during execution
        :param stmt_idx: the index of the statement, that caused the exception
        :param ex: the exception
        """
        self._exceptions[stmt_idx] = ex

    def __str__(self) -> str:
        return (
            f"ExecutionResult(exceptions: {self._exceptions}, coverage: "
            f"{self._branch_coverage}, fitness: {self._fitness})"
        )

    def __repr__(self) -> str:
        return self.__str__()

    # TODO(fk) traces.
