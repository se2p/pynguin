#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a object assertion."""
from __future__ import annotations

from typing import Dict

import pynguin.assertion.variableassertion as va
import pynguin.testcase.variablereference as vr
from pynguin.assertion import assertionvisitor as av


class ComplexAssertion(va.VariableAssertion):
    """An assertion for complex values such as objects or collections."""

    def accept(self, visitor: av.AssertionVisitor) -> None:
        visitor.visit_complex_assertion(self)

    def clone(
        self, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> ComplexAssertion:
        return ComplexAssertion(self.source.clone(memo), self.value)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ComplexAssertion)
            and self._source == other._source
            and (self._value == other._value or self._value is other._value)
        )

    def __hash__(self) -> int:
        return hash((self._source, self._value))
