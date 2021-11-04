#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Callable, Dict, Iterable, List, Union
from unittest.mock import MagicMock

import pytest

import pynguin.utils.namingscope as ns


@pytest.fixture()
def naming_scope():
    return ns.NamingScope()


@pytest.fixture()
def variable_type_naming_scope():
    return ns.VariableTypeNamingScope()


def test_naming_scope_same(naming_scope):
    some_object = "something"
    name1 = naming_scope.get_name(some_object)
    name2 = naming_scope.get_name(some_object)
    assert name1 == name2


def test_naming_scope_different(naming_scope):
    name1 = naming_scope.get_name("one name")
    name2 = naming_scope.get_name("another")
    assert name1 != name2


def test_naming_scope_empty(naming_scope):
    assert len(naming_scope) == 0


def test_naming_scope_known_indices_not_empty(naming_scope):
    some_object = "something"
    naming_scope.get_name(some_object)
    assert dict(naming_scope) == {some_object: "var0"}


def test_naming_scope_known_indices_has_name(naming_scope):
    some_object = "something"
    naming_scope.get_name(some_object)
    assert naming_scope.is_name_known(some_object)


@pytest.mark.parametrize(
    "tp,name",
    [
        (int, "int0"),
        (str, "str0"),
        (Callable[[int, str], bool], "callable0"),
        (Dict[int, str], "dict0"),
        (List[str], "list0"),
        (list, "list0"),
        (Union[int, str, bool], "var0"),  # For union we get var0
        (Iterable[int], "iterable0"),
    ],
)
def test_variable_type_conversion(variable_type_naming_scope, tp, name):
    var = MagicMock(variable_type=tp)
    assert variable_type_naming_scope.get_name(var) == name


@pytest.mark.parametrize(
    "tp,name0,name1",
    [
        (int, "int0", "int1"),
        (str, "str0", "str1"),
        (Callable[[int, str], bool], "callable0", "callable1"),
        (Dict[int, str], "dict0", "dict1"),
    ],
)
def test_variable_type_counter(variable_type_naming_scope, tp, name0, name1):
    var = MagicMock(variable_type=tp)
    assert variable_type_naming_scope.get_name(var) == name0
    var = MagicMock(variable_type=tp)
    assert variable_type_naming_scope.get_name(var) == name1


def test_variable_type_empty(variable_type_naming_scope):
    assert len(variable_type_naming_scope) == 0


def test_variable_type_not_empty(variable_type_naming_scope):
    var = MagicMock(variable_type=int)
    variable_type_naming_scope.get_name(var)
    assert dict(variable_type_naming_scope) == {var: "int0"}


def test_variable_type_has_name(variable_type_naming_scope):
    var = MagicMock(variable_type=int)
    variable_type_naming_scope.get_name(var)
    assert variable_type_naming_scope.is_name_known(var)


@pytest.mark.parametrize("before,after", [("FOOBAR", "fOOBAR"), ("abc", "abc")])
def test_cheap_camel_case(before, after):
    assert ns.cheap_camel_case(before) == after


def test_cheap_camel_case_empty():
    with pytest.raises(AssertionError):
        ns.cheap_camel_case("")
