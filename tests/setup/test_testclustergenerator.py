#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import os
from typing import Dict, Set, Type

import pytest

import pynguin.configuration as config
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy
from pynguin.typeinference.stubstrategy import StubInferenceStrategy
from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericConstructor,
    GenericMethod,
)


def convert_to_str_count_dict(dic: Dict[Type, Set]) -> Dict[str, int]:
    return {k.__name__: len(v) for k, v in dic.items()}


def test_accessible():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.no_dependencies"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 4


def test_generators():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.no_dependencies"
    ).generate_cluster()

    assert len(cluster.get_generators_for(int)) == 0
    assert len(cluster.get_generators_for(float)) == 0
    assert convert_to_str_count_dict(cluster.generators) == {"Test": 1}


def test_simple_dependencies():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.simple_dependencies"
    ).generate_cluster()
    assert convert_to_str_count_dict(cluster.generators) == {
        "SomeArgumentType": 1,
        "ConstructMeWithDependency": 1,
    }


def test_complex_dependencies():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.complex_dependencies"
    ).generate_cluster()
    assert cluster.num_accessible_objects_under_test() == 1


def test_max_recursion():
    config.INSTANCE.max_cluster_recursion = 1
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.complex_dependencies"
    ).generate_cluster()
    assert len(cluster.generators) == 2


def test_modifier():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.complex_dependencies"
    ).generate_cluster()
    assert len(cluster.modifiers) == 2


def test_simple_dependencies_only_own_classes():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.simple_dependencies"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 1


def test_resolve_only_union():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.typing_parameters"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 3
    assert len(cluster.generators) == 1


def test_resolve_optional():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.typing_parameters"
    ).generate_cluster()
    assert type(None) not in cluster.generators


def test_private_method_not_added():
    cluster = TestClusterGenerator(
        "tests.fixtures.examples.private_methods"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 1
    assert isinstance(
        next(iter(cluster.accessible_objects_under_test)), GenericConstructor
    )


@pytest.mark.parametrize(
    "inference_strategy, obj",
    [
        pytest.param(config.TypeInferenceStrategy.NONE, NoTypeInferenceStrategy),
        pytest.param(config.TypeInferenceStrategy.STUB_FILES, StubInferenceStrategy),
        pytest.param(
            config.TypeInferenceStrategy.TYPE_HINTS, TypeHintsInferenceStrategy
        ),
    ],
)
def test_initialise_type_inference_strategies(inference_strategy, obj):
    config.INSTANCE.type_inference_strategy = inference_strategy
    config.INSTANCE.stub_dir = os.devnull
    generator = TestClusterGenerator("")
    assert isinstance(generator._inference._strategies[0], obj)


def test_initialise_stub_inference_strategy_exception():
    config.INSTANCE.type_inference_strategy = config.TypeInferenceStrategy.STUB_FILES
    with pytest.raises(ConfigurationException):
        TestClusterGenerator("")


def test_initialise_unknown_type_inference_strategies():
    config.INSTANCE.type_inference_strategy = "foo"
    with pytest.raises(ConfigurationException):
        TestClusterGenerator("")


def test_overridden_inherited_methods():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.overridden_inherited_methods"
    ).generate_cluster()
    accessible_objects = cluster.accessible_objects_under_test
    methods = _extract_method_names(accessible_objects)
    expected = {"Foo.__init__", "Foo.foo", "Foo.__iter__", "Bar.__init__", "Bar.foo"}
    assert methods == expected


def _extract_method_names(accessible_objects: Set[GenericAccessibleObject]) -> Set[str]:
    return {
        f"{elem.owner.__name__}.{elem.callable.__name__}"
        if isinstance(elem, GenericMethod)
        else f"{elem.owner.__name__}.__init__"
        for elem in accessible_objects
    }
