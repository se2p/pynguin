#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import cast

from ordered_set import OrderedSet

import pynguin.configuration as config
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericConstructor,
    GenericEnum,
    GenericMethod,
)


def convert_to_str_count_dict(dic: dict[type, OrderedSet]) -> dict[str, int]:
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
    config.configuration.type_inference.max_cluster_recursion = 1
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


def test_resolve_dependenices():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.typing_parameters"
    ).generate_cluster()
    # 3 functions
    assert len(cluster.accessible_objects_under_test) == 3
    # 3 non primitive types in args
    assert len(cluster.generators) == 3


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


def test_overridden_inherited_methods():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.overridden_inherited_methods"
    ).generate_cluster()
    accessible_objects = cluster.accessible_objects_under_test
    methods = _extract_method_names(accessible_objects)
    expected = {"Foo.__init__", "Foo.foo", "Foo.__iter__", "Bar.__init__", "Bar.foo"}
    assert methods == expected


def _extract_method_names(
    accessible_objects: OrderedSet[GenericAccessibleObject],
) -> set[str]:
    return {
        f"{elem.owner.__name__}.{elem.callable.__name__}"
        if isinstance(elem, GenericMethod)
        else f"{elem.owner.__name__}.__init__"
        for elem in accessible_objects
    }


def test_conditional_import_forward_ref():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.conditional_import"
    ).generate_cluster()
    accessible_objects = list(cluster.accessible_objects_under_test)
    constructor = cast(GenericConstructor, accessible_objects[0])
    assert (
        str(constructor.inferred_signature.parameters["arg0"])
        == "<class 'tests.fixtures.cluster.complex_dependency.SomeOtherType'>"
    )


def test_enums():
    cluster = TestClusterGenerator("tests.fixtures.cluster.enums").generate_cluster()
    accessible_objects = cast(
        list[GenericEnum], list(cluster.accessible_objects_under_test)
    )
    assert {enum.owner.__name__: set(enum.names) for enum in accessible_objects} == {
        "Color": {"RED", "BLUE", "GREEN"},
        "Foo": {"FOO", "BAR"},
        "Inline": {"MAYBE", "YES", "NO"},
    }
