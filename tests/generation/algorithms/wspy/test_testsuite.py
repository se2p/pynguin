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

import pynguin.generation.algorithms.wspy.testsuite as ts
import pynguin.testcase.testcase as tc


def test_test_suite():
    suite = ts.TestSuite()
    assert len(suite.test_cases) == 0


def test_test_suite_size():
    suite = ts.TestSuite()
    assert suite.size() == 0


def test_test_suite_test_cases():
    suite = ts.TestSuite()
    tcs = [MagicMock(tc.TestCase)]
    suite.test_cases = tcs
    assert suite.test_cases == tcs


def test_test_suite_total_size():
    suite = ts.TestSuite()
    test_case = MagicMock(tc.TestCase)
    test_case.size.return_value = 5
    tcs = [test_case, test_case]
    suite.test_cases = tcs
    assert suite.total_length_of_test_cases() == 10


def test_test_suite_clone():
    suite = ts.TestSuite()
    test_case = MagicMock(tc.TestCase)
    test_case.size.return_value = 5
    test_case.clone.return_value = test_case
    tcs = [test_case, test_case]
    suite.test_cases = tcs
    cloned = suite.clone()
    assert suite.test_cases == cloned.test_cases
