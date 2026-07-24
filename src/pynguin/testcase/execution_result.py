#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Contains the result representation of a test execution."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, TypeVar

import pynguin.assertion.assertion_trace as at
from pynguin.instrumentation.tracer import ExecutionTrace

if TYPE_CHECKING:
    import pynguin.utils.typetracing as tt
    from pynguin.analyses.typesystem import ProperType

T = TypeVar("T")


@dataclasses.dataclass
class ExecutionResult:
    """Result of an execution."""

    timeout: bool = False
    exceptions: dict[int, BaseException] = dataclasses.field(default_factory=dict, init=False)
    assertion_trace: at.AssertionTrace = dataclasses.field(
        default_factory=at.AssertionTrace, init=False
    )
    assertion_verification_trace: at.AssertionVerificationTrace = dataclasses.field(
        default_factory=at.AssertionVerificationTrace, init=False
    )
    execution_trace: ExecutionTrace = dataclasses.field(default_factory=ExecutionTrace, init=False)

    # Observation of return types.
    raw_return_types: dict[int, type] = dataclasses.field(default_factory=dict, init=False)
    raw_return_type_generic_args: dict[int, tuple[type, ...]] = dataclasses.field(
        default_factory=dict, init=False
    )
    # Observed return types converted to proper types.
    proper_return_type_trace: dict[int, ProperType] = dataclasses.field(
        default_factory=dict, init=False
    )

    proxy_knowledge: dict[tuple[int, str], tt.UsageTraceNode] = dataclasses.field(
        default_factory=dict, init=False
    )

    num_executed_statements: int = dataclasses.field(default=0, init=False)

    def has_test_exceptions(self) -> bool:
        """Returns true if any exceptions were thrown during the execution.

        Returns:
            Whether the test has exceptions
        """
        return bool(self.exceptions)

    def report_new_thrown_exception(self, stmt_idx: int, ex: BaseException) -> None:
        """Report an exception that was thrown during execution.

        Args:
            stmt_idx: the index of the statement, that caused the exception
            ex: the exception
        """
        self.exceptions[stmt_idx] = ex

    def get_first_position_of_thrown_exception(self) -> int | None:
        """Provide the index of the first thrown exception or None.

        Returns:
            The index of the first thrown exception, if any
        """
        if self.has_test_exceptions():
            return min(self.exceptions.keys())
        return None

    def delete_statement_data(self, deleted_statements: set[int]) -> None:
        """Delete statements at given indices.

        It may happen that the test case is modified after execution, for example,
        by removing unused primitives. We have to update the execution result to reflect
        this, otherwise the indexes maybe wrong.

        Args:
            deleted_statements: The indexes of the deleted statements
        """
        self.raw_return_types = ExecutionResult.shift_dict(
            self.raw_return_types, deleted_statements
        )
        self.raw_return_type_generic_args = ExecutionResult.shift_dict(
            self.raw_return_type_generic_args, deleted_statements
        )
        self.proper_return_type_trace = ExecutionResult.shift_dict(
            self.proper_return_type_trace, deleted_statements
        )
        self.exceptions = ExecutionResult.shift_dict(self.exceptions, deleted_statements)

    @staticmethod
    def shift_dict(to_shift: dict[int, T], deleted_indexes: set[int]) -> dict[int, T]:
        """Shifts the entries in the given dictionary.

        Compute the entries' new positions after the given statements were deleted.

        Args:
            to_shift: The dict to shift
            deleted_indexes: A set of deleted statement indexes.

        Returns:
            The shifted dict
        """
        # Count how many statements were deleted up to a given point
        shifts = {}
        delta = 0
        for idx in range(max(to_shift.keys(), default=0) + 1):
            if idx in deleted_indexes:
                delta += 1
            shifts[idx] = delta

        # Shift all indexes accordingly
        shifted = {}
        for stmt_idx, value in to_shift.items():
            if stmt_idx not in deleted_indexes:
                shifted[stmt_idx - shifts[stmt_idx]] = value
        return shifted

    def __str__(self) -> str:
        return f"ExecutionResult(exceptions: {self.exceptions}, trace: {self.execution_trace})"

    def __repr__(self) -> str:
        return str(self)
