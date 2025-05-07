#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from types import ClassMethodDescriptorType
from unittest.mock import MagicMock

from pynguin.analyses.typesystem import InferredSignature
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TypeInfo
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericField
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.orderedset import OrderedSet
from tests.fixtures.accessibles.accessible import SomeType


class TestAccessibleObject(GenericAccessibleObject):
    def generated_type(self) -> type | None:
        pass  # pragma: no cover

    def get_dependencies(
        self, memo: dict[InferredSignature, dict[str, ProperType]]
    ) -> OrderedSet[ProperType]:
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
    assert constructor_mock == constructor_mock  # noqa: PLR0124


def test_generic_constructor_eq_modified(constructor_mock, type_system):
    second = GenericConstructor(type_system.to_type_info(MagicMock), MagicMock(InferredSignature))
    assert constructor_mock != second


def test_generic_constructor_eq_other(constructor_mock):
    assert constructor_mock != "test"


def test_generic_constructor_hash_self(constructor_mock):
    assert hash(constructor_mock) == hash(constructor_mock)


def test_generic_constructor_is_constructor(constructor_mock):
    assert constructor_mock.is_constructor()


def test_generic_constructor_num_parameters(constructor_mock):
    assert constructor_mock.get_num_parameters() == 1


def test_generic_constructor_dependencies(constructor_mock, type_system):
    assert constructor_mock.get_dependencies({}) == OrderedSet([
        type_system.convert_type_hint(float)
    ])


def test_generic_method_eq_self(method_mock):
    assert method_mock == method_mock  # noqa: PLR0124


def test_generic_method_eq_modified(method_mock, type_system):
    second = GenericMethod(
        type_system.to_type_info(MagicMock),
        type_system.convert_type_hint(int),
        MagicMock(return_type=type_system.convert_type_hint(None)),
    )
    assert method_mock != second


def test_generic_method_eq_other(method_mock):
    assert method_mock != "test"


def test_generic_method_hash(method_mock):
    assert hash(method_mock) == hash(method_mock)


def test_generic_method_is_method(method_mock):
    assert method_mock.is_method()


def test_generic_method_dependencies(method_mock, type_system):
    assert method_mock.get_dependencies({}) == OrderedSet([
        type_system.convert_type_hint(int),
        type_system.convert_type_hint(SomeType),
    ])


def test_generic_function_eq_self(function_mock):
    assert function_mock == function_mock  # noqa: PLR0124


def test_generic_function_eq_modified(function_mock, type_system):
    second = GenericFunction(type_system.convert_type_hint(int), MagicMock(InferredSignature))
    assert function_mock != second


def test_generic_function_eq_other(function_mock):
    assert function_mock != "test"


def test_generic_function_hash(function_mock):
    assert hash(function_mock) == hash(function_mock)


def test_generic_function_is_function(function_mock):
    assert function_mock.is_function()


def test_generic_field_eq_self(field_mock):
    assert field_mock == field_mock  # noqa: PLR0124


def test_generic_field_eq_modified(field_mock, type_system):
    second = GenericField(
        type_system.to_type_info(MagicMock), "xyz", type_system.convert_type_hint(str)
    )
    assert field_mock != second


def test_generic_field_eq_other(field_mock):
    assert field_mock != "test"


def test_generic_field_hash(field_mock):
    assert hash(field_mock) == hash(field_mock)


def test_generic_field_field(field_mock):
    assert field_mock.field == "y"


def test_generic_field_is_field(field_mock):
    assert field_mock.is_field()


def test_generic_field_dependencies(field_mock, type_system):
    assert field_mock.get_dependencies({}) == OrderedSet([type_system.convert_type_hint(SomeType)])


def test_generic_function_raised_exceptions():
    func = GenericFunction(MagicMock(), MagicMock(), {"FooError"})
    assert func.raised_exceptions == {"FooError"}


def test_generic_accessible_object_is_classmethod():
    """Test is_classmethod on GenericAccessibleObject."""
    acc = TestAccessibleObject(None)
    assert not acc.is_classmethod()


def test_generic_constructor_is_classmethod(constructor_mock):
    """Test is_classmethod on GenericConstructor."""
    assert not constructor_mock.is_classmethod()


def test_generic_method_is_classmethod_with_class_method_descriptor(type_system):
    """Test is_classmethod on GenericMethod with a ClassMethodDescriptorType."""
    mock_signature = MagicMock()
    mock_signature.return_type = type_system.convert_type_hint(None)

    # Create a method with a mock callable
    method = GenericMethod(
        owner=TypeInfo(dict),
        method=MagicMock(),
        inferred_signature=mock_signature,
    )

    # Replace the _callable attribute with a mock that is an instance of ClassMethodDescriptorType
    method._callable = MagicMock(spec=ClassMethodDescriptorType)

    assert method.is_classmethod()
