#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an output trace."""
from __future__ import annotations

from typing import Dict, Generic, TypeVar, cast

import pynguin.assertion.outputtraceentry as ote
import pynguin.configuration as config
import pynguin.testcase.testcase as tc  # pylint:disable=cyclic-import
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

    def add_assertions(self, test_case: tc.TestCase) -> None:
        """Add all assertions contained within this trace to the given test case.

        Args:
            test_case: the test case to which we add the observed assertions.

        """
        for statement, value in self._trace.items():
            for _, entry in value.items():
                for assertion in entry.get_assertions():
                    if (
                        test_case.size_with_assertions()
                        >= config.INSTANCE.max_length_test_case
                    ):
                        return
                    test_case.get_statement(statement).add_assertion(assertion)

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
