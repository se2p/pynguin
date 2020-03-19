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

import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.testfactory as tf
import pynguin.configuration as config


def test_get_test_case_max_attempts():
    test_factory = MagicMock(tf.TestFactory)
    test_case_factory = tcf.RandomLengthTestCaseFactory(test_factory)
    test_case_factory.get_test_case()
    assert (
        test_factory.insert_random_statement.call_count == config.INSTANCE.max_attempts
    )


def test_get_test_case_success():
    test_factory = MagicMock(tf.TestFactory)
    test_factory.insert_random_statement.side_effect = lambda test_case, pos: test_case.add_statement(
        MagicMock(), 0
    )
    test_case_factory = tcf.RandomLengthTestCaseFactory(test_factory)
    test_case_factory.get_test_case()
    assert (
        1
        <= test_factory.insert_random_statement.call_count
        <= config.INSTANCE.chromosome_length
    )
