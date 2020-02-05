# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest.mock import MagicMock

from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericMethod,
    GenericFunction,
    GenericField,
)


def test_generic_constructor_eq_self(constructor_mock):
    assert constructor_mock == constructor_mock


def test_generic_constructor_eq_modified(constructor_mock):
    second = GenericConstructor(MagicMock, MagicMock(InferredSignature))
    assert constructor_mock != second


def test_generic_constructor_eq_other(constructor_mock):
    assert constructor_mock != "test"


def test_generic_constructor_hash_self(constructor_mock):
    assert hash(constructor_mock) == hash(constructor_mock)


def test_generic_method_eq_self(method_mock):
    assert method_mock == method_mock


def test_generic_method_eq_modified(method_mock):
    second = GenericMethod(MagicMock, int, MagicMock(InferredSignature))
    assert method_mock != second


def test_generic_method_eq_other(method_mock):
    assert method_mock != "test"


def test_generic_method_hash(method_mock):
    assert hash(method_mock) == hash(method_mock)


def test_generic_function_eq_self(function_mock):
    assert function_mock == function_mock


def test_generic_function_eq_modified(function_mock):
    second = GenericFunction(int, MagicMock(InferredSignature))
    assert function_mock != second


def test_generic_function_eq_other(function_mock):
    assert function_mock != "test"


def test_generic_function_hash(function_mock):
    assert hash(function_mock) == hash(function_mock)


def test_generic_field_eq_self(field_mock):
    assert field_mock == field_mock


def test_generic_field_eq_modified(field_mock):
    second = GenericField(MagicMock, "xyz", str)
    assert field_mock != second


def test_generic_field_eq_other(field_mock):
    assert field_mock != "test"


def test_generic_field_hash(field_mock):
    assert hash(field_mock) == hash(field_mock)
