#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a none assertion."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict

import pynguin.assertion.variableassertion as va

if TYPE_CHECKING:
    import pynguin.testcase.variablereference as vr
    from pynguin.assertion import assertionvisitor as av


class NoneAssertion(va.VariableAssertion):
    """An assertion of the None-ness of a variable."""

    def accept(self, visitor: av.AssertionVisitor) -> None:
        visitor.visit_none_assertion(self)

    def clone(
        self, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> NoneAssertion:
        return NoneAssertion(self.source.clone(memo), self.value)
