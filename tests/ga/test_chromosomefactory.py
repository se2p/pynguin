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

import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasefactory as tcf
import pynguin.configuration as config
import pynguin.testsuite.testsuitechromosome as tsc


def test_get_chromosome():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    factory = cf.TestSuiteChromosomeFactory(test_case_factory)
    config.INSTANCE.min_initial_tests = 5
    config.INSTANCE.max_initial_tests = 5
    chromosome = factory.get_chromosome()
    assert (
        config.INSTANCE.min_initial_tests
        <= test_case_factory.get_test_case.call_count
        <= config.INSTANCE.max_initial_tests
    )
    assert isinstance(chromosome, tsc.TestSuiteChromosome)
