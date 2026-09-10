#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.generator import (
    GeneratorProvider,
    HeuristicGeneratorFitnessFunction,
    RandomGeneratorProvider,
    _Generator,  # noqa: PLC2701
)
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import Instance, NoneType, TupleType, TypeInfo, TypeSystem
from pynguin.ga.operators.selection import RandomSelection, RankSelection, SelectionFunction
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
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


def test_generator_provider_add_tuple_type(generator_provider):
    class Foo:
        pass

    class Bar:
        pass

    foo_type = Instance(TypeInfo(Foo))
    bar_type = Instance(TypeInfo(Bar))
    int_type = Instance(TypeInfo(int))
    tuple_type = TupleType((foo_type, bar_type, int_type))

    generator = MagicMock()
    generator.generated_type.return_value = tuple_type

    generator_provider.add(generator)

    # Registered for the tuple itself
    assert generator in generator_provider.get_for_type(tuple_type)
    # Registered for non-primitive, non-None elements
    assert generator in generator_provider.get_for_type(foo_type)
    assert generator in generator_provider.get_for_type(bar_type)
    # Primitives in tuple are not registered as generators
    assert len(generator_provider.get_for_type(int_type)) == 0

    # Test remove_generator
    generator_provider.remove_generator(generator)
    assert len(generator_provider.get_for_type(tuple_type)) == 0
    assert len(generator_provider.get_for_type(foo_type)) == 0
    assert len(generator_provider.get_for_type(bar_type)) == 0


def test_generator_provider_add_for_type_tuple_type(generator_provider):
    class Foo:
        pass

    class Bar:
        pass

    foo_type = Instance(TypeInfo(Foo))
    bar_type = Instance(TypeInfo(Bar))
    int_type = Instance(TypeInfo(int))
    tuple_type = TupleType((foo_type, bar_type, int_type))

    generator = MagicMock()

    generator_provider.add_for_type(tuple_type, generator)

    # Registered for the tuple itself
    assert generator in generator_provider.get_for_type(tuple_type)
    # Registered for non-primitive, non-None elements
    assert generator in generator_provider.get_for_type(foo_type)
    assert generator in generator_provider.get_for_type(bar_type)
    # Primitives in tuple are not registered as generators
    assert len(generator_provider.get_for_type(int_type)) == 0


def test_generator_provider_add_for_type_primitive_and_none(generator_provider):
    generator = MagicMock()
    int_type = Instance(TypeInfo(int))
    none_type = NoneType()

    generator_provider.add_for_type(int_type, generator)
    generator_provider.add_for_type(none_type, generator)

    assert len(generator_provider.get_all_types()) == 0
    assert len(generator_provider.get_all()) == 0


def test_tuple_generator_fitness():
    class Foo:
        pass

    class Bar:
        pass

    class Baz:
        pass

    type_system = TypeSystem()
    fitness_fn = HeuristicGeneratorFitnessFunction(type_system)

    foo_type = Instance(type_system.to_type_info(Foo))
    bar_type = Instance(type_system.to_type_info(Bar))
    baz_type = Instance(type_system.to_type_info(Baz))
    tuple_type = TupleType((foo_type, bar_type))

    generator = MagicMock(GenericCallableAccessibleObject)
    generator.is_constructor.return_value = False
    generator.get_num_parameters.return_value = 0
    generator.inferred_signature = MagicMock()
    generator.inferred_signature.return_type = tuple_type

    # Distance to Foo should be finite (elem distance 0 + penalty 1)
    fitness_foo = fitness_fn.compute_fitness(foo_type, generator)
    assert fitness_foo != float("inf")

    # Distance to Bar should be finite
    fitness_bar = fitness_fn.compute_fitness(bar_type, generator)
    assert fitness_bar != float("inf")

    # Distance to Baz should be inf (not in tuple)
    fitness_baz = fitness_fn.compute_fitness(baz_type, generator)
    assert fitness_baz == float("inf")
