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
"""Provides a factory for test-case generation."""
import logging
import pynguin.configuration as config
import pynguin.testcase.statements.fieldstatement as f_stmt
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.parametrizedstatements as par_stmt
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.exceptions import ConstructionFailedException


class _TestFactory:
    """A factory for test-case generation."""

    _logger = logging.getLogger(__name__)

    def append_statement(
        self, test_case: tc.TestCase, statement: stmt.Statement
    ) -> None:
        """Appends a statement to a test case.

        :param test_case: The test case
        :param statement: The statement to append
        """
        if isinstance(statement, par_stmt.ConstructorStatement):
            self.add_constructor(test_case, statement)
        if isinstance(statement, par_stmt.MethodStatement):
            self.add_method(test_case, statement)
        if isinstance(statement, par_stmt.FunctionStatement):
            self.add_function(test_case, statement)
        if isinstance(statement, f_stmt.FieldStatement):
            self.add_field(test_case, statement)
        if isinstance(statement, prim.PrimitiveStatement):
            self.add_primitive(test_case, statement)

    def add_constructor(
        self,
        test_case: tc.TestCase,
        constructor: par_stmt.ConstructorStatement,
        position: int = -1,
        recursion_depth: int = 0,
    ) -> vr.VariableReference:
        """Adds a constructor statement to a test case at a given position.

        If the position is not given, the constructor will be appended on the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        :param test_case: The test case
        :param constructor: The constructor to add to the test case
        :param position: The position where to put the statement in the test case,
        defaults to the end of the test case
        :param recursion_depth: A recursion limit for the search of parameter values
        :return: A variable reference to the constructor
        """
        self._logger.debug("Adding constructor %s", constructor)
        if recursion_depth > config.INSTANCE.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        # TODO(sl) implement me
        statement = constructor.clone(test_case)
        return test_case.add_statement(statement, position)

    def add_method(
        self,
        test_case: tc.TestCase,
        method: par_stmt.MethodStatement,
        position: int = -1,
        recursion_depth: int = 0,
    ) -> vr.VariableReference:
        """Adds a method call to a test case at a given position.

        If the position is not given, the method call will be appended to the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        :param test_case: The test case
        :param method: The method call to add to the test case
        :param position: The position where to put the statement in the test case,
        defaults to the end of the test case
        :param recursion_depth: A recursion limit for the search of parameter values
        :return: A variable reference to the method call's result
        """
        self._logger.debug("Adding method %s", method)
        if recursion_depth > config.INSTANCE.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        # TODO(sl) implement me
        statement = method.clone(test_case)
        return test_case.add_statement(statement, position)

    def add_field(
        self,
        test_case: tc.TestCase,
        field: f_stmt.FieldStatement,
        position: int = -1,
        recursion_depth: int = 0,
    ) -> vr.VariableReference:
        """Adds a field access to a test case at a given position.

        If the position is not given, the field access will be appended to the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        :param test_case: The test case
        :param field: The field access to add to the test case
        :param position: The position where to put the statement in the test case,
        defaults to the end of the test case
        :param recursion_depth: A recursion limit for the search of values
        :return: A variable reference to the field value
        """
        self._logger.debug("Adding field %s", field)
        if recursion_depth > config.INSTANCE.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        # TODO(sl) implement me
        statement = field.clone(test_case)
        return test_case.add_statement(statement, position)

    def add_function(
        self,
        test_case: tc.TestCase,
        function: par_stmt.FunctionStatement,
        position: int = -1,
        recursion_depth: int = 0,
    ) -> vr.VariableReference:
        """Adds a function call to a test case at a given position.

        If the position is not given, the function call will be appended to the end
        of the test case.  A given recursion depth controls how far the factory
        searches for suitable parameter values.

        :param test_case: The test case
        :param function: The function call to add to the test case
        :param position: the position where to put the statement in the test case,
        defaults to the end of the test case
        :param recursion_depth: A recursion limit for the search of parameter values
        :return: A variable reference to the function call's result
        """
        self._logger.debug("Adding function %s", function)
        if recursion_depth > config.INSTANCE.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        # TODO(sl) implement me
        statement = function.clone(test_case)
        return test_case.add_statement(statement, position)

    def add_primitive(
        self,
        test_case: tc.TestCase,
        primitive: prim.PrimitiveStatement,
        position: int = -1,
    ) -> vr.VariableReference:
        """Adds a primitive statement to the given test case at the given position.

        If no position is given the statement will be put at the end of the test case.

        :param test_case: The test case to add the statement to
        :param primitive: The primitive statement itself
        :param position: The position where to put the statement, if none is given,
        the statement will be appended to the end of the test case
        :return: A reference to the statement
        """
        self._logger.debug("Adding primitive %s", primitive)
        statement = primitive.clone(test_case)
        return test_case.add_statement(statement, position)


# pylint: disable=invalid-name
_inst = _TestFactory()
append_statement = _inst.append_statement
add_constructor = _inst.add_constructor
add_method = _inst.add_method
add_field = _inst.add_field
add_function = _inst.add_function
add_primitive = _inst.add_primitive
