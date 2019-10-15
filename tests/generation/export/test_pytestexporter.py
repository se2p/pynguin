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
import ast
from unittest.mock import MagicMock

import pytest

from pynguin.generation.export.pytestexporter import _PyTestExportStatementVisitor
from pynguin.utils.statements import Expression, Name, Attribute, Call, Assignment


@pytest.fixture
def visitor():
    return _PyTestExportStatementVisitor()


def test_visit_expression(visitor):
    with pytest.raises(Exception) as exception:
        visitor.visit_expression(MagicMock(Expression))
    assert "Not implemented handling for expression" in exception.value.args[0]


def test_visit_name(visitor):
    name = Name(identifier="foo")
    result = visitor.visit_name(name)
    assert isinstance(result, ast.Name)
    assert result.id == "foo"


def test_visit_attribute(visitor):
    name = Name(identifier="foo")
    attribute = Attribute(owner=name, attribute_name="bar")
    result = visitor.visit_attribute(attribute)
    assert isinstance(result, ast.Attribute)
    assert result.value.id == "foo"
    assert result.attr == "bar"


def test_visit_call(visitor):
    call = Call(function=Name(identifier="foo"), arguments=[])
    result = visitor.visit_call(call)
    assert isinstance(result, ast.Expr)


def test_visit_call_attribute(visitor):
    call = Call(
        function=Attribute(owner=Name("foo"), attribute_name="bar"), arguments=[]
    )
    result = visitor.visit_call(call)
    assert isinstance(result, ast.Expr)


def test_visit_call_exception(visitor):
    call = Call(function="", arguments=[])
    with pytest.raises(Exception) as exception:
        visitor.visit_call(call)
    assert "Unknown function type" in exception.value.args[0]


def test_visit_assignment(visitor):
    lhs = Name(identifier="foo")
    rhs = Call(function=Name("bar"), arguments=[])
    assignment = Assignment(lhs=lhs, rhs=rhs)
    result = visitor.visit_assignment(assignment)
    assert isinstance(result, ast.Assign)


def test__visit_function_arguments(visitor):
    arguments = [Name(identifier="foo"), True, "bar", 42]
    result = visitor._visit_function_arguments(arguments)
    assert isinstance(result[0], ast.Name)
    assert isinstance(result[1], ast.NameConstant)
    assert isinstance(result[2], ast.Str)
    assert isinstance(result[3], ast.Num)
    assert len(result) == 4


def test__visit_function_arguments_with_exception(visitor):
    arguments = [Call(function=Name(identifier="foo"), arguments=[])]
    with pytest.raises(Exception) as exception:
        visitor._visit_function_arguments(arguments)
    assert "Missing case of argument" in exception.value.args[0]
