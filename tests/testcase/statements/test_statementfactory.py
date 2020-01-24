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


def test_create_float_statement(test_case_mock):
    name = "foo"
    parameter = MagicMock(Parameter)
    value = (name, parameter, 42.23)
    result = sf.StatementFactory.create_float_statement(test_case_mock, value)
    assert isinstance(result, prim.FloatPrimitiveStatement)
    assert result.test_case == test_case_mock
    assert result.value == 42.23
    assert result.return_value.variable_type == float


def test_create_string_statement(test_case_mock):
    name = "foo"
    parameter = MagicMock(Parameter)
    value = (name, parameter, "bar")
    result = sf.StatementFactory.create_string_statement(test_case_mock, value)
    assert isinstance(result, prim.StringPrimitiveStatement)
    assert result.test_case == test_case_mock
    assert result.value == "bar"
    assert result.return_value.variable_type == str


def test_create_bool_statement(test_case_mock):
    name = "foo"
    parameter = MagicMock(Parameter)
    value = (name, parameter, True)
    result = sf.StatementFactory.create_bool_statement(test_case_mock, value)
    assert isinstance(result, prim.BooleanPrimitiveStatement)
    assert result.test_case == test_case_mock
    assert result.value
    assert result.return_value.variable_type == bool


def test_create_statements(provide_callables_from_fixtures_modules, test_case_mock):
    callable_ = provide_callables_from_fixtures_modules["triangle"]
    values = [
        ("x", Parameter("x", Parameter.POSITIONAL_OR_KEYWORD, annotation=int), 42),
        ("y", Parameter("y", Parameter.POSITIONAL_OR_KEYWORD, annotation=int), 42),
        ("z", Parameter("z", Parameter.POSITIONAL_OR_KEYWORD, annotation=int), 42),
    ]
    statements = sf.StatementFactory.create_statements(
        test_case_mock, callable_, values
    )
    # a = 0
    assert statements
