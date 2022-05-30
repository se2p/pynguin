#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
import itertools
from logging import Logger
from typing import Any, Union, cast
from unittest.mock import MagicMock

import pytest
from ordered_set import OrderedSet

from pynguin.analyses import module
from pynguin.analyses.module import (
    ModuleTestCluster,
    TypeInferenceStrategy,
    _ParseResult,
    analyse_module,
    generate_test_cluster,
    parse_module,
)
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericConstructor,
    GenericEnum,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES


@pytest.fixture(scope="module")
def parsed_module_no_dependencies() -> _ParseResult:
    return parse_module("tests.fixtures.cluster.no_dependencies")


@pytest.fixture(scope="module")
def parsed_module_complex_dependencies() -> _ParseResult:
    return parse_module("tests.fixtures.cluster.complex_dependencies")


@pytest.fixture(scope="module")
def parsed_module_no_any_annotation() -> _ParseResult:
    return parse_module("tests.fixtures.cluster.no_any_annotations")


@pytest.fixture(scope="module")
def parsed_module_nested_functions() -> _ParseResult:
    return parse_module("tests.fixtures.cluster.nested_functions")


@pytest.fixture
def module_test_cluster() -> ModuleTestCluster:
    return ModuleTestCluster(linenos=-1)


def test_parse_module(parsed_module_no_dependencies):
    module_name = "tests.fixtures.cluster.no_dependencies"
    parse_result = parsed_module_no_dependencies
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == module_name
    assert parse_result.syntax_tree is not None


def test_parse_c_module():
    module.LOGGER = MagicMock(Logger)
    module_name = "jellyfish.cjellyfish"
    parse_result = parse_module(module_name)
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == module_name
    assert parse_result.syntax_tree is None
    module.LOGGER.warning.assert_called_once()


def test_parse_module_check_for_type_hint(parsed_module_no_dependencies):
    annotated_type = (
        parsed_module_no_dependencies.syntax_tree.body[2].args.args[0].annotation.id
    )
    assert annotated_type == "float"
    assert (
        parsed_module_no_dependencies.type_inference_strategy
        is TypeInferenceStrategy.TYPE_HINTS
    )


def test_parse_module_check_for_no_type_hint():
    module_name = "tests.fixtures.cluster.no_dependencies"
    parse_result = parse_module(module_name, type_inference=TypeInferenceStrategy.NONE)
    annotated_type = parse_result.syntax_tree.body[2].args.args[0].annotation
    assert annotated_type.id == "Any"
    assert parse_result.type_inference_strategy is TypeInferenceStrategy.NONE


def test_parse_module_add_from_typing_import_any_import(parsed_module_no_dependencies):
    import_statement = parsed_module_no_dependencies.syntax_tree.body[0]
    assert isinstance(import_statement, ast.ImportFrom)
    assert import_statement.module == "typing"
    assert import_statement.names[0].name == "Any"


def test_parse_module_not_add_from_typing_import_any_import(
    parsed_module_no_any_annotation,
):
    imports = len(
        [
            elem
            for elem in parsed_module_no_any_annotation.syntax_tree.body
            if isinstance(elem, ast.ImportFrom)
            and elem.module == "typing"
            and elem.names[0].name == "Any"
        ]
    )
    assert imports == 1


def test_parse_module_replace_no_annotation_by_any_parameter(
    parsed_module_no_any_annotation,
):
    function_args = parsed_module_no_any_annotation.syntax_tree.body[1].args
    assert function_args.args[0].annotation.id == "Any"
    assert function_args.args[1].annotation.id == "Any"
    assert function_args.args[2].annotation.id == "Any"


def test_parse_module_replace_no_annotation_by_any_return(
    parsed_module_no_any_annotation,
):
    foo_func_return = parsed_module_no_any_annotation.syntax_tree.body[1].returns.id
    bar_func_return = parsed_module_no_any_annotation.syntax_tree.body[2].returns.id
    baz_func_return = parsed_module_no_any_annotation.syntax_tree.body[3].returns.id
    faz_func_return = parsed_module_no_any_annotation.syntax_tree.body[4].returns
    assert foo_func_return == "Any"
    assert bar_func_return == "Any"
    assert baz_func_return == "Any"
    assert isinstance(faz_func_return, ast.Constant)
    assert faz_func_return.value is None


