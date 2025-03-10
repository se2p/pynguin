#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.generator import GeneratorProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import TypeInfo
from pynguin.ga.operators.selection import RankSelection
from pynguin.ga.operators.selection import SelectionFunction
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod


@pytest.fixture
def generator_provider() -> GeneratorProvider:
    fitness_function = MagicMock()
    selection_function = MagicMock(spec=SelectionFunction)
    return GeneratorProvider(fitness_function, selection_function)


# TODO: Get rid of code duplicate
@mock.patch("pynguin.utils.randomness.next_float")
def test_generator_provider_integration(rand_mock):
    rand_mock.side_effect = [0]

    cluster = generate_test_cluster("tests.fixtures.examples.constructors")
    type_system = cluster.type_system
    base_type: TypeInfo = type_system.find_type_info("tests.fixtures.examples.constructors.Base")

    methods = {
        method.owner.full_name + "." + method.method_name: method
        for method in cluster.accessible_objects_under_test
        if isinstance(method, GenericMethod)
    }
    constructors = {
        constructor.owner.full_name: constructor
        for constructor in cluster.accessible_objects_under_test
        if isinstance(constructor, GenericConstructor)
    }
    functions = {
        function.function_name: function
        for function in cluster.accessible_objects_under_test
        if isinstance(function, GenericFunction)
    }
    merged = {**methods, **constructors, **functions}

    selection_function = RankSelection()
    provider = GeneratorProvider(type_system, selection_function=selection_function)
    for generator in merged.values():
        provider.add(generator)

    proper_type = Instance(base_type)
    generators = provider.get_for_type(proper_type)
    generator = provider.select_generator(proper_type, generators.freeze())

    assert str(generator) == "tests.fixtures.examples.constructors.Base"


def test_generator_provider():
    class MyClass:
        pass

    type_system = MagicMock()
    selection_function = MagicMock(spec=SelectionFunction)
    selection_function.select = lambda x: x
    provider = GeneratorProvider(type_system, selection_function=selection_function)
    generated_type = Instance(TypeInfo(MyClass))
    generator = mock.MagicMock(spec=GenericCallableAccessibleObject)
    generator.generated_type.return_value = generated_type

    provider.add(generator)
    retrieved_generators = provider.get_for_type(generated_type)
    retrieved_generator = provider.select_generator(generated_type, retrieved_generators.freeze())

    assert retrieved_generator == generator


def test_generator_provider_empty(generator_provider):
    generated_type = MagicMock()
    assert len(generator_provider.get_for_type(generated_type)) == 0
    assert len(generator_provider.get_all_types()) == 0
    assert len(generator_provider.get_all()) == 0


def test_generator_provider_add_primitive(generator_provider):
    generated_type = Instance(TypeInfo(int))
    generator = MagicMock()
    generator.generated_type.return_value = generated_type
    generator_provider.add(generator)
    assert len(generator_provider.get_all_types()) == 0
    assert len(generator_provider.get_all()) == 0


def test_generator_provider_add_no_generator(generator_provider):
    generator = MagicMock()
    generator.generated_type.return_value = NoneType()
    generator_provider.add(generator)
    assert len(generator_provider.get_all_types()) == 0
    assert len(generator_provider.get_all()) == 0
