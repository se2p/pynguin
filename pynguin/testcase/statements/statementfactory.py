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
"""Provides a factory that creates a statement instance for a callable."""
from inspect import Parameter
from typing import Callable, List, Tuple, Any

import pynguin.testcase.testcase as tc
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.primitivestatements as prim


class StatementFactory:
    """A factory that creates a statement instance for a callable."""

    @classmethod
    def create_statement(
        cls,
        test_case: tc.TestCase,
        callable_: Callable,
        values: List[Tuple[str, Parameter, Any]],
    ) -> stmt.Statement:
        """Creates a statement for a callable.

        :param test_case: The test case for which we generate the statement
        :param callable_: The callable for which we generate the statement
        :param values: The list of parameter values
        :return: A statement representing this method call
        """

    @classmethod
    def create_int_statement(
        cls, test_case: tc.TestCase, value: Tuple[str, Parameter, Any],
    ) -> prim.IntPrimitiveStatement:
        """Creates a statement representing a primitive integer.

        :param test_case: The test case for which we generate the statement
        :param value: The parameter value
        :return: A statement representing the integer
        """
        statement = prim.IntPrimitiveStatement(test_case, value[2])
        return statement

    @classmethod
    def create_float_statement(
        cls, test_case: tc.TestCase, value: Tuple[str, Parameter, Any],
    ) -> prim.FloatPrimitiveStatement:
        """Creates a statement representing a primitive float.

        :param test_case: The test case for which we generate the statement
        :param value: The parameter value
        :return: A statement representing the float
        """
        statement = prim.FloatPrimitiveStatement(test_case, value[2])
        return statement

    @classmethod
    def create_string_statement(
        cls, test_case: tc.TestCase, value: Tuple[str, Parameter, Any],
    ) -> prim.StringPrimitiveStatement:
        """Creates a statement representing a primitive string.

        :param test_case: The test case for which we generate the statement
        :param value: The parameter value
        :return: A statement representing the string
        """
        statement = prim.StringPrimitiveStatement(test_case, value[2])
        return statement

    @classmethod
    def create_bool_statement(
        cls, test_case: tc.TestCase, value: Tuple[str, Parameter, Any],
    ) -> prim.BooleanPrimitiveStatement:
        """Creates a statement representing a primitive bool.

        :param test_case: The test case for which we generate the statement
        :param value: The parameter value
        :return: A statement representing the bool
        """
        statement = prim.BooleanPrimitiveStatement(test_case, value[2])
        return statement
