#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Iterable, Set

import pytest

from pynguin.utils.duckmock.duckmock import CallInformation, DuckMock


@pytest.fixture
def duck_mock() -> DuckMock:
    return DuckMock()


@pytest.fixture
def call_information() -> CallInformation:
    return CallInformation(name="foo", args=[], kwargs={})


def _names(result: Iterable[CallInformation]) -> Set[str]:
    return {info.name for info in result}


def _call_information_deep_eq(first: CallInformation, second: CallInformation) -> bool:
    return (
        first.name == second.name
        and first.args == second.args
        and first.kwargs == second.kwargs
    )


def test_simple_method_calls(duck_mock):
    duck_mock.foo()
    duck_mock.bar("param")
    duck_mock.bar()
    duck_mock.baz()
    result = duck_mock.call_information
    expected = {"bar", "baz", "foo"}
    assert expected.issubset(_names(result))


def test_field_access(duck_mock):
    duck_mock.foo = 42
    foo = duck_mock.foo
    result = duck_mock.call_information
    expected = set()
    assert expected.issubset(_names(result))
    assert foo == 42


def test_dunder_method_calls(duck_mock):
    duck_mock.__hash__()
    duck_mock.__lt__(42)
    result = duck_mock.call_information
    expected = {"__hash__", "__lt__"}
    assert expected.issubset(_names(result))


def test_parameters(duck_mock):
    duck_mock.__add__(42)
    duck_mock.foo("bar")
    duck_mock.baz(foo=23)
    result = duck_mock.call_information
    method_call_information = duck_mock.method_call_information

    add_call_information = CallInformation(name="__add__", args=[42], kwargs={})
    foo_call_information = CallInformation(name="foo", args=["bar"], kwargs={})
    baz_call_information = CallInformation(name="baz", args=[], kwargs={"foo": 23})
    expected = {add_call_information, foo_call_information, baz_call_information}

    assert expected.issubset(result)
    assert _call_information_deep_eq(
        method_call_information["__add__"], add_call_information
    )
    assert _call_information_deep_eq(
        method_call_information["foo"], foo_call_information
    )
    assert _call_information_deep_eq(
        method_call_information["baz"], baz_call_information
    )


def test_call_information_hash(call_information):
    assert call_information.__hash__() != 0


def test_call_information_eq_same(call_information):
    assert call_information.__eq__(call_information)


def test_call_information_eq_other_type(call_information):
    assert not call_information.__eq__("foo")


def test_call_information_eq_same_type(call_information):
    other = CallInformation(name="foo", args=[], kwargs={})
    assert call_information.__eq__(other)
