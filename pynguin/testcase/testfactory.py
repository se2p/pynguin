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
from typing import List, Type, Optional, Dict

import pynguin.configuration as config
import pynguin.testcase.statements.fieldstatement as f_stmt
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.parametrizedstatements as par_stmt
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.utils import randomness
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
            # self.add_constructor(test_case, statement)
            pass
        if isinstance(statement, par_stmt.MethodStatement):
            # self.add_method(test_case, statement)
            pass
        if isinstance(statement, par_stmt.FunctionStatement):
            # self.add_function(test_case, statement)
            pass
        if isinstance(statement, f_stmt.FieldStatement):
            self.add_field(test_case, statement)
        if isinstance(statement, prim.PrimitiveStatement):
            self.add_primitive(test_case, statement)

    def add_constructor(
        self,
        test_case: tc.TestCase,
        constructor: gao.GenericConstructor,
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

        if position < 0:
            position = test_case.size()

        signature = constructor.inferred_signature
        length = test_case.size()
        try:
            parameters: List[vr.VariableReference] = self.satisfy_parameters(
                test_case=test_case,
                parameter_types=signature.parameters,
                position=position,
                recursion_depth=recursion_depth + 1,
            )
            new_length = test_case.size()
            position = position + new_length - length

            statement = par_stmt.ConstructorStatement(
                test_case=test_case, constructor=constructor, args=parameters,
            )
            return test_case.add_statement(statement, position)
        except BaseException as exception:
            raise ConstructionFailedException(
                f"Failed to add constructor for {constructor} " f"due to {exception}."
            )

    def add_method(
        self,
        test_case: tc.TestCase,
        method: gao.GenericMethod,
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

        if position < 0:
            position = test_case.size()

        signature = method.inferred_signature
        length = test_case.size()
        callee = self._create_or_reuse_variable(
            test_case, method.owner, position, recursion_depth, allow_none=True
        )
        assert callee
        parameters: List[vr.VariableReference] = self.satisfy_parameters(
            test_case=test_case,
            parameter_types=signature.parameters,
            position=position,
            recursion_depth=recursion_depth + 1,
        )

        new_length = test_case.size()
        position = position + new_length - length

        statement = par_stmt.MethodStatement(
            test_case=test_case, method=method, callee=callee, args=parameters,
        )
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

        if position < 0:
            position = test_case.size()

        # TODO(sl) implement me
        statement = field.clone(test_case)
        return test_case.add_statement(statement, position)

    def add_function(
        self,
        test_case: tc.TestCase,
        function: gao.GenericFunction,
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

        if position < 0:
            position = test_case.size()

        signature = function.inferred_signature
        length = test_case.size()
        parameters: List[vr.VariableReference] = self.satisfy_parameters(
            test_case=test_case,
            parameter_types=signature.parameters,
            position=position,
            recursion_depth=recursion_depth + 1,
        )
        new_length = test_case.size()
        position = position + new_length - length

        statement = par_stmt.FunctionStatement(
            test_case=test_case, function=function, args=parameters,
        )
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
        if position < 0:
            position = test_case.size()

        self._logger.debug("Adding primitive %s", primitive)
        statement = primitive.clone(test_case)
        return test_case.add_statement(statement, position)

    # pylint: disable=too-many-arguments, assignment-from-none
    def satisfy_parameters(
        self,
        test_case: tc.TestCase,
        parameter_types: Dict[str, Optional[Type]],
        callee: Optional[vr.VariableReference] = None,
        position: int = -1,
        recursion_depth: int = 0,
        allow_none: bool = True,
        can_reuse_existing_variables: bool = True,
    ) -> List[vr.VariableReference]:
        """Satisfy a list of parameters by reusing or creating variables.

        :param test_case: The test case
        :param parameter_types: The list of parameter types
        :param callee: The callee of the method
        :param position: The current position in the test case
        :param recursion_depth: The recursion depth
        :param allow_none: Whether or not a variable can be a None value
        :param can_reuse_existing_variables: Whether or not existing variables shall
        be reused.
        :return: A list of variable references for the parameters
        """
        if position < 0:
            position = test_case.size()

        parameters: List[vr.VariableReference] = []
        self._logger.debug(
            "Trying to satisfy %d parameters at position %d",
            len(parameter_types),
            position,
        )

        for _, parameter_type in parameter_types.items():
            self._logger.debug("Current parameter type: %s", parameter_type)

            previous_length = test_case.size()

            if can_reuse_existing_variables:
                self._logger.debug("Ca re-use variables")
                var = self._create_or_reuse_variable(
                    test_case,
                    parameter_type,
                    position,
                    recursion_depth,
                    allow_none,
                    callee,
                )
            else:
                self._logger.debug(
                    "Cannot re-use variables: attempt to creating new one"
                )
                var = self._create_variable(
                    test_case,
                    parameter_type,
                    position,
                    recursion_depth,
                    allow_none,
                    callee,
                )
            if not var:
                raise ConstructionFailedException(
                    f"Failed to create variable for type {parameter_type} "
                    f"at position {position}",
                )

            parameters.append(var)
            current_length = test_case.size()
            position += current_length - previous_length

        self._logger.debug("Satisfied %d parameters", len(parameters))
        return parameters

    # pylint: disable=too-many-arguments, unused-argument, no-self-use
    def _create_or_reuse_variable(
        self,
        test_case: tc.TestCase,
        parameter_type: Optional[Type],
        position: int,
        recursion_depth: int,
        allow_none: bool,
        exclude: Optional[vr.VariableReference] = None,
    ) -> Optional[vr.VariableReference]:
        reuse = randomness.next_float()
        objects = test_case.get_objects(parameter_type, position)
        is_primitive = self._is_primitive(parameter_type)
        if (
            is_primitive
            and objects
            and reuse <= config.INSTANCE.primitive_reuse_probability
        ):
            self._logger.debug("Looking for existing object of type %s", parameter_type)
            reference = randomness.choice(objects)
            return reference
        if (
            not is_primitive
            and objects
            and reuse <= config.INSTANCE.object_reuse_probability
        ):
            self._logger.debug(
                "Choosing from %d existing objects %s", len(objects), objects
            )
            reference = randomness.choice(objects)
            return reference

        # if chosen to not re-use existing variable, try to create a new one
        created = self._create_variable(
            test_case, parameter_type, position, recursion_depth, allow_none, exclude
        )
        if created:
            return created

        # could not create, so go back in trying to re-use an existing variable
        if not objects:
            if allow_none:
                return self._create_none(
                    test_case, parameter_type, position, recursion_depth
                )
            raise ConstructionFailedException(f"No objects for type {parameter_type}")

        self._logger.debug(
            "Choosing from %d existing objects: %s", len(objects), objects
        )
        reference = randomness.choice(objects)
        self._logger.debug(
            "Use existing object of type %s: %s", parameter_type, reference
        )
        return reference

    # pylint: disable=too-many-arguments
    def _create_variable(
        self,
        test_case: tc.TestCase,
        parameter_type: Optional[Type],
        position: int,
        recursion_depth: int,
        allow_none: bool,
        exclude: Optional[vr.VariableReference] = None,
    ) -> Optional[vr.VariableReference]:
        return self._attempt_generation(
            test_case, parameter_type, position, recursion_depth, allow_none, exclude
        )

    # pylint: disable=too-many-arguments
    def _attempt_generation(
        self,
        test_case: tc.TestCase,
        parameter_type: Optional[Type],
        position: int,
        recursion_depth: int,
        allow_none: bool,
        exclude: Optional[vr.VariableReference] = None,
    ) -> Optional[vr.VariableReference]:
        if not parameter_type:
            return None

        if self._is_primitive(parameter_type):
            return self._create_primitive(
                test_case, parameter_type, position, recursion_depth,
            )
        if (
            allow_none
            and randomness.next_float() <= config.Configuration.none_probability
        ):
            return self._create_none(
                test_case, parameter_type, position, recursion_depth
            )
        return None

    @staticmethod
    def _create_none(
        test_case: tc.TestCase,
        parameter_type: Optional[Type],
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        statement = prim.NoneStatement(test_case, parameter_type)
        test_case.add_statement(statement, position)
        ret = test_case.get_statement(position).return_value
        ret.distance = recursion_depth
        return ret

    @staticmethod
    def _create_primitive(
        test_case: tc.TestCase,
        parameter_type: Type,
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        if parameter_type == int:
            statement: prim.PrimitiveStatement = prim.IntPrimitiveStatement(test_case)
        elif parameter_type == float:
            statement = prim.FloatPrimitiveStatement(test_case)
        elif parameter_type == bool:
            statement = prim.BooleanPrimitiveStatement(test_case)
        else:
            statement = prim.StringPrimitiveStatement(test_case)
        ret = test_case.add_statement(statement, position)
        ret.distance = recursion_depth
        return ret

    @staticmethod
    def _is_primitive(type_: Optional[Type]) -> bool:
        return type_ in (int, float, bool, str)


# pylint: disable=invalid-name
_inst = _TestFactory()
append_statement = _inst.append_statement
add_constructor = _inst.add_constructor
add_method = _inst.add_method
add_field = _inst.add_field
add_function = _inst.add_function
add_primitive = _inst.add_primitive
