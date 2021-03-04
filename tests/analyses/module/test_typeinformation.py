#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.module.inheritance import ClassInformation
from pynguin.analyses.module.typeinformation import (
    ConcreteType,
    Parameter,
    SignatureElement,
    SignatureType,
    unknown_type,
)


@pytest.fixture
def class_information():
    return ClassInformation(name="builtins.object", class_object=object)


@pytest.fixture
def concrete_type(class_information):
    return ConcreteType(class_information)


@pytest.fixture
def element():
    return SignatureElement._Element(
        signature_type=MagicMock(SignatureType),
        confidence=0.5,
    )


@pytest.fixture
def parameter():
    return Parameter("foo")


def test_concrete_type_class_information(concrete_type, class_information):
    assert concrete_type.class_information == class_information


def test_concrete_type_type_name(concrete_type):
    assert concrete_type.type_name == "builtins.object"


def test_concrete_type_type_object(concrete_type):
    assert concrete_type.type_object == object


def test_element_eq_same(element):
    assert element.__eq__(element)


def test_element_eq_other_type(element):
    assert not element.__eq__(MagicMock())


def test_element_eq_other(element):
    other = SignatureElement._Element(
        signature_type=element.signature_type,
        confidence=0.5,
    )
    assert element.__eq__(other)


def test_element_lt(element):
    other = SignatureElement._Element(
        signature_type=MagicMock(),
        confidence=0.7,
    )
    assert element.__lt__(other)


def test_element_lt_other_illegal_type(element):
    with pytest.raises(TypeError):
        element.__lt__(MagicMock())


def test_parameter_elements(parameter):
    element = parameter.elements.pop()
    assert element.signature_type == unknown_type
    assert element.confidence == 0.0


def test_parameter_element_types(parameter):
    elements = list(parameter.element_types)
    assert len(elements) == 1
    assert elements[0] == unknown_type


def test_parameter_name(parameter):
    assert parameter.name == "foo"
