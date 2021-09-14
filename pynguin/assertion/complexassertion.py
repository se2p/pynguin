#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a object assertion."""
from __future__ import annotations

from typing import Dict

import pynguin.assertion.variableassertion as va
import pynguin.testcase.variable.variablereference as vr
from pynguin.assertion import assertionvisitor as av


class ComplexAssertion(va.VariableAssertion):
    """An assertion for complex values such as objects or collections."""

    def accept(self, visitor: av.AssertionVisitor) -> None:
        visitor.visit_complex_assertion(self)

    def clone(
        self, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> ComplexAssertion:
        return ComplexAssertion(self.source.clone(memo), self.value)
