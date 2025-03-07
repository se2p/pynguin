from unittest import mock
from unittest.mock import MagicMock

from pynguin.analyses.generator import GeneratorProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import TypeInfo, Instance, NoneType
from pynguin.utils.generic.genericaccessibleobject import GenericMethod, \
    GenericConstructor, GenericFunction, GenericCallableAccessibleObject


# TODO: Get rid of code duplicate
@mock.patch("pynguin.utils.randomness.next_float")
def test_generator_provider_integration(rand_mock):
    rand_mock.side_effect = [0.0]

    cluster = generate_test_cluster("tests.fixtures.examples.constructors")
    type_system = cluster.type_system
    base_type: TypeInfo = type_system.find_type_info(
        "tests.fixtures.examples.constructors.Base")

    methods = {method.owner.full_name + "." + method.method_name: method for method in
               cluster.accessible_objects_under_test if isinstance(method, GenericMethod)}
    constructors = {constructor.owner.full_name: constructor for constructor in
                    cluster.accessible_objects_under_test if
                    isinstance(constructor, GenericConstructor)}
    functions = {function.function_name: function for function in
                 cluster.accessible_objects_under_test if
                 isinstance(function, GenericFunction)}
    merged = {**methods, **constructors, **functions}

    provider = GeneratorProvider(type_system)
    for generator in merged.values():
        provider.add(generator)

    proper_type = Instance(base_type)
    generators = provider.get_for_type(proper_type)
    generator = provider.select_generator(proper_type, generators)

    assert isinstance(generator, GenericMethod)
    assert generator.method_name == 'instance_constructor_with_args'


def test_generator_provider():
    class MyClass:
        pass

    type_system = MagicMock()
    provider = GeneratorProvider(type_system)
    generated_type = Instance(TypeInfo(MyClass))
    generator = mock.MagicMock(spec=GenericCallableAccessibleObject)
    generator.generated_type.return_value = generated_type

    provider.add(generator)
    retrieved_generators = provider.get_for_type(generated_type)
    retrieved_generator = provider.select_generator(generated_type, retrieved_generators)

    assert retrieved_generator == generator


def test_generator_provider_empty():
    fitness_function = MagicMock()
    provider = GeneratorProvider(fitness_function)
    generated_type = MagicMock()
    assert len(provider.get_for_type(generated_type)) == 0
    assert len(provider.get_all_types()) == 0
    assert len(provider.get_all()) == 0


def test_generator_provider_add_primitive():
    fitness_function = MagicMock()
    provider = GeneratorProvider(fitness_function)
    generated_type = Instance(TypeInfo(int))
    generator = MagicMock()
    generator.generated_type.return_value = generated_type
    provider.add(generator)
    assert len(provider.get_all_types()) == 0
    assert len(provider.get_all()) == 0


def test_generator_provider_add_no_generator():
    fitness_function = MagicMock()
    provider = GeneratorProvider(fitness_function)
    generator = MagicMock()
    generator.generated_type.return_value = NoneType()
    provider.add(generator)
    assert len(provider.get_all_types()) == 0
    assert len(provider.get_all()) == 0
