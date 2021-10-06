#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an entry for a primitive assertion."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Set

import pynguin.assertion.outputtraceentry as ote
import pynguin.assertion.primitiveassertion as pas

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.variable.variablereference as vr


class PrimitiveTraceEntry(ote.OutputTraceEntry):
    """An entry for a primitive assertion."""

    def __init__(self, variable: vr.VariableReference, value: Any) -> None:
        self._variable = variable
        self._value = value

    def clone(self) -> PrimitiveTraceEntry:
        return PrimitiveTraceEntry(self._variable, self._value)

    def get_assertions(self) -> Set[ass.Assertion]:
        return {pas.PrimitiveAssertion(self._variable, self._value)}

    def __eq__(self, other):
        return (
            isinstance(other, PrimitiveTraceEntry)
            and self._value == other._value
            and self._variable == other._variable
        )

    def __hash__(self):
        return hash((self._variable, self._value))
