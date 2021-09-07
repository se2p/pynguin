#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an assertion for primitive values."""
from __future__ import annotations

import pynguin.assertion.assertion as ass
import pynguin.testcase.testcase as tc
from pynguin.assertion import assertionvisitor as av


class PrimitiveAssertion(ass.Assertion):
    """An assertion for primitive values."""

    def accept(self, visitor: av.AssertionVisitor) -> None:
        visitor.visit_primitive_assertion(self)

    def clone(self, new_test_case: tc.TestCase, offset: int) -> PrimitiveAssertion:
        return PrimitiveAssertion(self._source.clone(new_test_case, offset)
                                  if self._source else None,
                                  self.value)
