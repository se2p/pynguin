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
from pynguin.setup.testclustergenerator import TestClusterGenerator
from tests.fixtures.cluster.no_dependencies import Test
from tests.fixtures.cluster.dependency import SomeArgumentType


def test_test_cluster_generator_accessible():
    cluster = TestClusterGenerator(
        ["tests.fixtures.cluster.no_dependencies"]
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 4


def test_test_cluster_generator_generators():
    cluster = TestClusterGenerator(
        ["tests.fixtures.cluster.no_dependencies"]
    ).generate_cluster()
    assert len(cluster.get_generators_for(Test)) == 1
    assert len(cluster.get_generators_for(int)) == 1
    assert len(cluster.get_generators_for(float)) == 1


def test_test_cluster_generator_simple_dependencies():
    cluster = TestClusterGenerator(
        ["tests.fixtures.cluster.simple_dependencies"]
    ).generate_cluster()
    assert len(cluster.get_generators_for(SomeArgumentType)) == 1


def test_test_cluster_generator_simple_dependencies_only_own_classes():
    cluster = TestClusterGenerator(
        ["tests.fixtures.cluster.simple_dependencies"]
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 1
