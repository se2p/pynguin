#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion as ass
from pynguin.assertion.assertion import Assertion, AssertionVisitor


class FooReferenceAssertion(ass.ReferenceAssertion):
    def accept(self, visitor: AssertionVisitor) -> None:
        pass  # pragma: no cover

    def clone(self, memo: dict[str, str]) -> Assertion:
        return self  # pragma: no cover

    def __eq__(self, other: object) -> bool:
        return self is other  # pragma: no cover

    def __hash__(self) -> int:
        return id(self)  # pragma: no cover


def test_reference_assertion_source():
    foo = FooReferenceAssertion("var_0")
    assert foo.source == "var_0"


def test_reference_assertion_source_setter():
    foo = FooReferenceAssertion("var_0")
    foo.source = "var_1"
    assert foo.source == "var_1"


@pytest.mark.parametrize(
    "assertion,method",
    [
        (ass.TypeNameAssertion("var_0", "", ""), "visit_type_name_assertion"),
        (ass.FloatAssertion("var_0", 3.7), "visit_float_assertion"),
        (ass.ObjectAssertion("var_0", [1]), "visit_object_assertion"),
        (
            ass.IsInstanceAssertion("var_0", "builtins", "int"),
            "visit_isinstance_assertion",
        ),
        (
            ass.CollectionLengthAssertion("var_0", 5),
            "visit_collection_length_assertion",
        ),
        (
            ass.ExceptionAssertion("", ""),
            "visit_exception_assertion",
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
        (ass.TypeNameAssertion("var_0", "builtins", "int")),
        (ass.FloatAssertion("var_0", 3.7)),
        (ass.ObjectAssertion("var_0", [1])),
        (ass.IsInstanceAssertion("var_0", "builtins", "int")),
        (ass.CollectionLengthAssertion("var_0", 5)),
    ],
)
def test_assertion_clone(assertion):
    source = assertion.source
    cloned = assertion.clone({source: source})
    assert cloned == assertion
    assert hash(cloned) == hash(assertion)


@pytest.mark.parametrize(
    "assertion,different",
    [
        (
            ass.TypeNameAssertion("var_0", "foo", "bar"),
            ass.TypeNameAssertion("var_1", "foo", "bar"),
        ),
        (
            ass.TypeNameAssertion("var_0", "foo", "bar"),
            ass.TypeNameAssertion("var_1", "fob", "bar"),
        ),
        (
            ass.TypeNameAssertion("var_0", "foo", "bar"),
            ass.TypeNameAssertion("var_1", "fob", "baz"),
        ),
        (
            ass.FloatAssertion("var_0", 3.7),
            ass.FloatAssertion("var_1", 3.7),
        ),
        (
            ass.FloatAssertion("var_0", 3.7),
            ass.FloatAssertion("var_0", 3.8),
        ),
        (ass.ObjectAssertion("var_0", [1]), ass.ObjectAssertion("var_1", [1])),
        (ass.ObjectAssertion("var_0", [1]), ass.ObjectAssertion("var_1", [2])),
        (
            ass.IsInstanceAssertion("var_0", "builtins", "int"),
            ass.IsInstanceAssertion("var_1", "builtins", "int"),
        ),
        (
            ass.IsInstanceAssertion("var_0", "builtins", "int"),
            ass.IsInstanceAssertion("var_0", "builtins", "str"),
        ),
        (
            ass.CollectionLengthAssertion("var_0", 5),
            ass.CollectionLengthAssertion("var_1", 5),
        ),
        (
            ass.CollectionLengthAssertion("var_0", 5),
            ass.CollectionLengthAssertion("var_0", 3),
        ),
    ],
)
def test_assertion_eq(assertion, different):
    assert assertion == assertion  # noqa: PLR0124
    assert assertion != different


def test_float_assertion_value():
    assertion = ass.FloatAssertion("var_0", 3.0)
    assert assertion.value == 3.0


def test_object_assertion_object():
    assertion = ass.ObjectAssertion("var_0", [3])
    assert assertion.object == [3]


def test_collection_length_assertion_length():
    assertion = ass.CollectionLengthAssertion("var_0", 3)
    assert assertion.length == 3


def test_exception_assertion():
    assertion = ass.ExceptionAssertion("builtin", "foo")
    assert assertion.module == "builtin"
    assert assertion.exception_type_name == "foo"


def test_isinstance_assertion_expected_type():
    assertion = ass.IsInstanceAssertion("var_0", "builtins", "int")
    assert assertion.module == "builtins"
    assert assertion.qualname == "int"
