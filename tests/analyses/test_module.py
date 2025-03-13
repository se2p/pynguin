#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import itertools
from logging import Logger
from typing import Union, cast
from unittest.mock import MagicMock, patch

import astroid
import pytest
from pynguin.analyses.type_inference import HintInference

import pynguin.configuration as config
from pynguin.analyses import module
from pynguin.analyses.generator import GeneratorProvider
from pynguin.analyses.generator import RandomGeneratorProvider
from pynguin.analyses.module import (
    MODULE_BLACKLIST,
    ModuleTestCluster,
    TypeInferenceStrategy,
    _ModuleParseResult,
    analyse_module,
    generate_test_cluster,
    parse_module,
)
from pynguin.analyses.typesystem import ANY, AnyType, ProperType, TypeInfo, UnionType
from pynguin.ga.operators.selection import RandomSelection
from pynguin.ga.operators.selection import RankSelection
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.exceptions import CoroutineFoundException
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericEnum
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES


@pytest.fixture(scope="module")
def parsed_module_no_dependencies() -> _ModuleParseResult:
    return parse_module("tests.fixtures.cluster.no_dependencies")


@pytest.fixture(scope="module")
def parsed_module_complex_dependencies() -> _ModuleParseResult:
    return parse_module("tests.fixtures.cluster.complex_dependencies")


@pytest.fixture(scope="module")
def parsed_module_no_any_annotation() -> _ModuleParseResult:
    return parse_module("tests.fixtures.cluster.no_any_annotations")  # pragma: no cover


@pytest.fixture(scope="module")
def parsed_module_nested_functions() -> _ModuleParseResult:
    return parse_module("tests.fixtures.cluster.nested_functions")


@pytest.fixture(scope="module")
def parsed_module_lambda() -> _ModuleParseResult:
    return parse_module("tests.fixtures.cluster.lambda")


@pytest.fixture(scope="module")
def parsed_module_unnamed_lambda() -> _ModuleParseResult:
    return parse_module("tests.fixtures.cluster.unnamed_lambda")


@pytest.fixture
def module_test_cluster() -> ModuleTestCluster:
    return ModuleTestCluster(linenos=-1)


def test_parse_module(parsed_module_no_dependencies):
    module_name = "tests.fixtures.cluster.no_dependencies"
    parse_result = parsed_module_no_dependencies
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == module_name
    assert parse_result.syntax_tree is not None


def test_parse_native_module():
    module.LOGGER = MagicMock(Logger)
    module_name = "libcst.native"
    parse_result = parse_module(module_name)
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == module_name
    assert parse_result.syntax_tree is None
    module.LOGGER.debug.assert_called_once()


@pytest.mark.parametrize("exception_type", [TypeError, OSError, astroid.AstroidError])
@patch("astroid.parse")
def test_parse_module_exceptions(mock_parse, exception_type):
    mock_parse.side_effect = exception_type("Mocked Exception")
    module.LOGGER = MagicMock(Logger)
    module_name = "tests.fixtures.cluster.no_dependencies"
    result = parse_module(module_name)
    assert result.module_name == module_name
    assert result.syntax_tree is None
    assert result.linenos == -1
    module.LOGGER.debug.assert_called_once()


def test_parse_alias_module():
    module.LOGGER = MagicMock(Logger)
    module_name = "tests.fixtures.cluster.dependency"
    alias_name = "tests.fixtures.cluster.alias_module.dep"
    parse_result = parse_module(alias_name)
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == alias_name
    assert parse_result.syntax_tree is not None


def test_analyse_module(parsed_module_no_dependencies):
    test_cluster = analyse_module(parsed_module_no_dependencies)
    assert test_cluster.num_accessible_objects_under_test() == 4


def test_analyse_module_dependencies(parsed_module_complex_dependencies):
    test_cluster = analyse_module(parsed_module_complex_dependencies)
    assert test_cluster.num_accessible_objects_under_test() == 1
    assert len(test_cluster.generators) == 3
    assert len(test_cluster.modifiers) == 1


