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
import pytest

import pynguin.configuration as config
from pynguin.generation.algorithms.randoopy.mypytypehandlermixin import (
    MyPyTypeHandlerMixin,
)
from pynguin.setup.testclustergenerator import TestClusterGenerator


@pytest.fixture
def mixin():
    return MyPyTypeHandlerMixin()


def test_retrieve_test_case_type_info_mypy(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    mixin.retrieve_test_case_type_info_mypy(short_test_case, test_cluster)


def test_retrieve_test_suite_type_info_mypy(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    mixin.retrieve_test_suite_type_info_mypy([short_test_case], test_cluster)
