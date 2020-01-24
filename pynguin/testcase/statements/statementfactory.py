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
from typing import Callable, List, Tuple, Any, Type, Optional

import pynguin.testcase.statements.parametrizedstatements as pars
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.typeinference.strategy import InferredMethodType


class StatementFactory:
    """A factory that creates a statement instance for a callable."""

    @classmethod
    def create_statements(
        cls,
        test_case: tc.TestCase,
        callable_: Callable,
        values: List[Tuple[str, Type, Any]],
        method_type: InferredMethodType,
    ) -> List[stmt.Statement]:
        """Creates a list of statements for a callable.

        :param test_case: The test case for which we generate the statement
        :param callable_: The callable for which we generate the statement
        :param values: The list of parameter values
        :param method_type: The inferred type information for this method
        :return: A list of statements representing this method call
        """
        statements: List[stmt.Statement] = []
        for value in values:
            # TODO(sl) build a mechanism that allows this depending on the type
            statements.append(cls.create_int_statement(test_case, value))
        statements.append(
            cls.create_function_statement(
                test_case,
                callable_,
                [s.return_value for s in statements],
                method_type.return_type,
            )
        )
        return statements

    @classmethod
    def create_function_statement(
        cls,
        test_case: tc.TestCase,
        callable_: Callable,
        values: List[vr.VariableReference],
        return_type: Optional[Type],
    ) -> pars.FunctionStatement:
        """Creates a function call statement.

        :param test_case: The test case for which we generate the statement
        :param callable_: The callable for which we generate the statement
        :param values: The list of parameter values
        :param return_type: The optional return type of the function
        :return: A statement representing the function call
        """
        # TODO(sl) extend this to use the InferredMethodType for types somehow
        statement = pars.FunctionStatement(
            test_case, callable_.__name__, return_type, args=values
        )
        return statement

    @classmethod
    def create_int_statement(
        cls, test_case: tc.TestCase, value: Tuple[str, Type, Any],
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
        cls, test_case: tc.TestCase, value: Tuple[str, Type, Any],
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
        cls, test_case: tc.TestCase, value: Tuple[str, Type, Any],
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
        cls, test_case: tc.TestCase, value: Tuple[str, Type, Any],
    ) -> prim.BooleanPrimitiveStatement:
        """Creates a statement representing a primitive bool.

        :param test_case: The test case for which we generate the statement
        :param value: The parameter value
        :return: A statement representing the bool
        """
        statement = prim.BooleanPrimitiveStatement(test_case, value[2])
        return statement