def test_add_generator_primitive(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = module_test_cluster.type_system.convert_type_hint(int)
    module_test_cluster.add_generator(generator)
    assert module_test_cluster.get_generators_for(
        module_test_cluster.type_system.convert_type_hint(int)
    ) == (OrderedSet([]))


@pytest.mark.parametrize(
    "generator_selection", [config.Selection.RANK_SELECTION, config.Selection.RANDOM_SELECTION]
)
def test_add_generator(module_test_cluster, generator_selection):
    config.configuration.generator_selection.generator_selection_algorithm = generator_selection
    type_hint = module_test_cluster.type_system.convert_type_hint(MagicMock)
    generator = MagicMock(GenericCallableAccessibleObject)
    generator.inferred_signature.return_type = type_hint
    generator.generated_type.return_value = type_hint
    generator.get_num_parameters.return_value = 0
    module_test_cluster.add_generator(generator)
    assert module_test_cluster.get_generators_for(
        module_test_cluster.type_system.convert_type_hint(MagicMock)
    ) == (OrderedSet([generator]))


@pytest.mark.parametrize(
    "generator_selection", [config.Selection.RANK_SELECTION, config.Selection.RANDOM_SELECTION]
)
def test_add_generator_two(module_test_cluster, generator_selection):
    config.configuration.generator_selection.generator_selection_algorithm = generator_selection
    type_hint = module_test_cluster.type_system.convert_type_hint(MagicMock)

    generator = MagicMock(GenericCallableAccessibleObject)
    generator.inferred_signature.return_type = type_hint
    generator.generated_type.return_value = type_hint
    generator.get_num_parameters.return_value = 0
    module_test_cluster.add_generator(generator)

    generator_2 = MagicMock(GenericCallableAccessibleObject)
    generator_2.inferred_signature.return_type = type_hint
    generator_2.generated_type.return_value = type_hint
    generator_2.get_num_parameters.return_value = 0
    module_test_cluster.add_generator(generator_2)

    retrieved_generators = module_test_cluster.generator_provider._get_generators_for(
        module_test_cluster.type_system.convert_type_hint(MagicMock)
    )
    generator_methods = OrderedSet([gen.generator for gen in retrieved_generators])
    assert generator_methods == (OrderedSet([generator, generator_2]))


@pytest.mark.parametrize("generator_provider", [GeneratorProvider, RandomGeneratorProvider])
def test_get_generators_for_any_type(generator_provider):
    type_system = MagicMock()
    selection_function = MagicMock()
    provider = generator_provider(type_system, selection_function)

    mock_generators = OrderedSet([MagicMock(), MagicMock(), MagicMock()])
    provider._get_all_generators = MagicMock(return_value=mock_generators)

    result = provider._get_generators_for(AnyType())

    provider._get_all_generators.assert_called_once_with(AnyType())
    assert result == mock_generators


def test_add_accessible_object_under_test(module_test_cluster):
    aoc = MagicMock(GenericMethod)
    aoc_2 = MagicMock(GenericMethod)
    module_test_cluster.add_accessible_object_under_test(aoc, None)
    module_test_cluster.add_accessible_object_under_test(aoc_2, None)
    assert module_test_cluster.accessible_objects_under_test == OrderedSet([aoc, aoc_2])


def test_add_modifier(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = module_test_cluster.type_system.convert_type_hint(
        MagicMock
    )
    module_test_cluster.add_modifier(
        module_test_cluster.type_system.to_type_info(MagicMock), modifier
    )
    assert module_test_cluster.get_modifiers_for(
        module_test_cluster.type_system.convert_type_hint(MagicMock)
    ) == OrderedSet([modifier])


def test_add_modifier_two(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(module_test_cluster.type_system.to_type_info(int), modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(module_test_cluster.type_system.to_type_info(int), modifier2)
    assert module_test_cluster.get_modifiers_for(
        module_test_cluster.type_system.convert_type_hint(int)
    ) == OrderedSet([modifier, modifier2])


def test_get_random_modifier(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(module_test_cluster.type_system.to_type_info(int), modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(module_test_cluster.type_system.to_type_info(int), modifier2)
    assert module_test_cluster.get_random_call_for(
        module_test_cluster.type_system.convert_type_hint(int)
    ) in {modifier, modifier2}


def test_get_random_modifier_none(module_test_cluster):
    with pytest.raises(ConstructionFailedException):
        module_test_cluster.get_random_call_for(
            module_test_cluster.type_system.convert_type_hint(int)
        )


def test_get_modifier_none_available(module_test_cluster):
    assert (
        module_test_cluster.get_modifiers_for(
            module_test_cluster.type_system.convert_type_hint(int)
        )
        == OrderedSet()
    )


def test_get_random_accessible(module_test_cluster):
    assert module_test_cluster.get_random_accessible() is None


def test_get_random_accessible_two(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier2 = MagicMock(GenericMethod)
    module_test_cluster.add_accessible_object_under_test(modifier, None)
    module_test_cluster.add_accessible_object_under_test(modifier2, None)
    assert module_test_cluster.get_random_accessible() in {modifier, modifier2}


@pytest.mark.parametrize(
    "type_, result",
    [
        pytest.param(bool, [bool]),
        pytest.param(Union[int, float], [int, float]),  # noqa: UP007
    ],
)
def test_select_concrete_type_union_unary(type_, result, module_test_cluster):
    assert module_test_cluster.select_concrete_type(
        module_test_cluster.type_system.convert_type_hint(type_)
    ) in [module_test_cluster.type_system.convert_type_hint(res) for res in result]


def test_select_concrete_type_any(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = module_test_cluster.type_system.convert_type_hint(
        MagicMock
    )
    module_test_cluster.add_generator(generator)
    assert (
        module_test_cluster.select_concrete_type(AnyType())
        in module_test_cluster.get_all_generatable_types()
    )


def test_get_all_generatable_types_only_builtin(module_test_cluster):
    expected = {
        module_test_cluster.type_system.convert_type_hint(typ)
        for typ in list(PRIMITIVES) + list(COLLECTIONS)
    }
    assert set(module_test_cluster.get_all_generatable_types()) == set(expected)


def test_get_all_generatable_types(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = module_test_cluster.type_system.convert_type_hint(
        MagicMock
    )
    module_test_cluster.add_generator(generator)
    expected = {
        module_test_cluster.type_system.convert_type_hint(typ)
        for typ in list(PRIMITIVES) + list(COLLECTIONS) + [MagicMock]
    }
    assert set(module_test_cluster.get_all_generatable_types()) == set(expected)


def __convert_to_str_count_dict(dic: dict[ProperType, OrderedSet]) -> dict[str, int]:
    return {k.type.name: len(v) for k, v in dic.items()}


def __extract_method_names(
    accessible_objects: OrderedSet[GenericAccessibleObject],
) -> set[str]:
    return {
        (
            f"{elem.owner.name}.{elem.callable.__name__}"
            if isinstance(elem, GenericMethod)
            else f"{elem.owner.name}.__init__"
        )
        for elem in accessible_objects
    }


def test_accessible():
    cluster = generate_test_cluster(
        "tests.fixtures.cluster.no_dependencies", TypeInferenceStrategy.NONE
    )
    assert len(cluster.accessible_objects_under_test) == 4


def test_nothing_from_blacklist():
    cluster = generate_test_cluster("tests.fixtures.cluster.blacklist")
    # Should only be foo, bar and object.
    assert sum(len(cl) for cl in cluster.generators.values()) == 3
    assert cluster.num_accessible_objects_under_test() == 1


def test_blacklist_is_valid():
    # Naive test without assert, checks if the module names are valid.
    allowed_to_fail = ("six",)
    for item in MODULE_BLACKLIST:
        if item in allowed_to_fail:
            # We have modules in our blacklist that are not a dependency of Pynguin,
            # thus the import might fail.
            continue
        importlib.import_module(item)


def test_nothing_included_multiple_times():
    cluster = generate_test_cluster("tests.fixtures.cluster.diamond_top")
    assert sum(len(cl) for cl in cluster.generators.values()) == 6
    assert cluster.num_accessible_objects_under_test() == 1


@pytest.mark.parametrize(
    "generator_selection", [config.Selection.RANK_SELECTION, config.Selection.RANDOM_SELECTION]
)
def test_generators(generator_selection):
    config.configuration.generator_selection.generator_selection_algorithm = generator_selection
    cluster = generate_test_cluster("tests.fixtures.cluster.no_dependencies")
    assert (
        len(
            cluster.generator_provider._get_generators_for(
                cluster.type_system.convert_type_hint(int)
            )
        )
        == 0
    )
    assert (
        len(
            cluster.generator_provider._get_generators_for(
                cluster.type_system.convert_type_hint(float)
            )
        )
        == 0
    )
    assert __convert_to_str_count_dict(cluster.generators) == {"Test": 1, "object": 1}
    assert cluster.num_accessible_objects_under_test() == 4


def test_simple_dependencies():
    cluster = generate_test_cluster("tests.fixtures.cluster.simple_dependencies")
    assert __convert_to_str_count_dict(cluster.generators) == {
        "SomeArgumentType": 1,
        "ConstructMeWithDependency": 1,
        "object": 1,
    }
    assert cluster.num_accessible_objects_under_test() == 1


def test_complex_dependencies():
    cluster = generate_test_cluster("tests.fixtures.cluster.complex_dependencies")
    assert cluster.num_accessible_objects_under_test() == 1


@pytest.mark.parametrize(
    "generator_selection", [config.Selection.RANK_SELECTION, config.Selection.RANDOM_SELECTION]
)
def test_inheritance_generator(generator_selection):
    config.configuration.generator_selection.generator_selection_algorithm = generator_selection
    cluster = generate_test_cluster("tests.fixtures.cluster.inheritance")
    from tests.fixtures.cluster.inheritance import (  # noqa: PLC0415
        Bar,
        Foo,
    )

    res_foo = cluster.generator_provider._get_generators_for(
        cluster.type_system.convert_type_hint(Foo)
    )
    assert len(res_foo) == 2
    res_bar = cluster.generator_provider._get_generators_for(
        cluster.type_system.convert_type_hint(Bar)
    )
    assert len(res_bar) == 1


def test_inheritance_modifier():
    cluster = generate_test_cluster("tests.fixtures.cluster.inheritance")
    from tests.fixtures.cluster.inheritance import (  # noqa: PLC0415
        Bar,
        Foo,
    )

    assert len(cluster.get_modifiers_for(cluster.type_system.convert_type_hint(Bar))) == 2
    assert len(cluster.get_modifiers_for(cluster.type_system.convert_type_hint(Foo))) == 1


def test_modifier():
    cluster = generate_test_cluster("tests.fixtures.cluster.complex_dependencies")
    assert len(cluster.modifiers) == 1


def test_simple_dependencies_only_own_classes():
    cluster = generate_test_cluster("tests.fixtures.cluster.simple_dependencies")
    assert len(cluster.accessible_objects_under_test) == 1


def test_resolve_dependencies():
    cluster = generate_test_cluster("tests.fixtures.cluster.typing_parameters")
    assert len(cluster.accessible_objects_under_test) == 3
    assert len(cluster.generators) == 4


def test_resolve_optional():
    cluster = generate_test_cluster("tests.fixtures.cluster.typing_parameters")
    assert type(None) not in cluster.generators


def test_private_method_not_added():
    cluster = generate_test_cluster("tests.fixtures.examples.private_methods")
    assert len(cluster.accessible_objects_under_test) == 1
    assert isinstance(next(iter(cluster.accessible_objects_under_test)), GenericConstructor)


def test_overridden_inherited_methods():
    cluster = generate_test_cluster("tests.fixtures.cluster.overridden_inherited_methods")
    accessible_objects = cluster.accessible_objects_under_test
    methods = __extract_method_names(accessible_objects)
    expected = {"Foo.__init__", "Foo.foo", "Foo.__iter__", "Bar.__init__", "Bar.foo"}
    assert methods == expected


def test_conditional_import_forward_ref():
    cluster = generate_test_cluster("tests.fixtures.cluster.conditional_import")
    accessible_objects = list(cluster.accessible_objects_under_test)
    constructor = cast("GenericConstructor", accessible_objects[0])
    assert constructor.inferred_signature.original_parameters["arg0"] == AnyType()


def test_enums():
    cluster = generate_test_cluster("tests.fixtures.cluster.enums")
    accessible_objects = cast("list[GenericEnum]", list(cluster.accessible_objects_under_test))
    assert {enum.owner.name: set(enum.names) for enum in accessible_objects} == {
        "Color": {"RED", "BLUE", "GREEN"},
        "Foo": {"FOO", "BAR"},
        "Inline": {"MAYBE", "YES", "NO"},
    }


@pytest.mark.parametrize(
    "module_name",
    ["async_func", "async_gen", "async_class_gen", "async_class_method"],
)
def test_analyse_async_function_or_method(module_name):
    with pytest.raises(CoroutineFoundException):
        generate_test_cluster(f"tests.fixtures.cluster.{module_name}")


def test_analyse_async_as_dependency():
    cluster = generate_test_cluster("tests.fixtures.cluster.uses_async_dependency")
    assert len(cluster.generators) == 4
    assert len(cluster.modifiers) == 0
    assert len(cluster.accessible_objects_under_test) == 1


def test_import_dependency():
    cluster = generate_test_cluster("tests.fixtures.cluster.import_dependency")
    assert len(cluster.accessible_objects_under_test) == 3
    # The numbers of the following values change depending on whether we run the test
    # from PyCharm or from the command line.  Thus, use a very weak assertion to only
    # ensures that the analysis of the included modules has found at least something.
    # TODO Improve this test
    assert len(cluster.generators) > 2
    assert len(cluster.modifiers) > 0


def test_analyse_nested_functions(parsed_module_nested_functions):
    test_cluster = analyse_module(parsed_module_nested_functions)
    assert test_cluster.num_accessible_objects_under_test() == 1
    func = test_cluster.accessible_objects_under_test.pop()
    assert isinstance(func, GenericFunction)
    assert func.function_name == "table_row"


def test_analyse_empty_enum_module():
    def extract_enum_without_fields(enum: GenericAccessibleObject) -> bool:
        return isinstance(enum, GenericEnum) and len(enum.names) == 0

    cluster = generate_test_cluster("enum")
    enums_without_fields = list(
        filter(
            extract_enum_without_fields,
            itertools.chain.from_iterable(cluster.generators.values()),
        )
    )
    assert len(enums_without_fields) == 0


def test_no_abstract_class():
    cluster = generate_test_cluster("tests.fixtures.cluster.abstract")
    assert len(cluster.accessible_objects_under_test) == 1
    assert len(cluster.generators) == 3
    assert len(cluster.modifiers) == 1


def test_inheritance_graph():
    cluster = generate_test_cluster("tests.fixtures.cluster.inheritance")
    assert (
        len(cluster.type_system.get_subclasses(TypeInfo(object)))
        == len(COLLECTIONS)
        + len(PRIMITIVES)
        + len(cluster.type_system.get_subclasses(TypeInfo(str)))
        + 2
    )


@pytest.mark.parametrize(
    "mod,typ,attributes",
    [
        ("tests.fixtures.cluster.attributes", "SomeClass", OrderedSet(["foo", "bar"])),
        (
            "tests.fixtures.cluster.attributes",
            "SomeDataClass",
            OrderedSet(["baz", "box"]),
        ),
    ],
)
def test_instance_attrs(mod, typ, attributes):
    cluster = generate_test_cluster(mod)
    assert cluster.type_system.find_type_info(f"{mod}.{typ}").instance_attributes == attributes


@pytest.mark.parametrize(
    "first, second, result",
    [
        (int, bool, bool | int),
        (int | bool, bool, bool | int),
        (int | bool, float, int | bool | float),
        (int | str | bool | bytes | float, bool, int | str | bool | bytes | float),
    ],
)
def test__add_or_make_union(type_system, first, second, result):
    assert ModuleTestCluster._add_or_make_union(
        type_system.convert_type_hint(first), type_system.convert_type_hint(second)
    ) == type_system.convert_type_hint(result)


def test__add_or_make_union_2(type_system):
    assert ModuleTestCluster._add_or_make_union(
        ANY, type_system.convert_type_hint(int)
    ) == UnionType((type_system.convert_type_hint(int),))


class CustomError(Exception):
    pass


def test_exception_during_inspect_getmembers(parsed_module_no_dependencies):
    with patch("inspect.getmembers", side_effect=CustomError):
        test_cluster = analyse_module(parsed_module_no_dependencies)
        assert test_cluster.num_accessible_objects_under_test() == 3  # one less (failed)


def test_analyse_module_lambda(parsed_module_lambda):
    test_cluster = analyse_module(parsed_module_lambda)
    assert test_cluster.num_accessible_objects_under_test() == 3
    objects = list(test_cluster.accessible_objects_under_test)
    lambda1 = cast("GenericFunction", objects[0])
    assert lambda1.function_name == "y"
    lambda2 = cast("GenericFunction", objects[1])
    assert lambda2.function_name == "abc"
    lambda3 = cast("GenericFunction", objects[2])
    assert lambda3.function_name == "salam_aleykum"


def test_analyse_function_lambda_no_name():
    """Test that __analyse_function returns early when no name for a lambda is found."""
    # Create a test cluster
    test_cluster = ModuleTestCluster(linenos=-1)

    # Create a lambda function
    lambda_func = lambda x: x  # noqa: E731

    # create a type inference provider
    type_inference_provider = HintInference()

    # Mock the _get_lambda_assigned_name function to return None
    with patch("pynguin.analyses.module._get_lambda_assigned_name", return_value=None):
        # Call __analyse_function directly
        module.__analyse_function(
            func_name="<lambda>",
            func=lambda_func,
            type_inference_provider=type_inference_provider,
            module_tree=None,
            test_cluster=test_cluster,
            add_to_test=True,
        )

    # Verify that the lambda was not added to the test cluster
    assert test_cluster.num_accessible_objects_under_test() == 0


@pytest.mark.parametrize(
    "subprocess,subprocess_if_recommended,expected_subprocess_mode",
    [
        (False, False, "False"),
        (True, False, "True"),
        (False, True, "True"),
        (True, True, "True"),
    ],
)
def test_analyse_module_not_sets_c_if_not_recommended(
    monkeypatch, subprocess, subprocess_if_recommended, expected_subprocess_mode
):
    tracked = {}

    def fake_track_output_variable(var, value):
        tracked[var] = value

    monkeypatch.setattr(module.stat, "track_output_variable", fake_track_output_variable)
    monkeypatch.setattr(module.config.configuration, "subprocess", subprocess)
    monkeypatch.setattr(
        module.config.configuration, "subprocess_if_recommended", subprocess_if_recommended
    )
    parse_result = module.parse_module("_ctypes")
    module.analyse_module(parse_result)
    assert tracked[RuntimeVariable.SubprocessMode] == expected_subprocess_mode, (
        f"Expected subprocess mode to be {expected_subprocess_mode}, "
        f"but got {tracked[RuntimeVariable.SubprocessMode]}"
    )


@pytest.mark.parametrize(
    "module_name,expected_subprocess_value,expected_c_ext_present",
    [
        ("_ctypes", True, "_ctypes"),
        ("tests.fixtures.c.my_ctypes", True, "_ctypes"),  # imports _ctypes
        ("_abc", False, None),  # _abc is whitelisted
    ],
)
def test_analyse_module_sets_c_extension_and_subprocess(
    monkeypatch, module_name, expected_subprocess_value, expected_c_ext_present
):
    tracked = {}

    def fake_track_output_variable(var, value):
        tracked[var] = value

    monkeypatch.setattr(module.stat, "track_output_variable", fake_track_output_variable)
    monkeypatch.setattr(module.config.configuration, "subprocess", False)
    monkeypatch.setattr(module.config.configuration, "subprocess_if_recommended", True)

    parse_result = module.parse_module(module_name)
    module.analyse_module(parse_result)

    # Check C extension tracking
    if expected_c_ext_present is not None:
        assert RuntimeVariable.CExtensionModules in tracked, "CExtensionModules not tracked"
        assert expected_c_ext_present in tracked[RuntimeVariable.CExtensionModules], (
            f"Expected {expected_c_ext_present} to be tracked as C extension, "
            f"but got {tracked[RuntimeVariable.CExtensionModules]}"
        )

    # Check subprocess mode tracking
    assert RuntimeVariable.SubprocessMode in tracked, "SubprocessMode not tracked"
    assert tracked[RuntimeVariable.SubprocessMode] == str(expected_subprocess_value), (
        f"Expected subprocess mode to be {expected_subprocess_value}, "
        f"but got {tracked[RuntimeVariable.SubprocessMode]}"
    )


@pytest.mark.parametrize(
    "config_selection_function, created_selection_function",
    [
        (config.Selection.RANDOM_SELECTION, RandomSelection),
        (config.Selection.RANK_SELECTION, RankSelection),
    ],
)
def test_create_module_test_cluster(config_selection_function, created_selection_function):
    config.configuration.generator_selection.generator_selection_algorithm = (
        config_selection_function
    )
    test_cluster = ModuleTestCluster(linenos=-1)
    assert test_cluster.generator_provider is not None
    assert test_cluster.generator_provider._selection_function is not None
    assert isinstance(
        test_cluster.generator_provider._selection_function, created_selection_function
    )


def test_create_module_test_cluster_tournament_selection():
    config.configuration.generator_selection.generator_selection_algorithm = (
        config.Selection.TOURNAMENT_SELECTION
    )
    with pytest.raises(ValueError, match="Unsupported generator selection algorithm"):
        ModuleTestCluster(linenos=-1)
