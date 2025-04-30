#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast

from typing import cast
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion as ass

from pynguin.assertion.assertion import Assertion
from pynguin.assertion.assertion import AssertionVisitor
from pynguin.testcase import variablereference as vr


class FooReferenceAssertion(ass.ReferenceAssertion):
    def accept(self, visitor: AssertionVisitor) -> None:
        pass  # pragma: no cover

    def clone(self, memo: dict[vr.VariableReference, vr.VariableReference]) -> Assertion:
        pass  # pragma: no cover

    def __eq__(self, other: object) -> bool:
        pass  # pragma: no cover

    def __hash__(self) -> int:
        pass  # pragma: no cover


def test_reference_assertion_source():
    ref = MagicMock()
    foo = FooReferenceAssertion(ref)
    assert foo.source == ref


def test_reference_assertion_source_setter():
    ref1 = MagicMock()
    ref2 = MagicMock()
    foo = FooReferenceAssertion(ref1)
    foo.source = ref2
    assert foo.source == ref2


@pytest.mark.parametrize(
    "assertion,method",
    [
        (ass.TypeNameAssertion(MagicMock(), "", ""), "visit_type_name_assertion"),
        (ass.FloatAssertion(MagicMock(), 3.7), "visit_float_assertion"),
        (ass.ObjectAssertion(MagicMock(), [1]), "visit_object_assertion"),
        (
            ass.IsInstanceAssertion(MagicMock(), ast.Name(id="int", ctx=ast.Load())),
            "visit_isinstance_assertion",
        ),
        (
            ass.CollectionLengthAssertion(MagicMock(), 5),
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
        (ass.TypeNameAssertion(vr.VariableReference(MagicMock(), int), "builtins", "int")),
        (ass.FloatAssertion(vr.VariableReference(MagicMock(), int), 3.7)),
        (ass.ObjectAssertion(vr.VariableReference(MagicMock(), int), [1])),
        (
            ass.IsInstanceAssertion(
                vr.VariableReference(MagicMock(), int), ast.Name(id="int", ctx=ast.Load())
            )
        ),
        (ass.CollectionLengthAssertion(vr.VariableReference(MagicMock(), int), 5)),
    ],
)
def test_assertion_clone(assertion):
    source = cast("vr.VariableReference", assertion.source)
    cloned = assertion.clone({source: source})
    assert cloned == assertion
    assert hash(cloned) == hash(assertion)


@pytest.mark.parametrize(
    "assertion,different",
    [
        (
            ass.TypeNameAssertion(0, "foo", "bar"),
            ass.TypeNameAssertion(1, "foo", "bar"),
        ),
        (
            ass.TypeNameAssertion(0, "foo", "bar"),
            ass.TypeNameAssertion(1, "fob", "bar"),
        ),
        (
            ass.TypeNameAssertion(0, "foo", "bar"),
            ass.TypeNameAssertion(1, "fob", "baz"),
        ),
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
            ass.IsInstanceAssertion(0, ast.Name(id="int", ctx=ast.Load())),
            ass.IsInstanceAssertion(1, ast.Name(id="int", ctx=ast.Load())),
        ),
        (
            ass.IsInstanceAssertion(0, ast.Name(id="int", ctx=ast.Load())),
            ass.IsInstanceAssertion(0, ast.Name(id="str", ctx=ast.Load())),
        ),
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
    assert assertion == assertion  # noqa: PLR0124
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


def test_isinstance_assertion_expected_type():
    expected_type = ast.Name(id="int", ctx=ast.Load())
    assertion = ass.IsInstanceAssertion(MagicMock(), expected_type)
    assert assertion.expected_type == expected_type
