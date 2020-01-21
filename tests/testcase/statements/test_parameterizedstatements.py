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

import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.variable.variablereferenceimpl as vri


def test_constructor_statement(
    test_case_mock, variable_reference_mock, inferred_method_type_mock
):
    statement = ps.ConstructorStatement(
        test_case_mock, inferred_method_type_mock, str, [variable_reference_mock]
    )
    assert statement.parameters == [variable_reference_mock]


def test_constructor_statement_parameters(
    test_case_mock, variable_reference_mock, inferred_method_type_mock
):
    statement = ps.ConstructorStatement(
        test_case_mock, inferred_method_type_mock, str, [variable_reference_mock]
    )
    references = [
        MagicMock(vri.VariableReferenceImpl),
        MagicMock(vri.VariableReferenceImpl),
    ]
    statement.parameters = references
    assert statement.parameters == references


def test_method_statement(
    test_case_mock, variable_reference_mock, inferred_method_type_mock
):
    references = [variable_reference_mock]

    statement = ps.MethodStatement(
        test_case_mock, inferred_method_type_mock, variable_reference_mock, references
    )
    assert statement.parameters == references
