#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
import importlib
import inspect
import itertools
from typing import Set, Type
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.module.inheritance import (
    ClassInformation,
    build_inheritance_graph,
)
from pynguin.analyses.module.typeinformation import (
    ConcreteType,
    Parameter,
    ReturnType,
    SignatureElement,
    SignatureType,
    any_type,
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
    return SignatureElement.Element(
        signature_type=MagicMock(SignatureType),
        confidence=0.5,
    )


@pytest.fixture
def concrete_element():
    return SignatureElement.Element(
        signature_type=ConcreteType(
            ClassInformation(name="builtins.object", class_object=object)
        ),
        confidence=0.25,
    )


@pytest.fixture
def other_element():
    return SignatureElement.Element(
        signature_type=ConcreteType(
            ClassInformation(
                name="tests.fixtures.cluster.complex_dependency.SomeOtherType",
                class_object=MagicMock,
            )
        ),
        confidence=0.75,
    )


@pytest.fixture
def parameter():
    return Parameter("foo")


@pytest.fixture
def return_type():
    return ReturnType()


@pytest.fixture(scope="module")
def inheritance_graph():
    return build_inheritance_graph(
        _extract_classes_from_module("tests.fixtures.cluster.typing_parameters")
    )


def _extract_classes_from_module(module_name: str) -> Set[Type]:
    module = importlib.import_module(module_name)
    return {v for _, v in inspect.getmembers(module, inspect.isclass)}


def test_concrete_type_class_information(concrete_type, class_information):
    assert concrete_type.class_information == class_information


def test_concrete_type_type_name(concrete_type):
    assert concrete_type.type_name == "builtins.object"


def test_concrete_type_type_object(concrete_type):
    assert concrete_type.type_object == object


def test_concrete_type_eq_same(concrete_type):
    assert concrete_type.__eq__(concrete_type)


def test_concrete_type_eq_other_type(concrete_type):
    assert not concrete_type.__eq__(MagicMock())


def test_concrete_type_eq_other(concrete_type, class_information):
    other_type = ConcreteType(class_information)
    assert concrete_type.__eq__(other_type)


def test_concrete_type_hash(concrete_type):
    assert concrete_type.__hash__() != 0


def test_element_eq_same(element):
    assert element.__eq__(element)


def test_element_eq_other_type(element):
    assert not element.__eq__(MagicMock())


def test_element_eq_other(element):
    other = SignatureElement.Element(
        signature_type=element.signature_type,
        confidence=0.5,
    )
    assert element.__eq__(other)


def test_element_lt(element):
    other = SignatureElement.Element(
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


@pytest.mark.parametrize(
    "confidence, method",
    itertools.product(  # magic to test all four combinations with one test :)
        [-0.1, 1.1], ["add_element", "replace_element"]
    ),
)
def test_parameter_element_illegal_confidence(
    parameter: SignatureElement, confidence: float, method: str
):
    with pytest.raises(ValueError):
        getattr(parameter, method)(MagicMock(SignatureType), confidence)


def test_parameter_add_element_first(parameter, element):
    parameter.add_element(element.signature_type, element.confidence)
    elements = list(parameter.elements)
    assert len(elements) == 1
    assert elements[0] == element


def test_parameter_add_element_twice_illegal(parameter, element):
    parameter.add_element(element.signature_type, element.confidence)
    with pytest.raises(AssertionError):
        parameter.add_element(element.signature_type, element.confidence)


def test_parameter_add_element_two(parameter, element):
    signature_2 = MagicMock(any_type)
    confidence_2 = 1.0
    parameter.add_element(element.signature_type, element.confidence)
    parameter.add_element(signature_2, confidence_2)
    assert len(list(parameter.elements)) == 2


def test_parameter_replace_element_not_existing(parameter, element):
    parameter.replace_element(element.signature_type, element.confidence)
    elements = list(parameter.elements)
    assert len(elements) == 1
    assert elements[0] == element


def test_parameter_replace_element(parameter, element):
    signature_2 = element.signature_type
    confidence_2 = 0.75
    parameter.add_element(element.signature_type, element.confidence)
    parameter.replace_element(signature_2, confidence_2)
    elements = list(parameter.elements)
    assert len(elements) == 1
    assert elements[0].signature_type == element.signature_type
    assert elements[0].confidence == confidence_2


def test_parameter_provide_random_type_no_confidence(parameter, element):
    element_2 = SignatureElement.Element(MagicMock(SignatureType), 0.75)
    parameter.add_element(element.signature_type, element.confidence)
    parameter.add_element(element_2.signature_type, element_2.confidence)
    result = parameter.provide_random_type(respect_confidence=False)
    assert result in (element.signature_type, element_2.signature_type)


def test_parameter_provide_random_type_with_confidence(parameter, element):
    element_2 = SignatureElement.Element(MagicMock(SignatureType), 0.75)
    parameter.add_element(element.signature_type, element.confidence)
    parameter.add_element(element_2.signature_type, element_2.confidence)
    result = parameter.provide_random_type(respect_confidence=True)
    assert result in (element.signature_type, element_2.signature_type)


def test_parameter_get_element(parameter, concrete_element):
    assert parameter.get_element(concrete_element.signature_type) is None


def test_parameter_include_inheritance(parameter, concrete_element, inheritance_graph):
    parameter.add_element(concrete_element.signature_type, concrete_element.confidence)
    parameter.include_inheritance(inheritance_graph)
    assert len(parameter.elements) == 4


def test_parameter_include_inheritance_existing(
    parameter, concrete_element, other_element, inheritance_graph
):
    parameter.add_element(concrete_element.signature_type, concrete_element.confidence)
    parameter.add_element(other_element.signature_type, other_element.confidence)
    parameter.include_inheritance(inheritance_graph)
    assert len(parameter.elements) == 4


def test_parameter_include_inheritance_no_types(parameter, inheritance_graph):
    parameter.include_inheritance(inheritance_graph)
    assert len(parameter.elements) == 1


def test_return_type_include_inheritance_no_types(return_type, inheritance_graph):
    return_type.include_inheritance(inheritance_graph)
    assert len(return_type.elements) == 1


def test_return_type_include_inheritance(return_type, other_element, inheritance_graph):
    return_type.add_element(other_element.signature_type, other_element.confidence)
    return_type.include_inheritance(inheritance_graph)
    assert len(return_type.elements) == 2


def test_return_type_include_inheritance_existing(
    return_type, concrete_element, other_element, inheritance_graph
):
    return_type.add_element(
        concrete_element.signature_type, concrete_element.confidence
    )
    return_type.add_element(other_element.signature_type, other_element.confidence)
    return_type.include_inheritance(inheritance_graph)
    assert len(return_type.elements) == 2


def test_parameter_inheritance_confidence(return_type):
    graph = build_inheritance_graph(
        _extract_classes_from_module(
            "tests.fixtures.cluster.overridden_inherited_methods"
        )
    )
    nodes = list(graph._graph.nodes)
    nodes.sort(key=lambda n: n.name)
    ci_builtins, ci_bar, ci_foo = nodes
    return_type.add_element(ConcreteType(ci_bar), 1.0)
    return_type.include_inheritance(graph)

    elements = [element for element in return_type.elements]
    elements.sort(key=lambda n: n.signature_type.class_information.name)
    confidences = [element.confidence for element in elements]
    assert confidences == [0.25, 1.0, 0.5]
