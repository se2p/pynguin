#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion as ass
from pynguin.assertion.assertion import Assertion, AssertionVisitor
from pynguin.testcase import variablereference as vr


class FooReferenceAssertion(ass.ReferenceAssertion):
    def accept(self, visitor: AssertionVisitor) -> None:
        pass  # pragma: no cover

    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> Assertion:
        pass  # pragma: no cover

    def __eq__(self, other: Any) -> bool:
        pass  # pragma: no cover

    def __hash__(self) -> int:
        pass  # pragma: no cover


def test_reference_assertion_source():
    ref = MagicMock()
    foo = FooReferenceAssertion(ref)
    assert foo.source == ref


@pytest.mark.parametrize(
    "assertion,method",
    [
        (ass.NotNoneAssertion(MagicMock()), "visit_not_none_assertion"),
        (ass.FloatAssertion(MagicMock(), 3.7), "visit_float_assertion"),
        (ass.ObjectAssertion(MagicMock(), [1]), "visit_object_assertion"),
        (
            ass.CollectionLengthAssertion(MagicMock(), 5),
            "visit_collection_length_assertion",
        ),
    ],
)
def test_assertion_accept(assertion, method):
    visitor = MagicMock()
    assertion.accept(visitor)
    getattr(visitor, method).assert_called_with(assertion)


@pytest.mark.parametrize(
    "assertion",
    [
        (ass.NotNoneAssertion(vr.VariableReference(MagicMock(), int))),
        (ass.FloatAssertion(vr.VariableReference(MagicMock(), int), 3.7)),
        (ass.ObjectAssertion(vr.VariableReference(MagicMock(), int), [1])),
        (ass.CollectionLengthAssertion(vr.VariableReference(MagicMock(), int), 5)),
    ],
)
def test_assertion_clone(assertion):
    source = cast(vr.VariableReference, assertion.source)
    cloned = assertion.clone({source: source})
    assert cloned == assertion
    assert hash(cloned) == hash(assertion)


@pytest.mark.parametrize(
    "assertion,different",
    [
        (ass.NotNoneAssertion(0), ass.NotNoneAssertion(1)),
        (
            ass.FloatAssertion(0, 3.7),
            ass.FloatAssertion(vr.VariableReference(1, int), 3.7),
        ),
        (
            ass.FloatAssertion(0, 3.7),
            ass.FloatAssertion(vr.VariableReference(0, int), 3.8),
        ),
        (ass.ObjectAssertion(0, [1]), ass.ObjectAssertion(1, [1])),
        (ass.ObjectAssertion(0, [1]), ass.ObjectAssertion(1, [2])),
        (
            ass.CollectionLengthAssertion(0, 5),
            ass.CollectionLengthAssertion(1, 5),
        ),
        (
            ass.CollectionLengthAssertion(0, 5),
            ass.CollectionLengthAssertion(0, 3),
        ),
    ],
)
def test_assertion_eq(assertion, different):
    assert assertion == assertion
    assert assertion != different


def test_float_assertion_value():
    assertion = ass.FloatAssertion(MagicMock(), 3.0)
    assert assertion.value == 3.0


def test_object_assertion_object():
    assertion = ass.ObjectAssertion(MagicMock(), [3])
    assert assertion.object == [3]


def test_collection_length_assertion_length():
    assertion = ass.CollectionLengthAssertion(MagicMock(), 3)
    assert assertion.length == 3


def test_exception_assertion():
    assertion = ass.ExceptionAssertion("builtin", "foo")
    assert assertion.module == "builtin"
    assert assertion.exception_type_name == "foo"
