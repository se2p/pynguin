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
from pynguin.setup.testcluster import TestCluster
from tests.fixtures.cluster.no_dependencies import Test


def test_simple_cluster_accessible():
    cluster = TestCluster(["tests.fixtures.cluster.no_dependencies"])
    assert len(cluster.accessible_objects_under_test) == 3


def test_simple_cluster_generators():
    cluster = TestCluster(["tests.fixtures.cluster.no_dependencies"])
    assert len(cluster.get_generators_for(Test)) == 1
    # TODO(fk) This should also be 3, because the method and the function also generate float/int.
    # But they are not yet added as generators.
