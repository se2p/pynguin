# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest.mock import MagicMock

import pytest

from pynguin.setup.testcluster import TestCluster
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import GenericMethod


def test_add_generator_primitive():
    cluster = TestCluster()
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = int
    cluster.add_generator(generator)
    assert cluster.get_generators_for(int) == set()


def test_add_generator():
    cluster = TestCluster()
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    cluster.add_generator(generator)
    assert cluster.get_generators_for(MagicMock) == {generator}


def test_add_generator_two():
    cluster = TestCluster()
    generator = MagicMock(GenericMethod)
    generator.generated_type.return_value = MagicMock
    cluster.add_generator(generator)
    generator2 = MagicMock(GenericMethod)
    generator2.generated_type.return_value = MagicMock
    cluster.add_generator(generator2)
    assert cluster.get_generators_for(MagicMock) == {generator, generator2}


def test_add_accessible_object_under_test():
    cluster = TestCluster()
    aoc = MagicMock(GenericMethod)
    aoc2 = MagicMock(GenericMethod)
    cluster.add_accessible_object_under_test(aoc)
    cluster.add_accessible_object_under_test(aoc2)
    assert cluster.accessible_objects_under_test == {aoc, aoc2}


def test_add_modifier():
    cluster = TestCluster()
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier)
    assert cluster.get_modifiers_for(int) == {modifier}


def test_add_modifier_two():
    cluster = TestCluster()
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier2)
    assert cluster.get_modifiers_for(int) == {modifier, modifier2}


def test_get_random_modifier():
    cluster = TestCluster()
    modifier = MagicMock(GenericMethod)
    modifier.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier)
    modifier2 = MagicMock(GenericMethod)
    modifier2.generated_type.return_value = MagicMock
    cluster.add_modifier(int, modifier2)
    assert cluster.get_random_call_for(int) in {modifier, modifier2}


def test_get_random_modifier_none():
    cluster = TestCluster()
    with pytest.raises(ConstructionFailedException):
        cluster.get_random_call_for(int)


def test_get_modifier_none_available():
    cluster = TestCluster()
    assert cluster.get_modifiers_for(int) == set()


def test_get_random_accessible():
    cluster = TestCluster()
    assert cluster.get_random_accessible() is None


def test_get_random_accessible_two():
    cluster = TestCluster()
    modifier = MagicMock(GenericMethod)
    modifier2 = MagicMock(GenericMethod)
    cluster.add_accessible_object_under_test(modifier)
    cluster.add_accessible_object_under_test(modifier2)
    assert cluster.get_random_accessible() in {modifier, modifier2}
