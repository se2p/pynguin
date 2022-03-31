#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from logging import Logger
from typing import Any, Union
from unittest.mock import MagicMock

import pytest
from ordered_set import OrderedSet

from pynguin.analyses import module
from pynguin.analyses.module import (
    ModuleTestCluster,
    TypeInferenceStrategy,
    _ParseResult,
    analyse_module,
    parse_module,
)
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES


@pytest.fixture(scope="module")
def parsed_module_no_dependencies() -> _ParseResult:
    return parse_module("tests.fixtures.cluster.no_dependencies")


@pytest.fixture(scope="module")
def parsed_module_complex_dependencies() -> _ParseResult:
    return parse_module("tests.fixtures.cluster.complex_dependencies")


@pytest.fixture
def module_test_cluster() -> ModuleTestCluster:
    return ModuleTestCluster()


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
        parsed_module_no_dependencies.syntax_tree.body[1].args.args[0].annotation.id
    )
    assert annotated_type == "float"
    assert (
        parsed_module_no_dependencies.type_inference_strategy
        is TypeInferenceStrategy.TYPE_HINTS
    )


def test_parse_module_check_for_no_type_hint():
    module_name = "tests.fixtures.cluster.no_dependencies"
    parse_result = parse_module(module_name, type_inference=TypeInferenceStrategy.NONE)
    annotated_type = parse_result.syntax_tree.body[1].args.args[0].annotation
    assert annotated_type is None
    assert parse_result.type_inference_strategy is TypeInferenceStrategy.NONE


def test_analyse_module(parsed_module_no_dependencies):
    test_cluster = analyse_module(parsed_module_no_dependencies)
    assert test_cluster.num_accessible_objects_under_test() == 5


def test_analyse_module_dependencies(parsed_module_complex_dependencies):
    test_cluster = analyse_module(parsed_module_complex_dependencies)
    assert test_cluster.num_accessible_objects_under_test() == 2
    assert len(test_cluster.generators) == 2
    assert len(test_cluster.modifiers) == 2


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
