#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.assertion as ass
from pynguin.assertion import assertionvisitor as av
from pynguin.assertion.assertion import Assertion
from pynguin.testcase import testcase as tc


class FooAssertion(ass.Assertion):
    def accept(self, visitor: av.AssertionVisitor) -> None:
        pass

    def clone(self, new_test_case: tc.TestCase, offset: int) -> Assertion:
        pass


def test_eq():
    var = MagicMock()
    assert FooAssertion(var, True) == FooAssertion(var, True)


def test_neq():
    assert FooAssertion(MagicMock(), True) != FooAssertion(MagicMock(), True)


def test_hash():
    var = MagicMock()
    assert hash(FooAssertion(var, True)) == hash(FooAssertion(var, True))


def test_neq_hash():
    assert hash(FooAssertion(MagicMock(), True)) != hash(
        FooAssertion(MagicMock(), True)
    )
