#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an entry for none assertions"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.assertion.noneassertion as nas
import pynguin.assertion.statetraceentry as ote

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.variablereference as vr


class NoneTraceEntry(ote.StateTraceEntry):
    """An Entry for none assertions"""

    def __init__(self, variable: vr.VariableReference, is_none: bool) -> None:
        """Create new none trace entry.

        Args:
            variable: the variable whose none-ness is asserted.
            is_none: is the variable none?
        """
        self._variable = variable
        self._is_none: bool = is_none

    def clone(self) -> NoneTraceEntry:
        return NoneTraceEntry(self._variable, self._is_none)

    def get_assertions(self) -> set[ass.Assertion]:
        return {nas.NoneAssertion(self._variable, self._is_none)}

    def __eq__(self, other):
        return (
            isinstance(other, NoneTraceEntry)
            and self._is_none == other._is_none
            and self._variable == other._variable
        )

    def __hash__(self):
        return hash((self._variable, self._is_none))
