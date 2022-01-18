#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Optional, Set, Type
from unittest.mock import MagicMock

from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericConstructor,
    GenericField,
    GenericFunction,
    GenericMethod,
)
from tests.fixtures.accessibles.accessible import SomeType


class TestAccessibleObject(GenericAccessibleObject):
    def generated_type(self) -> Optional[Type]:
        pass  # pragma: no cover

    def get_dependencies(self) -> Set[Type]:
        pass  # pragma: no cover


def test_no_types_true():
    acc = TestAccessibleObject(None)
    assert not acc.is_constructor()
    assert not acc.is_method()
    assert not acc.is_function()
    assert not acc.is_field()


def test_no_params():
    acc = TestAccessibleObject(None)
    assert acc.get_num_parameters() == 0


def test_generic_constructor_eq_self(constructor_mock):
    assert constructor_mock == constructor_mock


def test_generic_constructor_eq_modified(constructor_mock):
    second = GenericConstructor(MagicMock, MagicMock(InferredSignature))
    assert constructor_mock != second


def test_generic_constructor_eq_other(constructor_mock):
    assert constructor_mock != "test"


def test_generic_constructor_hash_self(constructor_mock):
    assert hash(constructor_mock) == hash(constructor_mock)


def test_generic_constructor_is_constructor(constructor_mock):
    assert constructor_mock.is_constructor()


def test_generic_constructor_num_parameters(constructor_mock):
    assert constructor_mock.get_num_parameters() == 1


def test_generic_constructor_dependencies(constructor_mock):
    assert constructor_mock.get_dependencies() == {float}


def test_generic_method_eq_self(method_mock):
    assert method_mock == method_mock


def test_generic_method_eq_modified(method_mock):
    second = GenericMethod(MagicMock, int, MagicMock(InferredSignature))
    assert method_mock != second


def test_generic_method_eq_other(method_mock):
    assert method_mock != "test"


def test_generic_method_hash(method_mock):
    assert hash(method_mock) == hash(method_mock)


def test_generic_method_is_method(method_mock):
    assert method_mock.is_method()


def test_generic_method_dependencies(method_mock):
    assert method_mock.get_dependencies() == {int, SomeType}


def test_generic_function_eq_self(function_mock):
    assert function_mock == function_mock


def test_generic_function_eq_modified(function_mock):
    second = GenericFunction(int, MagicMock(InferredSignature))
    assert function_mock != second


def test_generic_function_eq_other(function_mock):
    assert function_mock != "test"


def test_generic_function_hash(function_mock):
    assert hash(function_mock) == hash(function_mock)


def test_generic_function_is_function(function_mock):
    assert function_mock.is_function()


def test_generic_field_eq_self(field_mock):
    assert field_mock == field_mock


def test_generic_field_eq_modified(field_mock):
    second = GenericField(MagicMock, "xyz", str)
    assert field_mock != second


def test_generic_field_eq_other(field_mock):
    assert field_mock != "test"


def test_generic_field_hash(field_mock):
    assert hash(field_mock) == hash(field_mock)


def test_generic_field_field(field_mock):
    assert field_mock.field == "y"


def test_generic_field_is_field(field_mock):
    assert field_mock.is_field()


def test_generic_field_dependencies(field_mock):
    assert field_mock.get_dependencies() == {SomeType}
