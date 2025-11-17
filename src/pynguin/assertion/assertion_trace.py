#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an output trace."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import TYPE_CHECKING

from pynguin.utils.orderedset import OrderedSet

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.statement as stmt


class AssertionTrace:
    """Stores the states that have been observed during execution."""

    def __init__(self) -> None:
        """Create new assertion trace."""
        # One entry per statement, i.e., the assertions after executing that statement.
        self.trace: dict[int, OrderedSet[ass.Assertion]] = defaultdict(OrderedSet)

    def add_entry(self, position: int, assertion: ass.Assertion) -> None:
        """Add an entry to this trace.

        Args:
            position: the position of the statement after whose execution the
                state is observed.
            assertion: the made assertion.
        """
        self.trace[position].add(assertion)

    def get_assertions(self, statement: stmt.Statement) -> OrderedSet[ass.Assertion]:
        """Get all assertions contained within this trace for the given statement.

        Args:
            statement: the statement for which all recorded assertions
                should be generated.

        Returns:
            All assertions in this trace for the given statement.
        """
        position = statement.get_position()
        if position in self.trace:
            return OrderedSet(self.trace[position])
        return OrderedSet()

    def get_all_assertions(self) -> dict[int, OrderedSet[ass.Assertion]]:
        """Get all generated assertions.

        Returns:
            A dict that maps every statement position to all recorded assertions.

        """
        return dict(self.trace)

    def clear(self) -> None:
        """Clear this trace."""
        self.trace.clear()

    def clone(self) -> AssertionTrace:
        """Clone this trace.

        Returns:
            a clone of this trace.
        """
        copy: AssertionTrace = AssertionTrace()
        for stmt_key, stmt_value in self.trace.items():
            copy.trace[stmt_key] = OrderedSet()
            for entry in stmt_value:
                copy.trace[stmt_key].add(entry)
        return copy

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AssertionTrace) and self.trace == other.trace

    def __hash__(self) -> int:
        return hash(self.trace)


@dataclasses.dataclass
class AssertionVerificationTrace:
    """Trace for assertion verification."""

    # Assertion that did not hold
    failed: dict[int, OrderedSet[int]] = dataclasses.field(
        default_factory=lambda: defaultdict(OrderedSet)
    )
    # Assertion whose execution raised an error
    error: dict[int, OrderedSet[int]] = dataclasses.field(
        default_factory=lambda: defaultdict(OrderedSet)
    )

    def merge(self, other: AssertionVerificationTrace) -> None:
        """Merge another trace into this trace.

        Args:
            other: The other trace

        """
        for pos, assertions in other.failed.items():
            self.failed[pos].update(assertions)
        for pos, assertions in other.error.items():
            self.error[pos].update(assertions)

    def was_violated(self, stmt_idx: int, assertion_idx: int) -> bool:
        """Was the assertion at the given position violated?

        This may happen because the assertion failed or another error occurred.

        Args:
            stmt_idx: The statement index.
            assertion_idx: The assertion index.

        Returns:
            True, if the assertion was violated.
        """
        if stmt_idx in self.failed and assertion_idx in self.failed[stmt_idx]:
            return True
        return bool(stmt_idx in self.error and assertion_idx in self.error[stmt_idx])
