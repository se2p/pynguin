#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a none assertion."""
from __future__ import annotations

import pynguin.assertion.assertion as ass
import pynguin.testcase.testcase as tc
from pynguin.assertion import assertionvisitor as av


class NoneAssertion(ass.Assertion):
    """An assertion of the None-ness of a variable."""

    def accept(self, visitor: av.AssertionVisitor) -> None:
        visitor.visit_none_assertion(self)

    def clone(self, new_test_case: tc.TestCase, offset: int) -> NoneAssertion:
        return NoneAssertion(self._source.clone(new_test_case, offset), self.value)
