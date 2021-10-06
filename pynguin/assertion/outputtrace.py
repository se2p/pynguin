#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an output trace."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Generic, Set, TypeVar, cast

import pynguin.assertion.outputtraceentry as ote

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.statements.statement as stmt
    import pynguin.testcase.variable.variablereference as vr

# pylint:disable=invalid-name
T = TypeVar("T", bound=ote.OutputTraceEntry)


class OutputTrace(Generic[T]):
    """Store the entries generated during an observation"""

    # TODO(fk) better class name?
    def __init__(self) -> None:
        """Create new output trace."""
        # One Entry per Statement and per Variable
        self._trace: Dict[int, Dict[int, T]] = {}

    def add_entry(
        self, position: int, variable: vr.VariableReference, entry: T
    ) -> None:
        """Add an entry to this trace.

        Args:
            position: the position of the statement where the assertion is made.
            variable: the variable on which the assertion is made.
            entry: the entry describing the made assertion.
        """
        if position not in self._trace:
            self._trace[position] = {}

        self._trace[position][variable.get_statement_position()] = entry

    def get_assertions(self, statement: stmt.Statement) -> Set[ass.Assertion]:
        """Get all assertions contained within this trace for the given statement.

        Args:
            statement: the statement for which all recorded assertions
                       should be generated.

        Returns:
            All assertions in this trace for the given statement.
        """
        position = statement.get_position()
        assertions = set()
        if position in self._trace:
            for _, entry in self._trace[position].items():
                assertions.update(entry.get_assertions())
        return assertions

    def clear(self) -> None:
        """Clear this trace."""
        self._trace.clear()

    def clone(self) -> OutputTrace[T]:
        """Clone this trace.

        Returns:
            a clone of this trace.
        """
        # TODO(fk) check generics really required?
        copy: OutputTrace[T] = OutputTrace()
        for stmt_key, stmt_value in self._trace.items():
            copy._trace[stmt_key] = {}
            for var_key, var_value in stmt_value.items():
                copy._trace[stmt_key][var_key] = cast(T, var_value.clone())
        return copy
