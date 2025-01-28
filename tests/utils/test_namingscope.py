#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from collections.abc import Callable
from collections.abc import Iterable
from typing import Union
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.variablereference as vr
import pynguin.utils.namingscope as ns


@pytest.fixture
def naming_scope():
    return ns.NamingScope()


@pytest.fixture
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
    assert dict(naming_scope) == {some_object: "var_0"}


def test_naming_scope_known_indices_has_name(naming_scope):
    some_object = "something"
    naming_scope.get_name(some_object)
    assert naming_scope.is_known_name(some_object)


@pytest.mark.parametrize(
    "tp,name",
    [
        (int, "int_0"),
        (str, "str_0"),
        (Callable[[int, str], bool], "callable_0"),
        (dict[int, str], "dict_0"),
        (list[str], "list_0"),
        (list, "list_0"),
        (Union[int, str, bool], "var_0"),  # For a union we get var0  # noqa: UP007
        (Iterable[int], "iterable_0"),
        (MagicMock, "magic_mock_0"),
    ],
)
def test_variable_type_conversion(variable_type_naming_scope, tp, name, type_system):
    var = vr.VariableReference(MagicMock(), type_system.convert_type_hint(tp))
    assert variable_type_naming_scope.get_name(var) == name


@pytest.mark.parametrize(
    "tp,name0,name1",
    [
        (int, "int_0", "int_1"),
        (str, "str_0", "str_1"),
        (Callable[[int, str], bool], "callable_0", "callable_1"),
        (dict[int, str], "dict_0", "dict_1"),
    ],
)
def test_variable_type_counter(variable_type_naming_scope, tp, name0, name1, type_system):
    var = vr.VariableReference(MagicMock(), type_system.convert_type_hint(tp))
    assert variable_type_naming_scope.get_name(var) == name0
    var = vr.VariableReference(MagicMock(), type_system.convert_type_hint(tp))
    assert variable_type_naming_scope.get_name(var) == name1


def test_variable_type_runtime(type_system):
    scope = ns.VariableTypeNamingScope(return_type_trace={0: type_system.convert_type_hint(int)})
    var = MagicMock(type=type_system.convert_type_hint(None))
    var.get_statement_position.return_value = 1
    assert scope.get_name(var) == "var_0"


def test_variable_type_runtime_2(type_system):
    scope = ns.VariableTypeNamingScope(
        return_type_trace={0: type_system.convert_type_hint(MagicMock)}
    )
    var = MagicMock(type=type_system.convert_type_hint(None))
    var.get_statement_position.return_value = 0
    assert scope.get_name(var) == "magic_mock_0"


def test_variable_type_empty(variable_type_naming_scope):
    assert len(variable_type_naming_scope) == 0


def test_variable_type_not_empty(variable_type_naming_scope, type_system):
    var = vr.VariableReference(MagicMock(), type_system.convert_type_hint(int))
    variable_type_naming_scope.get_name(var)
    assert dict(variable_type_naming_scope) == {var: "int_0"}


def test_variable_type_has_name(variable_type_naming_scope, type_system):
    var = vr.VariableReference(MagicMock(), type_system.convert_type_hint(int))
    variable_type_naming_scope.get_name(var)
    assert variable_type_naming_scope.is_known_name(var)


@pytest.mark.parametrize("before,after", [("FooBar", "foo_bar"), ("abc", "abc")])
def test_snake_case(before, after):
    assert ns.snake_case(before) == after


def test_snake_case_empty():
    with pytest.raises(AssertionError):
        ns.snake_case("")
