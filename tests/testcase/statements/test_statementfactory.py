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
from inspect import Parameter
from unittest.mock import MagicMock

import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statementfactory as sf


def test_create_int_statement(test_case_mock):
    name = "foo"
    parameter = MagicMock(Parameter)
    value = (name, parameter, 42)
    result = sf.StatementFactory.create_int_statement(test_case_mock, value)
    assert isinstance(result, prim.IntPrimitiveStatement)
    assert result.test_case == test_case_mock
    assert result.value == 42
    assert result.return_value.variable_type == int
