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
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.generation.algorithms.randoopy.monkeytypehandlermixin import (
    MonkeyTypeHandlerMixin,
)
from pynguin.setup.testclustergenerator import TestClusterGenerator


@pytest.fixture
def mixin():
    return MonkeyTypeHandlerMixin()


def test_execute_test_case_monkey_type(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    mixin.execute_test_case_monkey_type(short_test_case, test_cluster)


def test_execute_test_suite_monkey_type(mixin, short_test_case):
    module_name = "tests.fixtures.accessibles.accessible"
    config.INSTANCE.module_name = module_name
    test_cluster = TestClusterGenerator(module_name).generate_cluster()
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test(short_test_case)
    mixin.execute_test_suite_monkey_type(test_suite, test_cluster)
