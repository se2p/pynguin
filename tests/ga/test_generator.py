#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.generator import GeneratorProvider
from pynguin.analyses.generator import RandomGeneratorProvider
from pynguin.analyses.generator import _Generator  # noqa: PLC2701
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import TypeInfo
from pynguin.ga.operators.selection import RandomSelection
from pynguin.ga.operators.selection import RankSelection
from pynguin.ga.operators.selection import SelectionFunction
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.orderedset import FrozenOrderedSet


def get_all_generators(cluster):
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
    return {**methods, **constructors, **functions}


@pytest.fixture
def generator_provider() -> GeneratorProvider:
    fitness_function = MagicMock()
    selection_function = MagicMock(spec=SelectionFunction)
    return GeneratorProvider(fitness_function, selection_function)


def test_generator():
    generator_method = MagicMock()
    type_to_generate = MagicMock()
    fitness_function = MagicMock()
    generator = _Generator(generator_method, type_to_generate, fitness_function)
    assert generator.generator == generator_method
    assert str(generator) == str(generator_method)


def test_generator_get_fitness_for():
    generator_method = MagicMock(GenericCallableAccessibleObject)
    generator_method.inferred_signature = MagicMock()
    generator_method.inferred_signature.return_type = MagicMock(Instance)
    generator_method.inferred_signature.return_type.type = MagicMock()

    type_to_generate = MagicMock(Instance)
    type_to_generate.type = MagicMock()

    fitness_function = MagicMock()
    generator = _Generator(generator_method, type_to_generate, fitness_function)
    assert generator.get_fitness() == generator.get_fitness_for(fitness_function) != float("inf")


def test_generator_get_fitness_for_no_inf():
    generator_method = MagicMock()
    fitness_function = MagicMock()

    type_to_generate = MagicMock(Instance)
    type_to_generate.type = MagicMock()

    generator = _Generator(generator_method, type_to_generate, fitness_function)
    assert generator.get_fitness() == generator.get_fitness_for(fitness_function) != float("inf")


@pytest.mark.parametrize(
    "provider_class, selection_function, expected",
    [
        (GeneratorProvider, RankSelection(), "tests.fixtures.examples.constructors.Base"),
        (
            RandomGeneratorProvider,
            RandomSelection(),
            "tests.fixtures.examples.constructors.Base.instance_constructor",
        ),
    ],
)
@mock.patch("pynguin.utils.randomness.next_float")
@mock.patch("pynguin.utils.randomness.next_int")
def test_generator_provider_integration(
    float_mock, int_mock, provider_class, selection_function, expected
):
    float_mock.side_effect = [0]
    int_mock.side_effect = [0]

    cluster = generate_test_cluster("tests.fixtures.examples.constructors")
    type_system = cluster.type_system
    base_type: TypeInfo = type_system.find_type_info("tests.fixtures.examples.constructors.Base")

    generators = get_all_generators(cluster)

    provider = provider_class(type_system, selection_function=selection_function)
    for generator in generators.values():
        provider.add(generator)

    proper_type = Instance(base_type)
    generator_methods = provider.get_for_type(proper_type)
    generators = FrozenOrderedSet([
        _Generator(generator, proper_type, provider._fitness_function)
        for generator in generator_methods
    ])
    generator = provider._select_generator(generators)

    assert str(generator) == expected


@pytest.mark.parametrize("provider_class", [GeneratorProvider, RandomGeneratorProvider])
def test_generator_provider(provider_class):
    class MyClass:
        pass

    type_system = MagicMock()
    selection_function = MagicMock(spec=SelectionFunction)
    selection_function.select = lambda x: x

    provider = provider_class(type_system, selection_function=selection_function)
    generated_type = Instance(TypeInfo(MyClass))
    generator = mock.MagicMock()
    generator.generated_type.return_value = generated_type
    generator.inferred_signature.return_type = generated_type
    generator.get_fitness.return_value = 0.0

    provider.add(generator)
    retrieved_generator_methods = provider.get_for_type(generated_type)
    retrieved_generators = FrozenOrderedSet([
        _Generator(generator, generated_type, provider._fitness_function)
        for generator in retrieved_generator_methods
    ])
    retrieved_generator = provider._select_generator(retrieved_generators)

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
