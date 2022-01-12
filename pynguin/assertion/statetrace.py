#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an output trace."""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ordered_set import OrderedSet

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.assertion.statetraceentry as ote
    import pynguin.testcase.statement as stmt


class StateTrace:
    """Stores the states that have been observed during execution."""

    def __init__(self) -> None:
        """Create new output trace."""
        # One entry per statement, i.e., the states after executing that statement.
        self._trace: dict[int, OrderedSet[ote.StateTraceEntry]] = defaultdict(
            OrderedSet
        )

    def add_entry(self, position: int, entry: ote.StateTraceEntry) -> None:
        """Add an entry to this trace.

        Args:
            position: the position of the statement after whose execution the
                state is observed.
            entry: the entry describing the made assertion.
        """
        self._trace[position].add(entry)

    def get_assertions(self, statement: stmt.Statement) -> OrderedSet[ass.Assertion]:
        """Get all assertions contained within this trace for the given statement.

        Args:
            statement: the statement for which all recorded assertions
                should be generated.

        Returns:
            All assertions in this trace for the given statement.
        """
        position = statement.get_position()
        assertions = OrderedSet()
        if position in self._trace:
            for entry in self._trace[position]:
                assertions.update(entry.get_assertions())
        return assertions

    def clear(self) -> None:
        """Clear this trace."""
        self._trace.clear()

    def clone(self) -> StateTrace:
        """Clone this trace.

        Returns:
            a clone of this trace.
        """
        copy: StateTrace = StateTrace()
        for stmt_key, stmt_value in self._trace.items():
            copy._trace[stmt_key] = OrderedSet()
            for entry in stmt_value:
                copy._trace[stmt_key].add(entry.clone())
        return copy
