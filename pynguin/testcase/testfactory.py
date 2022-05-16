#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factory for test-case generation."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from ordered_set import OrderedSet
from typing_inspect import get_args, get_origin

import pynguin.configuration as config
import pynguin.testcase.statement as stmt
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.constants import ConstantProvider, EmptyConstantProvider
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.type_utils import (
    is_assignable_to,
    is_collection_type,
    is_optional_parameter,
    is_primitive_type,
    is_type_unknown,
)

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.variablereference as vr
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.analyses.types import InferredSignature


# TODO(fk) find better name for this?
# TODO split this monster!
class TestFactory:
    """A factory for test-case generation.
    This factory does not generate test cases but provides all necessary means to
    construct and modify test cases."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        test_cluster: ModuleTestCluster,
        constant_provider: ConstantProvider | None = None,
    ):
        self._test_cluster = test_cluster
        if constant_provider is None:
            constant_provider = EmptyConstantProvider()
        self._constant_provider: ConstantProvider = constant_provider

    def append_statement(
        self,
        test_case: tc.TestCase,
        statement: stmt.Statement,
        position: int = -1,
        allow_none: bool = True,
    ) -> None:
        """Appends a statement to a test case.

        Args:
            test_case: The test case
            statement: The statement to append
            position: The position to insert the statement, default is at the end
                of the test case
            allow_none: Whether or not parameter variables can hold None values

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        new_position = test_case.size() if position == -1 else position
        if isinstance(statement, stmt.ConstructorStatement):
            self.add_constructor(
                test_case,
                statement.accessible_object(),
                position=new_position,
                allow_none=allow_none,
            )
        elif isinstance(statement, stmt.MethodStatement):
            self.add_method(
                test_case,
                statement.accessible_object(),
                position=new_position,
                allow_none=allow_none,
            )
        elif isinstance(statement, stmt.FunctionStatement):
            self.add_function(
                test_case,
                statement.accessible_object(),
                position=new_position,
                allow_none=allow_none,
            )
        elif isinstance(statement, stmt.FieldStatement):
            self.add_field(
                test_case,
                statement.field,
                position=new_position,
            )
        elif isinstance(statement, stmt.PrimitiveStatement):
            self.add_primitive(test_case, statement, position=new_position)
        else:
            raise ConstructionFailedException(f"Unknown statement type: {statement}")

    # pylint: disable=too-many-arguments
    def append_generic_accessible(
        self,
        test_case: tc.TestCase,
        accessible: gao.GenericAccessibleObject,
        position: int = -1,
        recursion_depth: int = 0,
        allow_none: bool = True,
    ) -> vr.VariableReference | None:
        """Appends a generic accessible object to a test case.

        Args:
            test_case: The test case
            accessible: The accessible to append
            position: The position to insert the statement, default is at the end
                of the test case
            recursion_depth: The recursion depth for search
            allow_none: Whether or not parameter variables can hold None values

        Returns:
            An optional variable reference to the added statement

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        new_position = test_case.size() if position == -1 else position
        if isinstance(accessible, gao.GenericConstructor):
            return self.add_constructor(
                test_case,
                accessible,
                position=new_position,
                allow_none=allow_none,
                recursion_depth=recursion_depth,
            )
        if isinstance(accessible, gao.GenericMethod):
            return self.add_method(
                test_case,
                accessible,
                position=new_position,
                allow_none=allow_none,
                recursion_depth=recursion_depth,
            )
        if isinstance(accessible, gao.GenericFunction):
            return self.add_function(
                test_case,
                accessible,
                position=new_position,
                allow_none=allow_none,
                recursion_depth=recursion_depth,
            )
        if isinstance(accessible, gao.GenericField):
            return self.add_field(
                test_case,
                accessible,
                position=new_position,
                recursion_depth=recursion_depth,
            )
        if isinstance(accessible, gao.GenericEnum):
            return self.add_enum(
                test_case,
                accessible,
                position=new_position,
                recursion_depth=recursion_depth,
            )
        raise ConstructionFailedException(f"Unknown accessible type: {accessible}")

    # pylint: disable=too-many-arguments
    def add_constructor(
        self,
        test_case: tc.TestCase,
        constructor: gao.GenericConstructor,
        position: int = -1,
        recursion_depth: int = 0,
        allow_none: bool = True,
    ) -> vr.VariableReference:
        """Adds a constructor statement to a test case at a given position.

        If the position is not given, the constructor will be appended on the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        Args:
            test_case: The test case
            constructor: The constructor to add to the test case
            position: The position where to put the statement in the test case,
                defaults to the end of the test case
            recursion_depth: A recursion limit for the search of parameter values
            allow_none: Whether or not a variable can be an None value

        Returns:
            A variable reference to the constructor

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        self._logger.debug("Adding constructor %s", constructor)
        if recursion_depth > config.configuration.test_creation.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        if position < 0:
            position = test_case.size()

        signature = constructor.inferred_signature
        length = test_case.size()
        try:
            parameters: dict[str, vr.VariableReference] = self.satisfy_parameters(
                test_case=test_case,
                signature=signature,
                position=position,
                recursion_depth=recursion_depth + 1,
                allow_none=allow_none,
            )
            new_length = test_case.size()
            position = position + new_length - length

            statement = stmt.ConstructorStatement(
                test_case=test_case,
                generic_callable=constructor,
                args=parameters,
            )
            return test_case.add_variable_creating_statement(statement, position)
        except BaseException as exception:
            raise ConstructionFailedException(
                f"Failed to add constructor for {constructor}"
            ) from exception

    # pylint: disable=too-many-arguments
    def add_method(
        self,
        test_case: tc.TestCase,
        method: gao.GenericMethod,
        position: int = -1,
        recursion_depth: int = 0,
        allow_none: bool = True,
        callee: vr.VariableReference | None = None,
    ) -> vr.VariableReference:
        """Adds a method call to a test case at a given position.

        If the position is not given, the method call will be appended to the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        Args:
            test_case: The test case
            method: The method call to add to the test case
            position: The position where to put the statement in the test case,
                defaults to the end of the test case
            recursion_depth: A recursion limit for the search of parameter values
            allow_none: Whether or not a variable can hold a None value
            callee: The callee, if it is already known.

        Returns:
            A variable reference to the method call's result

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        self._logger.debug("Adding method %s", method)
        if recursion_depth > config.configuration.test_creation.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        if position < 0:
            position = test_case.size()

        signature = method.inferred_signature
        length = test_case.size()
        if callee is None:
            callee = self._create_or_reuse_variable(
                test_case, method.owner, position, recursion_depth, allow_none=False
            )
        assert callee, "The callee must not be None"
        parameters: dict[str, vr.VariableReference] = self.satisfy_parameters(
            test_case=test_case,
            signature=signature,
            position=position,
            recursion_depth=recursion_depth + 1,
            allow_none=allow_none,
        )

        new_length = test_case.size()
        position = position + new_length - length

        statement = stmt.MethodStatement(
            test_case=test_case,
            generic_callable=method,
            callee=callee,
            args=parameters,
        )
        return test_case.add_variable_creating_statement(statement, position)

    def add_field(
        self,
        test_case: tc.TestCase,
        field: gao.GenericField,
        position: int = -1,
        recursion_depth: int = 0,
        callee: vr.VariableReference | None = None,
    ) -> vr.VariableReference:
        """Adds a field access to a test case at a given position.

        If the position is not given, the field access will be appended to the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        Args:
            test_case: The test case
            field: The field access to add to the test case
            position: The position where to put the statement in the test case,
                defaults to the end of the test case
            recursion_depth: A recursion limit for the search of values
            callee: The callee, if it is already known.

        Returns:
            A variable reference to the field value

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        self._logger.debug("Adding field %s", field)
        if recursion_depth > config.configuration.test_creation.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        if position < 0:
            position = test_case.size()

        length = test_case.size()
        if callee is None:
            callee = self._create_or_reuse_variable(
                test_case, field.owner, position, recursion_depth, allow_none=False
            )
        assert callee, "The callee must not be None"
        position = position + test_case.size() - length
        statement = stmt.FieldStatement(test_case, field, callee)
        return test_case.add_variable_creating_statement(statement, position)

    def add_enum(
        self,
        test_case: tc.TestCase,
        enum_: gao.GenericEnum,
        position: int = -1,
        recursion_depth: int = 0,
    ) -> vr.VariableReference:
        """Adds a primitive based on an enum value at a given position.

        If the position is not given, the enum access will be appended to the end of
        the test case.  A given recursion depth controls how far the factory searches
        for suitable parameter values.

        Args:
            test_case: The test case
            enum_: The enum to add to the test case
            position: The position where to put the statement in the test case,
                defaults to the end of the test case
            recursion_depth: A recursion limit for the search of values

        Returns:
            A variable reference to the enum value

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        self._logger.debug("Adding enum %s", enum_)
        if recursion_depth > config.configuration.test_creation.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        if position < 0:
            position = test_case.size()

        statement = stmt.EnumPrimitiveStatement(test_case, enum_)
        return test_case.add_variable_creating_statement(statement, position)

    # pylint: disable=too-many-arguments
    def add_function(
        self,
        test_case: tc.TestCase,
        function: gao.GenericFunction,
        position: int = -1,
        recursion_depth: int = 0,
        allow_none: bool = True,
    ) -> vr.VariableReference:
        """Adds a function call to a test case at a given position.

        If the position is not given, the function call will be appended to the end
        of the test case.  A given recursion depth controls how far the factory
        searches for suitable parameter values.

        Args:
            test_case: The test case
            function: The function call to add to the test case
            position: the position where to put the statement in the test case,
                defaults to the end of the test case
            recursion_depth: A recursion limit for the search of parameter values
            allow_none: Whether or not a variable can hold a None value

        Returns:
            A variable reference to the function call's result

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        self._logger.debug("Adding function %s", function)
        if recursion_depth > config.configuration.test_creation.max_recursion:
            self._logger.debug("Max recursion depth reached")
            raise ConstructionFailedException("Max recursion depth reached")

        if position < 0:
            position = test_case.size()

        signature = function.inferred_signature
        length = test_case.size()
        parameters: dict[str, vr.VariableReference] = self.satisfy_parameters(
            test_case=test_case,
            signature=signature,
            position=position,
            recursion_depth=recursion_depth + 1,
            allow_none=allow_none,
        )
        new_length = test_case.size()
        position = position + new_length - length

        statement = stmt.FunctionStatement(
            test_case=test_case,
            generic_callable=function,
            args=parameters,
        )
        return test_case.add_variable_creating_statement(statement, position)

    def add_primitive(
        self,
        test_case: tc.TestCase,
        primitive: stmt.PrimitiveStatement,
        position: int = -1,
    ) -> vr.VariableReference:
        """Adds a primitive statement to the given test case at the given position.

        If no position is given the statement will be put at the end of the test case.

        Args:
            test_case: The test case to add the statement to
            primitive: The primitive statement itself
            position: The position where to put the statement, if none is given,
                the statement will be appended to the end of the test case

        Returns:
            A reference to the statement
        """
        if position < 0:
            position = test_case.size()

        self._logger.debug("Adding primitive %s", primitive)
        # TODO(fk) fix this ugly cast.
        statement = cast(stmt.PrimitiveStatement, primitive.clone(test_case, {}))
        return test_case.add_variable_creating_statement(statement, position)

    def insert_random_statement(
        self, test_case: tc.TestCase, last_position: int
    ) -> int:
        """Insert a random statement up to the given position.

        If the insertion was successful, the position at which the statement was
        inserted is returned, otherwise -1.

        Args:
            test_case: The test case to add the statement to
            last_position: The last position before that the statement is inserted

        Returns:
            The index the statement was inserted to, otherwise -1
        """
        old_size = test_case.size()
        rand = randomness.next_float()

        position = randomness.next_int(0, last_position + 1)
        if rand <= config.configuration.test_creation.insertion_uut:
            success = self.insert_random_call(test_case, position)
        else:
            success = self.insert_random_call_on_object(test_case, position)

        if test_case.size() - old_size > 1:
            position += test_case.size() - old_size - 1
        if success:
            return position
        return -1

    def insert_random_call_on_object(
        self, test_case: tc.TestCase, position: int
    ) -> bool:
        """Insert a random call on an object that already exists within the test case.

        Args:
            test_case: The test case to add the call to
            position: The last position before that the call is inserted

        Returns:
            Whether or not the insertion was successful
        """
        variable = self._select_random_variable_for_call(test_case, position)
        success = False
        if variable is not None:
            success = self.insert_random_call_on_object_at(
                test_case, variable, position
            )

        if not success and self._test_cluster.num_accessible_objects_under_test() > 0:
            success = self.insert_random_call(test_case, position)
        return success

    def insert_random_call_on_object_at(
        self, test_case: tc.TestCase, variable: vr.VariableReference, position: int
    ) -> bool:
        """Add a random call on the passed variable.

        Args:
            test_case: The test case to add the call to
            variable: The object the method is called from
            position: The last position before that the call is inserted

        Returns:
            Whether or not the insertion was successful
        """
        assert variable.type, "Cannot insert random call on variable of unknown type."
        try:
            accessible = self._test_cluster.get_random_call_for(variable.type)
            return self.add_call_for(test_case, variable, accessible, position)
        except ConstructionFailedException:
            pass
        return False

    def add_call_for(
        self,
        test_case: tc.TestCase,
        callee: vr.VariableReference,
        accessible: gao.GenericAccessibleObject,
        position: int,
    ) -> bool:
        """Add a call for the given accessible object.

        Args:
            test_case: The test case to add the call to
            callee: The callee
            accessible: The accessible object
            position: The last position

        Returns:
            Whether or not the insertion was successful

        Raises:
            RuntimeError: in case of an unknown accessible
        """
        previous_length = test_case.size()
        try:
            if accessible.is_method():
                method = cast(gao.GenericMethod, accessible)
                self.add_method(test_case, method, position, callee=callee)
                return True
            if accessible.is_field():
                field = cast(gao.GenericField, accessible)
                self.add_field(test_case, field, position, callee=callee)
                return True
            raise RuntimeError("Unknown accessible object")
        except ConstructionFailedException:
            self._rollback_changes(test_case, previous_length, position)
            return False

    @staticmethod
    def _select_random_variable_for_call(
        test_case: tc.TestCase, position: int
    ) -> vr.VariableReference | None:
        """Randomly select one of the variables in the test defined up to
        position to insert a call for.


        Args:
            test_case: The test case
            position: The last position

        Returns:
            A candidate, if found
        """
        candidates: list[vr.VariableReference] = [
            var
            for var in test_case.get_all_objects(position)
            if not var.is_primitive()
            and not var.is_type_unknown()
            and not isinstance(
                test_case.get_statement(var.get_statement_position()),
                stmt.NoneStatement,
            )
        ]

        if len(candidates) == 0:
            return None
        # TODO(fk) sort based on distance and use rank selection.
        return randomness.choice(candidates)

    def insert_random_call(self, test_case: tc.TestCase, position: int) -> bool:
        """Insert a random call for the unit under test at the given position.

        Args:
            test_case: The test case the call will be inserted
            position: The position of the insertion

        Returns:
            Whether or not the insertion was successful
        """
        previous_length = test_case.size()
        accessible = self._test_cluster.get_random_accessible()
        if accessible is None:
            return False

        try:
            self.append_generic_accessible(test_case, accessible, position)
        except ConstructionFailedException:
            self._rollback_changes(test_case, previous_length, position)
            return False
        return True

    @staticmethod
    def _rollback_changes(test_case: tc.TestCase, previous_length: int, position: int):
        """Rollback any changes that were made on the given test case.

        This means that we remove any extra statements that were added.
        TODO(fk) there should be a better way to do this?

        Args:
            test_case: The test case
            previous_length: The length before the modification
            position: The position
        """
        length_difference = test_case.size() - previous_length
        assert length_difference >= 0, "Cannot rollback from negative size difference."
        for i in reversed(range(length_difference)):
            test_case.remove(position + i)

    @staticmethod
    def delete_statement_gracefully(test_case: tc.TestCase, position: int) -> bool:
        """Try to delete the statement that is defined at the given index.

        We try to find replacements for the variable that is provided by this statement

        Args:
            test_case: The test case
            position: The position

        Returns:
            Whether or not the deletion was successful
        """
        variable = test_case.get_statement(position).ret_val

        changed = False
        if variable is not None:
            for i in range(position + 1, test_case.size()):
                alternatives = test_case.get_objects(variable.type, i)
                try:
                    alternatives.remove(variable)
                except ValueError:
                    pass
                if len(alternatives) > 0:
                    statement = test_case.get_statement(i)
                    if statement.references(variable):
                        statement.replace(variable, randomness.choice(alternatives))
                        changed = True

        deleted = TestFactory.delete_statement(test_case, position)
        return deleted or changed

    @staticmethod
    def delete_statement(test_case: tc.TestCase, position: int) -> bool:
        """Delete the statement at position from the test case and remove all
        references to it.

        Args:
            test_case: The test case
            position: The position

        Returns:
            Whether or not the deletion was successful
        """
        to_delete: set[int] = set()
        TestFactory._recursive_delete_inclusion(test_case, to_delete, position)
        for index in sorted(list(to_delete), reverse=True):
            test_case.remove(index)
        return True

    @staticmethod
    def _recursive_delete_inclusion(
        test_case: tc.TestCase, to_delete: set[int], position: int
    ) -> None:
        if position in to_delete:
            return  # end of recursion
        to_delete.add(position)
        references = TestFactory._get_reference_positions(test_case, position)
        # TODO(fk) is this even required?
        for i in references:
            TestFactory._recursive_delete_inclusion(test_case, to_delete, i)

    @staticmethod
    def _get_reference_positions(test_case: tc.TestCase, position: int) -> set[int]:
        references = set()
        positions = set()
        if (ret_val := test_case.get_statement(position).ret_val) is not None:
            references.add(ret_val)
            for i in range(position, test_case.size()):
                temp = set()
                for var in references:
                    if (
                        test_case.get_statement(i).references(var)
                        and (rval := test_case.get_statement(i).ret_val) is not None
                    ):
                        temp.add(rval)
                        positions.add(i)
                references.update(temp)
        return positions

    def change_random_call(
        self, test_case: tc.TestCase, statement: stmt.VariableCreatingStatement
    ) -> bool:
        """Change the call represented by this statement to another one.

        Args:
            test_case: The test case
            statement: The new statement

        Returns:
            Whether or not the operation was successful
        """
        if statement.ret_val.is_type_unknown():
            return False

        objects = test_case.get_all_objects(statement.get_position())
        type_ = statement.ret_val.type
        assert type_, "Cannot change change call, when type is unknown"
        calls = self._get_possible_calls(type_, objects)
        acc_object = statement.accessible_object()
        if acc_object in calls:
            calls.remove(acc_object)

        if len(calls) == 0:
            return False

        call = randomness.choice(calls)
        try:
            self.change_call(test_case, statement, call)
            return True
        except ConstructionFailedException:
            self._logger.exception("Failed to change call for statement.")
        return False

    def change_call(
        self,
        test_case: tc.TestCase,
        statement: stmt.VariableCreatingStatement,
        call: gao.GenericAccessibleObject,
    ):
        """Change the call of the given statement to the one that is given.

        Args:
            test_case: The test case
            statement: The given statement
            call: The new call
        """
        position = statement.ret_val.get_statement_position()
        return_value = statement.ret_val
        replacement: stmt.Statement | None = None
        if call.is_method():
            method = cast(gao.GenericMethod, call)
            assert method.owner
            callee = self._get_random_non_none_object(test_case, method.owner, position)
            parameters = self._get_reuse_parameters(
                test_case, method.inferred_signature, position
            )
            replacement = stmt.MethodStatement(test_case, method, callee, parameters)
        elif call.is_constructor():
            constructor = cast(gao.GenericConstructor, call)
            parameters = self._get_reuse_parameters(
                test_case, constructor.inferred_signature, position
            )
            replacement = stmt.ConstructorStatement(test_case, constructor, parameters)
        elif call.is_function():
            funktion = cast(gao.GenericFunction, call)
            parameters = self._get_reuse_parameters(
                test_case, funktion.inferred_signature, position
            )
            replacement = stmt.FunctionStatement(test_case, funktion, parameters)

        if replacement is None:
            assert False, f"Unhandled call type {call}"
        else:
            replacement.ret_val = return_value
            test_case.set_statement(replacement, position)

    @staticmethod
    def _get_reuse_parameters(
        test_case: tc.TestCase, inf_signature: InferredSignature, position: int
    ) -> dict[str, vr.VariableReference]:
        """Find specified parameters from existing objects.

        Args:
            test_case: The test case
            inf_signature: The inferred signature information
            position: The position

        Returns:
            A dict of existing objects
        """
        found = {}
        for parameter_name, parameter_type in inf_signature.parameters.items():
            if (
                is_optional_parameter(inf_signature, parameter_name)
                and randomness.next_float()
                < config.configuration.test_creation.skip_optional_parameter_probability
            ):
                continue
            found[parameter_name] = test_case.get_random_object(
                parameter_type, position
            )
        return found

    @staticmethod
    def _get_random_non_none_object(
        test_case: tc.TestCase, type_: type, position: int
    ) -> vr.VariableReference:
        variables = test_case.get_objects(type_, position)
        variables = [
            var
            for var in variables
            if not isinstance(
                test_case.get_statement(var.get_statement_position()),
                stmt.NoneStatement,
            )
        ]
        if len(variables) == 0:
            raise ConstructionFailedException(
                f"Found no variables of type {type_} at position {position}"
            )
        return randomness.choice(variables)

    def _get_possible_calls(
        self, return_type: type, objects: list[vr.VariableReference]
    ) -> list[gao.GenericAccessibleObject]:
        """Retrieve all the replacement calls that can be inserted at this position
         without changing the length.

         Args:
            return_type: The return type
            objects: The objects that are available as parameters.

        Returns:
            A list of possible replacement calls
        """
        calls: list[gao.GenericAccessibleObject] = []
        try:
            all_calls = self._test_cluster.get_generators_for(return_type)
        except ConstructionFailedException:
            return calls
        for i in all_calls:
            if self._dependencies_satisfied(i.get_dependencies(), objects):
                calls.append(i)
        return calls

    @staticmethod
    def _dependencies_satisfied(
        dependencies: set[type], objects: list[vr.VariableReference]
    ) -> bool:
        """Determine if the set of objects is sufficient to satisfy the set of
        dependencies.

        Args:
            dependencies: a set of types
            objects: A list of objects

        Returns:
            Whether or not the objects are sufficient to satisfy the dependencies
        """
        for type_ in dependencies:
            found = False
            for var in objects:
                if is_assignable_to(var.type, type_):
                    found = True
            if not found:
                return False
        return True

    # pylint: disable=too-many-arguments, assignment-from-none
    def satisfy_parameters(
        self,
        test_case: tc.TestCase,
        signature: InferredSignature,
        callee: vr.VariableReference | None = None,
        position: int = -1,
        recursion_depth: int = 0,
        allow_none: bool = True,
        can_reuse_existing_variables: bool = True,
    ) -> dict[str, vr.VariableReference]:
        """Satisfy a list of parameters by reusing or creating variables.

        Args:
            test_case: The test case
            signature: The inferred signature of the method
            callee: The callee of the method
            position: The current position in the test case
            recursion_depth: The recursion depth
            allow_none: Whether or not a variable can be a None value
            can_reuse_existing_variables: Whether or not existing variables shall
                be reused.

        Returns:
            A dict of variable references for the parameters

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        if position < 0:
            position = test_case.size()

        parameters: dict[str, vr.VariableReference] = {}
        self._logger.debug(
            "Trying to satisfy %d parameters at position %d",
            len(signature.parameters),
            position,
        )

        for parameter_name, parameter_type in signature.parameters.items():
            self._logger.debug("Current parameter type: %s", parameter_type)

            previous_length = test_case.size()

            if (
                is_optional_parameter(signature, parameter_name)
                and randomness.next_float()
                < config.configuration.test_creation.skip_optional_parameter_probability
            ):
                continue

            if can_reuse_existing_variables:
                self._logger.debug("Can re-use variables")
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
                    (
                        f"Failed to create variable for type {parameter_type} "
                        + f"at position {position}"
                    ),
                )

            parameters[parameter_name] = var
            current_length = test_case.size()
            position += current_length - previous_length

        self._logger.debug("Satisfied %d parameters", len(parameters))
        return parameters

    def _reuse_variable(
        self, test_case: tc.TestCase, parameter_type: type | None, position: int
    ) -> vr.VariableReference | None:
        """Reuse an existing variable, if possible.

        Args:
            test_case: the test case to take the variable from
            parameter_type: the type of the variable that is needed
            position: the position to limit the search

        Returns:
            A matching existing variable, if existing
        """

        objects = test_case.get_objects(parameter_type, position)
        probability = (
            config.configuration.test_creation.primitive_reuse_probability
            if is_primitive_type(parameter_type)
            else config.configuration.test_creation.object_reuse_probability
        )
        if objects and randomness.next_float() <= probability:
            var = randomness.choice(objects)
            self._logger.debug("Reusing variable %s for type %s", var, parameter_type)
            return var
        return None

    def _get_variable_fallback(
        self,
        test_case: tc.TestCase,
        parameter_type: type | None,
        position: int,
        recursion_depth: int,
        allow_none: bool,
    ) -> vr.VariableReference | None:
        """Best effort approach to return some kind of matching variable.

        Args:
            test_case: The test case to take the variable from
            parameter_type: the type of the variable that is needed
            position: the position to limit the search
            recursion_depth: the current recursion level
            allow_none: whether or not a None value is allowed

        Returns:
            A variable if found

        Raises:
            ConstructionFailedException: if construction of an object failed
        """
        objects = test_case.get_objects(parameter_type, position)

        # No objects to choose from, so either create random type variable or use None.
        if not objects:
            if (
                config.configuration.type_inference.guess_unknown_types
                and randomness.next_float() <= 0.85
            ):
                return self._create_random_type_variable(
                    test_case, position, recursion_depth, allow_none
                )
            if allow_none:
                return self._create_none(
                    test_case, parameter_type, position, recursion_depth
                )
            raise ConstructionFailedException(f"No objects for type {parameter_type}")

        # Could not create, so re-use an existing variable.
        self._logger.debug(
            "Choosing from %d existing objects: %s", len(objects), objects
        )
        reference = randomness.choice(objects)
        self._logger.debug(
            "Use existing object of type %s: %s", parameter_type, reference
        )
        return reference

    # pylint: disable=too-many-arguments, unused-argument, too-many-return-statements
    def _create_or_reuse_variable(
        self,
        test_case: tc.TestCase,
        parameter_type: type | None,
        position: int,
        recursion_depth: int,
        allow_none: bool,
        exclude: vr.VariableReference | None = None,
    ) -> vr.VariableReference | None:
        if is_type_unknown(parameter_type):
            if config.configuration.type_inference.guess_unknown_types:
                parameter_type = randomness.choice(
                    self._test_cluster.get_all_generatable_types()
                )
            else:
                return None

        if (
            reused_variable := self._reuse_variable(test_case, parameter_type, position)
        ) is not None:
            return reused_variable
        if (
            created_variable := self._create_variable(
                test_case,
                parameter_type,
                position,
                recursion_depth,
                allow_none,
                exclude,
            )
        ) is not None:
            return created_variable
        return self._get_variable_fallback(
            test_case, parameter_type, position, recursion_depth, allow_none
        )

    # pylint: disable=too-many-arguments
    def _create_variable(
        self,
        test_case: tc.TestCase,
        parameter_type: type | None,
        position: int,
        recursion_depth: int,
        allow_none: bool,
        exclude: vr.VariableReference | None = None,
    ) -> vr.VariableReference | None:
        return self._attempt_generation(
            test_case, parameter_type, position, recursion_depth, allow_none, exclude
        )

    # pylint: disable=too-many-arguments
    def _attempt_generation(
        self,
        test_case: tc.TestCase,
        parameter_type: type | None,
        position: int,
        recursion_depth: int,
        allow_none: bool,
        exclude: vr.VariableReference | None = None,
    ) -> vr.VariableReference | None:
        # We only select a concrete type e.g. from a union, when we are forced to
        # choose one.
        parameter_type = self._test_cluster.select_concrete_type(parameter_type)

        if not parameter_type:
            return None

        if (
            allow_none
            and randomness.next_float()
            <= config.configuration.test_creation.none_probability
        ):
            return self._create_none(
                test_case, parameter_type, position, recursion_depth
            )
        if is_primitive_type(parameter_type):
            return self._create_primitive(
                test_case,
                parameter_type,
                position,
                recursion_depth,
                constant_provider=self._constant_provider,
            )
        if is_collection_type(parameter_type):
            return self._create_collection(
                test_case,
                parameter_type,
                position,
                recursion_depth,
            )
        if type_generators := self._test_cluster.get_generators_for(parameter_type):
            return self._attempt_generation_for_type(
                test_case, position, recursion_depth, allow_none, type_generators
            )
        return None

    def _attempt_generation_for_type(
        self,
        test_case: tc.TestCase,
        position: int,
        recursion_depth: int,
        allow_none: bool,
        type_generators: OrderedSet[gao.GenericAccessibleObject],
    ) -> vr.VariableReference | None:
        type_generator = randomness.choice(type_generators)
        return self.append_generic_accessible(
            test_case,
            type_generator,
            position=position,
            recursion_depth=recursion_depth + 1,
            allow_none=allow_none,
        )

    def _create_random_type_variable(
        self,
        test_case: tc.TestCase,
        position: int,
        recursion_depth: int,
        allow_none: bool,
    ) -> vr.VariableReference | None:
        return self._create_or_reuse_variable(
            test_case=test_case,
            parameter_type=randomness.choice(
                self._test_cluster.get_all_generatable_types()
            ),
            position=position,
            recursion_depth=recursion_depth + 1,
            allow_none=allow_none,
        )

    @staticmethod
    def _create_none(
        test_case: tc.TestCase,
        parameter_type: type | None,
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        statement = stmt.NoneStatement(test_case, parameter_type)
        ret = test_case.add_variable_creating_statement(statement, position)
        ret.distance = recursion_depth
        return ret

    @staticmethod
    def _create_primitive(
        test_case: tc.TestCase,
        parameter_type: type,
        position: int,
        recursion_depth: int,
        constant_provider: ConstantProvider,
    ) -> vr.VariableReference:
        if parameter_type == int:
            statement: stmt.PrimitiveStatement = stmt.IntPrimitiveStatement(
                test_case, constant_provider=constant_provider
            )
        elif parameter_type == float:
            statement = stmt.FloatPrimitiveStatement(
                test_case, constant_provider=constant_provider
            )
        elif parameter_type == bool:
            statement = stmt.BooleanPrimitiveStatement(test_case)
        elif parameter_type == bytes:
            statement = stmt.BytesPrimitiveStatement(
                test_case, constant_provider=constant_provider
            )
        else:
            statement = stmt.StringPrimitiveStatement(
                test_case, constant_provider=constant_provider
            )
        ret = test_case.add_variable_creating_statement(statement, position)
        ret.distance = recursion_depth
        return ret

    def _create_collection(
        self,
        test_case: tc.TestCase,
        parameter_type: type,
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        if parameter_type in (list, set) or get_origin(parameter_type) in (list, set):
            return self._create_list_or_set(
                test_case, parameter_type, position, recursion_depth
            )
        if parameter_type == tuple or get_origin(parameter_type) == tuple:
            return self._create_tuple(
                test_case, parameter_type, position, recursion_depth
            )
        if parameter_type == dict or get_origin(parameter_type) == dict:
            return self._create_dict(
                test_case, parameter_type, position, recursion_depth
            )
        raise RuntimeError("Unknown collection type")

    # TODO(fk) Methods below should be refactored asap,
    # as they contain a lot of duplicate code
    def _create_list_or_set(
        self,
        test_case: tc.TestCase,
        parameter_type: type,
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        args = get_args(parameter_type)
        if len(args) == 1:
            element_type = args[0]
        else:
            element_type = Any
        size = randomness.next_int(
            0, config.configuration.test_creation.collection_size
        )
        elements = []
        for _ in range(size):
            previous_length = test_case.size()
            var = self._create_or_reuse_variable(
                test_case, element_type, position, recursion_depth + 1, True
            )
            if var is not None:
                elements.append(var)
            position += test_case.size() - previous_length
        collection_stmt = (
            stmt.ListStatement(test_case, parameter_type, elements)
            if parameter_type == list or get_origin(parameter_type) == list
            else stmt.SetStatement(test_case, parameter_type, elements)
        )
        ret = test_case.add_variable_creating_statement(collection_stmt, position)
        ret.distance = recursion_depth
        return ret

    def _create_tuple(
        self,
        test_case: tc.TestCase,
        parameter_type: type,
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        args = get_args(parameter_type)
        if len(args) == 0:
            # Untyped tuple, time to guess...
            size = randomness.next_int(
                0, config.configuration.test_creation.collection_size
            )
            args = [
                randomness.choice(self._test_cluster.get_all_generatable_types())
                for _ in range(size)
            ]
        elements = []
        for arg_type in args:
            previous_length = test_case.size()
            var = self._create_or_reuse_variable(
                test_case, arg_type, position, recursion_depth + 1, True
            )
            if var is not None:
                elements.append(var)
            position += test_case.size() - previous_length
        ret = test_case.add_variable_creating_statement(
            stmt.TupleStatement(test_case, parameter_type, elements), position
        )
        ret.distance = recursion_depth
        return ret

    def _create_dict(
        self,
        test_case: tc.TestCase,
        parameter_type: type,
        position: int,
        recursion_depth: int,
    ) -> vr.VariableReference:
        args = get_args(parameter_type)
        if len(args) == 2:
            key_type = args[0]
            value_type = args[1]
        else:
            key_type = Any
            value_type = Any
        size = randomness.next_int(
            0, config.configuration.test_creation.collection_size
        )
        elements = []
        for _ in range(size):
            previous_length = test_case.size()
            key = self._create_or_reuse_variable(
                test_case, key_type, position, recursion_depth + 1, True
            )
            position += test_case.size() - previous_length
            previous_length = test_case.size()
            value = self._create_or_reuse_variable(
                test_case, value_type, position, recursion_depth + 1, True
            )
            position += test_case.size() - previous_length
            if key is not None and value is not None:
                elements.append((key, value))

        ret = test_case.add_variable_creating_statement(
            stmt.DictStatement(test_case, parameter_type, elements), position
        )
        ret.distance = recursion_depth
        return ret

    def has_call_on_sut(self, test_case: tc.TestCase) -> bool:
        """Does the given test case have a call to the SUT?

        Args:
            test_case: the test case to check.

        Returns:
            True, iff the test case has a call on the SUT.
        """
        for statement in test_case.statements:
            if (
                statement.accessible_object()
                in self._test_cluster.accessible_objects_under_test
            ):
                return True
        return False
