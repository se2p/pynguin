#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Any, Union
from unittest.mock import MagicMock

import pytest
from ordered_set import OrderedSet

from pynguin.setup.testcluster import FullTestCluster
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES


def test_add_generator_primitive():
    cluster = FullTestCluster()
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = int
    cluster.add_generator(generator)
    assert cluster.get_generators_for(int) == OrderedSet([])


def test_add_generator():
    cluster = FullTestCluster()
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    cluster.add_generator(generator)
    assert cluster.get_generators_for(MagicMock) == OrderedSet([generator])


def test_add_generator_two():
    cluster = FullTestCluster()
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    cluster.add_generator(generator)
    generator2 = MagicMock(GenericMethod)
    generator2.generated_type.return_value = MagicMock
    cluster.add_generator(generator2)
    assert cluster.get_generators_for(MagicMock) == OrderedSet([generator, generator2])


def test_add_accessible_object_under_test():
    cluster = FullTestCluster()
    aoc = MagicMock(GenericMethod)
    aoc2 = MagicMock(GenericMethod)
    cluster.add_accessible_object_under_test(aoc)
    cluster.add_accessible_object_under_test(aoc2)
    assert cluster.accessible_objects_under_test == OrderedSet([aoc, aoc2])


def test_add_modifier():
    cluster = FullTestCluster()
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier)
    assert cluster.get_modifiers_for(int) == OrderedSet([modifier])


def test_add_modifier_two():
    cluster = FullTestCluster()
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier2)
    assert cluster.get_modifiers_for(int) == OrderedSet([modifier, modifier2])


def test_get_random_modifier():
    cluster = FullTestCluster()
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier2)
    assert cluster.get_random_call_for(int) in {modifier, modifier2}


def test_get_random_modifier_none():
    cluster = FullTestCluster()
    with pytest.raises(ConstructionFailedException):
        cluster.get_random_call_for(int)


def test_get_modifier_none_available():
    cluster = FullTestCluster()
    assert cluster.get_modifiers_for(int) == OrderedSet()


def test_get_random_accessible():
    cluster = FullTestCluster()
    assert cluster.get_random_accessible() is None


def test_get_random_accessible_two():
    cluster = FullTestCluster()
    modifier = MagicMock(GenericMethod)
    modifier2 = MagicMock(GenericMethod)
    cluster.add_accessible_object_under_test(modifier)
    cluster.add_accessible_object_under_test(modifier2)
    assert cluster.get_random_accessible() in {modifier, modifier2}


@pytest.mark.parametrize(
    "type_, result",
    [
        pytest.param(None, [None]),
        pytest.param(bool, [bool]),
        pytest.param(Union[int, float], [int, float]),
        pytest.param(Union, [None]),
    ],
)
def test_select_concrete_type_union_unary(type_, result):
    assert FullTestCluster().select_concrete_type(type_) in result


def test_select_concrete_type_any():
    cluster = FullTestCluster()
    cluster._generators[MagicMock] = MagicMock
    assert cluster.select_concrete_type(Any) in list(PRIMITIVES) + list(COLLECTIONS) + [
        MagicMock
    ]


def test_get_all_generatable_types_only_primitive():
    cluster = FullTestCluster()
    assert cluster.get_all_generatable_types() == list(PRIMITIVES) + list(COLLECTIONS)


def test_get_all_generatable_types():
    cluster = FullTestCluster()
    cluster._generators[MagicMock] = MagicMock
    assert cluster.get_all_generatable_types() == [MagicMock] + list(PRIMITIVES) + list(
        COLLECTIONS
    )
