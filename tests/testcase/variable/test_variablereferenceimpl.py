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

import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereferenceimpl as vri


def test_getters(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    assert ref.variable_type == int
    assert ref.test_case == test_case_mock


def test_setters(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    vt_new = float
    ref.variable_type = vt_new
    assert ref.variable_type == vt_new


def test_clone(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    tc_new = MagicMock(tc.TestCase)
    clone = ref.clone(tc_new)
    assert clone.variable_type == int
    assert clone.test_case == tc_new