def test_analyse_module(parsed_module_no_dependencies):
    test_cluster = analyse_module(parsed_module_no_dependencies)
    assert test_cluster.num_accessible_objects_under_test() == 4


def test_analyse_module_dependencies(parsed_module_complex_dependencies):
    test_cluster = analyse_module(parsed_module_complex_dependencies)
    assert test_cluster.num_accessible_objects_under_test() == 1
    assert len(test_cluster.generators) == 2
    assert len(test_cluster.modifiers) == 1


def test_add_generator_primitive(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = int
    module_test_cluster.add_generator(generator)
    assert module_test_cluster.get_generators_for(int) == OrderedSet([])


def test_add_generator(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    module_test_cluster.add_generator(generator)
    assert module_test_cluster.get_generators_for(MagicMock) == OrderedSet([generator])


def test_add_generator_two(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    module_test_cluster.add_generator(generator)
    generator_2 = MagicMock(GenericMethod)
    generator_2.generated_type.return_value = MagicMock
    module_test_cluster.add_generator(generator_2)
    assert module_test_cluster.get_generators_for(MagicMock) == OrderedSet(
        [generator, generator_2]
    )


def test_add_accessible_object_under_test(module_test_cluster):
    aoc = MagicMock(GenericMethod)
    aoc_2 = MagicMock(GenericMethod)
    module_test_cluster.add_accessible_object_under_test(aoc, None)
    module_test_cluster.add_accessible_object_under_test(aoc_2, None)
    assert module_test_cluster.accessible_objects_under_test == OrderedSet([aoc, aoc_2])


def test_add_modifier(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(int, modifier)
    assert module_test_cluster.get_modifiers_for(int) == OrderedSet([modifier])


def test_add_modifier_two(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(int, modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(int, modifier2)
    assert module_test_cluster.get_modifiers_for(int) == OrderedSet(
        [modifier, modifier2]
    )


def test_get_random_modifier(module_test_cluster):
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(int, modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    module_test_cluster.add_modifier(int, modifier2)
    assert module_test_cluster.get_random_call_for(int) in {modifier, modifier2}


def test_get_random_modifier_none(module_test_cluster):
    with pytest.raises(ConstructionFailedException):
        module_test_cluster.get_random_call_for(int)


def test_get_modifier_none_available(module_test_cluster):
    assert module_test_cluster.get_modifiers_for(int) == OrderedSet()


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
        pytest.param(None, [None]),
        pytest.param(bool, [bool]),
        pytest.param(Union[int, float], [int, float]),
        pytest.param(Union, [None]),
    ],
)
def test_select_concrete_type_union_unary(type_, result, module_test_cluster):
    assert module_test_cluster.select_concrete_type(type_) in result


def test_select_concrete_type_any(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    module_test_cluster.add_generator(generator)
    assert module_test_cluster.select_concrete_type(Any) in list(PRIMITIVES) + list(
        COLLECTIONS
    ) + [MagicMock]


def test_get_all_generatable_types_only_primitive(module_test_cluster):
    assert module_test_cluster.get_all_generatable_types() == list(PRIMITIVES) + list(
        COLLECTIONS
    )


def test_get_all_generatable_types(module_test_cluster):
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    module_test_cluster.add_generator(generator)
    assert module_test_cluster.get_all_generatable_types() == [MagicMock] + list(
        PRIMITIVES
    ) + list(COLLECTIONS)


def __convert_to_str_count_dict(dic: dict[type, OrderedSet]) -> dict[str, int]:
    return {k.__name__: len(v) for k, v in dic.items()}


def __extract_method_names(
    accessible_objects: OrderedSet[GenericAccessibleObject],
) -> set[str]:
    return {
        f"{elem.owner.__name__}.{elem.callable.__name__}"
        if isinstance(elem, GenericMethod)
        else f"{elem.owner.__name__}.__init__"
        for elem in accessible_objects
    }


def test_accessible():
    cluster = generate_test_cluster("tests.fixtures.cluster.no_dependencies")
    assert len(cluster.accessible_objects_under_test) == 4


def test_nothing_from_blacklist():
    cluster = generate_test_cluster("tests.fixtures.cluster.blacklist")
    # Should only be foo and bar
    assert sum(len(cl) for cl in cluster.generators.values()) == 2
    assert cluster.num_accessible_objects_under_test() == 1


def test_nothing_included_multiple_times():
    cluster = generate_test_cluster("tests.fixtures.cluster.diamond_top")
    assert sum(len(cl) for cl in cluster.generators.values()) == 5
    assert cluster.num_accessible_objects_under_test() == 1


def test_generators():
    cluster = generate_test_cluster("tests.fixtures.cluster.no_dependencies")
    assert len(cluster.get_generators_for(int)) == 0
    assert len(cluster.get_generators_for(float)) == 0
    assert __convert_to_str_count_dict(cluster.generators) == {"Test": 1}
    assert cluster.num_accessible_objects_under_test() == 4


def test_simple_dependencies():
    cluster = generate_test_cluster("tests.fixtures.cluster.simple_dependencies")
    assert __convert_to_str_count_dict(cluster.generators) == {
        "SomeArgumentType": 1,
        "ConstructMeWithDependency": 1,
    }
    assert cluster.num_accessible_objects_under_test() == 1


def test_complex_dependencies():
    cluster = generate_test_cluster("tests.fixtures.cluster.complex_dependencies")
    assert cluster.num_accessible_objects_under_test() == 1


def test_modifier():
    cluster = generate_test_cluster("tests.fixtures.cluster.complex_dependencies")
    assert len(cluster.modifiers) == 1


def test_simple_dependencies_only_own_classes():
    cluster = generate_test_cluster("tests.fixtures.cluster.simple_dependencies")
    assert len(cluster.accessible_objects_under_test) == 1


def test_resolve_dependencies():
    cluster = generate_test_cluster("tests.fixtures.cluster.typing_parameters")
    assert len(cluster.accessible_objects_under_test) == 3
    assert len(cluster.generators) == 3


def test_resolve_optional():
    cluster = generate_test_cluster("tests.fixtures.cluster.typing_parameters")
    assert type(None) not in cluster.generators


def test_private_method_not_added():
    cluster = generate_test_cluster("tests.fixtures.examples.private_methods")
    assert len(cluster.accessible_objects_under_test) == 1
    assert isinstance(
        next(iter(cluster.accessible_objects_under_test)), GenericConstructor
    )


def test_overridden_inherited_methods():
    cluster = generate_test_cluster(
        "tests.fixtures.cluster.overridden_inherited_methods"
    )
    accessible_objects = cluster.accessible_objects_under_test
    methods = __extract_method_names(accessible_objects)
    expected = {"Foo.__init__", "Foo.foo", "Foo.__iter__", "Bar.__init__", "Bar.foo"}
    assert methods == expected


def test_conditional_import_forward_ref():
    cluster = generate_test_cluster("tests.fixtures.cluster.conditional_import")
    accessible_objects = list(cluster.accessible_objects_under_test)
    constructor = cast(GenericConstructor, accessible_objects[0])
    assert (
        str(constructor.inferred_signature.parameters["arg0"])
        == "<class 'tests.fixtures.cluster.complex_dependency.SomeOtherType'>"
    )


def test_enums():
    cluster = generate_test_cluster("tests.fixtures.cluster.enums")
    accessible_objects = cast(
        list[GenericEnum], list(cluster.accessible_objects_under_test)
    )
    assert {enum.owner.__name__: set(enum.names) for enum in accessible_objects} == {
        "Color": {"RED", "BLUE", "GREEN"},
        "Foo": {"FOO", "BAR"},
        "Inline": {"MAYBE", "YES", "NO"},
    }


@pytest.mark.parametrize(
    "module_name",
    [pytest.param("cluster.comments"), pytest.param("instrumentation.mixed")],
)
def test_analyse_async_function_or_method(module_name):
    with pytest.raises(ValueError):
        generate_test_cluster(f"tests.fixtures.{module_name}")


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
