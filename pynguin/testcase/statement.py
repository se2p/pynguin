#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a base implementation of a statement representation."""
from __future__ import annotations

import abc
import logging
import math
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, get_args

from ordered_set import OrderedSet

import pynguin.configuration as config
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses import constants
from pynguin.utils import randomness
from pynguin.utils.mutation_utils import alpha_exponent_insertion
from pynguin.utils.type_utils import is_assignable_to, is_optional_parameter

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.types import InferredSignature

T = TypeVar("T")  # pylint:disable=invalid-name


class Statement(metaclass=ABCMeta):
    """An abstract base class of a statement representation."""

    _logger = logging.getLogger(__name__)

    def __init__(self, test_case: tc.TestCase) -> None:
        self._test_case = test_case
        self._assertions: OrderedSet[ass.Assertion] = OrderedSet()

    @property
    def ret_val(self) -> vr.VariableReference | None:
        """Provides the variable defined by this statement, if any.
        This is intentionally not named 'return_value' because that name is reserved by
        the mocking framework which is used in our tests.

        Returns:
            The variable defined by this statement, if any.
        """
        return None

    # pylint:disable = no-self-use
    @ret_val.setter
    def ret_val(
        self,
        reference: vr.VariableReference,  # pylint:disable=unused-argument,
    ) -> None:
        """Updates the return value of this statement.

        Args:
            reference: The new return value
        """
        return

    @property
    def test_case(self) -> tc.TestCase:
        """Provides the test case in which this statement is used.

        Returns:
            The containing test case
        """
        return self._test_case

    @abstractmethod
    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        """Provides a deep clone of this statement.

        Args:
            test_case: the new test case in which the clone will be used.
            memo: A memo that maps old variable reference to new ones.

        Returns:
            A deep clone of this statement  # noqa: DAR202
        """

    @abstractmethod
    def accept(self, visitor: StatementVisitor) -> None:
        """Accepts a visitor to visit this statement.

        Args:
            visitor: the statement visitor
        """

    @abstractmethod
    def accessible_object(self) -> gao.GenericAccessibleObject | None:
        """Provides the accessible which is used in this statement.

        Returns:
            The accessible used in the statement  # noqa: DAR202
        """

    @abstractmethod
    def mutate(self) -> bool:
        """Mutate this statement.

        Returns:
            True, if a mutation happened.  # noqa: DAR202
        """

    @abstractmethod
    def get_variable_references(self) -> set[vr.VariableReference]:
        """Get all references that are used in this statement.

        Including return values.

        Returns:
            A set of references that are used in this statements  # noqa: DAR202
        """

    def references(self, var: vr.VariableReference) -> bool:
        """Check if this statement makes use of the given variable.

        Args:
            var: the given variable

        Returns:
            Whether or not this statement makes use of the given variable
        """
        return var in self.get_variable_references()

    @abstractmethod
    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        """Replace the old variable with the new variable.

        Args:
            old: the old variable
            new: the new variable
        """

    def get_position(self) -> int:
        """Provides the position of this statement in the test case.

        Raises:
            Exception: if the statement is not found in the test case

        Returns:
            The position of this statement

        """
        for idx, stmt in enumerate(self._test_case.statements):
            if stmt == self:
                return idx
        raise Exception("Statement is not part of it's test case")

    def add_assertion(self, assertion: ass.Assertion) -> None:
        """Add the given assertion to this statement.

        Args:
            assertion: The assertion to add
        """
        self._assertions.add(assertion)

    def copy_assertions(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> OrderedSet[ass.Assertion]:
        """Returns a copy of the assertions of this statement.

        Args:
            memo: The dictionary of mappings

        Returns:
            A set of assertions
        """
        copy: OrderedSet[ass.Assertion] = OrderedSet()
        for assertion in self._assertions:
            copy.add(assertion.clone(memo))
        return copy

    @property
    def assertions(self) -> OrderedSet[ass.Assertion]:
        """Provides the assertions of this statement, which are expected
        to hold after the execution of this statement.

        Returns:
            The set of assertions of this statements
        """
        return self._assertions

    @assertions.setter
    def assertions(self, assertions: OrderedSet[ass.Assertion]) -> None:
        self._assertions = assertions

    @property
    def affects_assertions(self) -> bool:
        """Does the execution of this statement possibly affects assertions.

        Returns:
            Whether the execution of this statement possibly affect assertions.
        """
        return False

    @abstractmethod
    def structural_eq(
        self, other: Statement, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        """Comparing a statement with another statement only makes sense in the context
        of a test case. This context is added by the memo, which maps variable used in
        this test case to their counterparts in the other test case.

        Args:
            other: Check if this statement is equal to the other.
            memo: A dictionary that maps variable to their corresponding values in the
                other test case.

        Returns:
            True, if this statement is equal to the other statement and references the
            same variables.
        """

    @abstractmethod
    def structural_hash(self) -> int:
        """Required for structural_eq to work.

        Returns:
            A hash.
        """


class VariableCreatingStatement(Statement, metaclass=abc.ABCMeta):
    """Abstract superclass for statements that create new variables."""

    def __init__(self, test_case: tc.TestCase, ret_val: vr.VariableReference):
        super().__init__(test_case)
        self._ret_val = ret_val

    @property
    def ret_val(self) -> vr.VariableReference:
        return self._ret_val

    @ret_val.setter
    def ret_val(self, ret_val: vr.VariableReference) -> None:
        self._ret_val = ret_val


class StatementVisitor(metaclass=ABCMeta):
    """An abstract statement visitor."""

    @abstractmethod
    def visit_int_primitive_statement(self, stmt) -> None:
        """Visit int primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_float_primitive_statement(self, stmt) -> None:
        """Visit float primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_string_primitive_statement(self, stmt) -> None:
        """Visit string primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_bytes_primitive_statement(self, stmt) -> None:
        """Visit bytes primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_boolean_primitive_statement(self, stmt) -> None:
        """Visit boolean primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_enum_statement(self, stmt) -> None:
        """Visit enum.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_none_statement(self, stmt) -> None:
        """Visit none.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_constructor_statement(self, stmt) -> None:
        """Visit constructor.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_method_statement(self, stmt) -> None:
        """Visit method.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_function_statement(self, stmt) -> None:
        """Visit function.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_field_statement(self, stmt) -> None:
        """Visit field.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_assignment_statement(self, stmt) -> None:
        """Visit assignment.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_list_statement(self, stmt) -> None:
        """Visit list.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_set_statement(self, stmt) -> None:
        """Visit set.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_tuple_statement(self, stmt) -> None:
        """Visit tuple.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_dict_statement(self, stmt) -> None:
        """Visit dict.

        Args:
            stmt: the statement to visit
        """


class AssignmentStatement(Statement):
    """A statement that assigns the value of a variable to a reference.
    This statement does not create new variables, it only assigns values to
    possibly nested fields.

    For example:
        foo_0.baz = int_0"""

    def __init__(
        self,
        test_case: tc.TestCase,
        lhs: vr.Reference,
        rhs: vr.VariableReference,
    ):
        super().__init__(test_case)
        self._lhs = lhs
        self._rhs = rhs

    @property
    def ret_val(self) -> vr.VariableReference | None:
        return None

    @ret_val.setter
    def ret_val(
        self, ret_val: vr.VariableReference | None  # pylint:disable=unused-argument
    ) -> None:
        return

    @property
    def lhs(self) -> vr.Reference:
        """The reference that is used on the left hand side.

        Returns:
            The reference that is used on the left hand side
        """
        return self._lhs

    @property
    def rhs(self) -> vr.VariableReference:
        """The variable that is used as the right hand side.

        Returns:
            The variable used as the right hand side
        """
        return self._rhs

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return AssignmentStatement(
            test_case,
            self._lhs.clone(memo),
            self._rhs.clone(memo),
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_assignment_statement(self)

    def accessible_object(self) -> gao.GenericAccessibleObject | None:
        return None

    def mutate(self) -> bool:
        raise Exception("Implement me")

    def get_variable_references(self) -> set[vr.VariableReference]:
        refs = {self._rhs}
        if (l_var := self._lhs.get_variable_reference()) is not None:
            refs.add(l_var)
        return refs

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self._lhs == old:
            self._lhs = new
        else:
            self._lhs.replace_variable_reference(old, new)
        if self._rhs == old:
            self._rhs = new

    def structural_hash(self) -> int:
        return 31 + 17 * self._lhs.structural_hash() + 17 * self._rhs.structural_hash()

    def structural_eq(
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, AssignmentStatement):
            return False
        return self._lhs.structural_eq(other._lhs, memo) and self._rhs.structural_eq(
            other._rhs, memo
        )


class CollectionStatement(Generic[T], VariableCreatingStatement):
    """Abstract base class for collection statements."""

    def __init__(
        self,
        test_case: tc.TestCase,
        type_: type | None,
        elements: list[T],
    ):
        super().__init__(
            test_case,
            vr.VariableReference(test_case, type_),
        )
        self._elements = elements

    @property
    def elements(self) -> list[T]:
        """The elements of the collection.

        Returns:
            A list of elements
        """
        return self._elements

    def accessible_object(self) -> gao.GenericAccessibleObject | None:
        return None

    def mutate(self) -> bool:
        changed = False
        if (
            randomness.next_float()
            < config.configuration.search_algorithm.test_delete_probability
            and len(self._elements) > 0
        ):
            changed |= self._random_deletion()

        if (
            randomness.next_float()
            < config.configuration.search_algorithm.test_change_probability
            and len(self._elements) > 0
        ):
            changed |= self._random_replacement()

        if (
            randomness.next_float()
            < config.configuration.search_algorithm.test_insert_probability
        ):
            changed |= self._random_insertion()
        return changed

    def _random_deletion(self) -> bool:
        p_per_element = 1.0 / len(self._elements)
        previous_length = len(self._elements)
        self._elements = [
            element
            for element in self._elements
            if randomness.next_float() >= p_per_element
        ]
        return previous_length != len(self._elements)

    @abstractmethod
    def _replacement_supplier(self, element: T) -> T:
        """Provide an element that can replace the current element.
        May also be the original element.

        Args:
            element: the element to be replaced

        Returns:
            A fitting replacement.
        """

    def _random_replacement(self) -> bool:
        """Randomly replace elements in the collection.

        Returns:
            True, iff an element was replaced.
        """
        p_per_element = 1.0 / len(self._elements)
        changed = False
        for i, elem in enumerate(self._elements):
            if randomness.next_float() < p_per_element:
                replace = self._replacement_supplier(elem)
                self._elements[i] = replace
                changed |= replace != elem
        return changed

    @abstractmethod
    def _insertion_supplier(self) -> T | None:
        """Supply appropriate values for insertion during mutation.

        Returns:
            None, if no value can be generated.
        """

    def _random_insertion(self) -> bool:
        """Randomly insert elements into the collection.

        Returns:
            True, iff an element was inserted.
        """
        return alpha_exponent_insertion(self._elements, self._insertion_supplier)


class NonDictCollection(CollectionStatement[vr.VariableReference], metaclass=ABCMeta):
    """Abstract base class for collections that are not dicts.
    We have to handle dicts in a special way, because mutation can affect either
    the key or the value of an item."""

    def _insertion_supplier(self) -> vr.VariableReference | None:
        arg_type = (
            get_args(self.ret_val.type)[0] if get_args(self.ret_val.type) else None
        )
        # TODO(fk) what if the current type is not correct?
        possible_insertions = self.test_case.get_objects(arg_type, self.get_position())
        if len(possible_insertions) == 0:
            return None
        return randomness.choice(possible_insertions)

    def _replacement_supplier(
        self, element: vr.VariableReference
    ) -> vr.VariableReference:
        # TODO(fk) what if the current type is not correct?
        return randomness.choice(
            self.test_case.get_objects(element.type, self.get_position()) + [element]
        )

    def structural_hash(self) -> int:
        return (
            31
            + 17 * self._ret_val.structural_hash()
            + 17 * hash(frozenset((v.structural_hash()) for v in self._elements))
        )

    def structural_eq(
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self._ret_val.structural_eq(other._ret_val, memo)
            and len(self._elements) == len(other._elements)
            and all(
                {
                    left.structural_eq(right, memo)
                    for left, right in zip(self._elements, other._elements)
                }
            )
        )


class ListStatement(NonDictCollection):
    """Represents a list."""

    def get_variable_references(self) -> set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> ListStatement:
        return ListStatement(
            test_case,
            self.ret_val.type,
            [var.clone(memo) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_list_statement(self)


class SetStatement(NonDictCollection):
    """Represents a set."""

    def get_variable_references(self) -> set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> SetStatement:
        return SetStatement(
            test_case,
            self.ret_val.type,
            [var.clone(memo) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_set_statement(self)


class TupleStatement(NonDictCollection):
    """Represents a tuple."""

    def get_variable_references(self) -> set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> TupleStatement:
        return TupleStatement(
            test_case,
            self.ret_val.type,
            [var.clone(memo) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_tuple_statement(self)

    # No deletion or insertion on tuple
    # Maybe consider if structure of tuple is unknown?
    def _random_insertion(self) -> bool:
        return False

    def _random_deletion(self) -> bool:
        return False


class DictStatement(
    CollectionStatement[tuple[vr.VariableReference, vr.VariableReference]]
):
    """Represents a dict. The tuples represent key-value pairs."""

    def get_variable_references(self) -> set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        for entry in self._elements:
            references.add(entry[0])
            references.add(entry[1])
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [
            (new if elem[0] == old else elem[0], new if elem[1] == old else elem[1])
            for elem in self._elements
        ]

    def _replacement_supplier(
        self, element: tuple[vr.VariableReference, vr.VariableReference]
    ) -> tuple[vr.VariableReference, vr.VariableReference]:
        change_idx = randomness.next_int(0, 2)
        new = list(element)
        # TODO(fk) what if the current type is not correct?
        new[change_idx] = randomness.choice(
            self.test_case.get_objects(element[change_idx].type, self.get_position())
            + [element[change_idx]]
        )
        assert len(new) == 2, "Tuple must consist of key and value"
        return new[0], new[1]

    def _insertion_supplier(
        self,
    ) -> tuple[vr.VariableReference, vr.VariableReference] | None:
        # TODO(fk) what if the current type is not correct?
        key_type = (
            get_args(self.ret_val.type)[0] if get_args(self.ret_val.type) else None
        )
        val_type = (
            get_args(self.ret_val.type)[1] if get_args(self.ret_val.type) else None
        )
        possibles_keys = self.test_case.get_objects(key_type, self.get_position())
        possibles_values = self.test_case.get_objects(val_type, self.get_position())
        if len(possibles_keys) == 0 or len(possibles_values) == 0:
            return None
        return (
            randomness.choice(possibles_keys),
            randomness.choice(possibles_values),
        )

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> DictStatement:
        return DictStatement(
            test_case,
            self.ret_val.type,
            [(var[0].clone(memo), var[1].clone(memo)) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_dict_statement(self)

    def structural_hash(self) -> int:
        return (
            31
            + 17 * self._ret_val.structural_hash()
            + 17
            * hash(
                frozenset(
                    (k.structural_hash(), v.structural_hash())
                    for k, v in self._elements
                )
            )
        )

    def structural_eq(
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self._ret_val.structural_eq(other._ret_val, memo)
            and len(self._elements) == len(other._elements)
            and all(
                {
                    lk.structural_eq(rk, memo) and lv.structural_eq(rv, memo)
                    for (lk, lv), (rk, rv) in zip(self._elements, other._elements)
                }
            )
        )


class FieldStatement(VariableCreatingStatement):
    """A statement which reads a public field or a property of an object.

    For example:
        int_0 = foo_0.baz
    """

    # TODO(fk) add subclasses for staticfield and modulestaticfield?

    def __init__(
        self,
        test_case: tc.TestCase,
        field: gao.GenericField,
        source: vr.Reference,
    ):
        super().__init__(
            test_case, vr.VariableReference(test_case, field.generated_type())
        )
        self._field = field
        self._source = source

    @property
    def source(self) -> vr.Reference:
        """Provides the reference whose field is accessed.

        Returns:
            The reference whose field is accessed
        """
        return self._source

    @source.setter
    def source(self, new_source: vr.Reference) -> None:
        """Set new source.

        Args:
            new_source: The new variable to access
        """
        self._source = new_source

    def accessible_object(self) -> gao.GenericAccessibleObject | None:
        return self._field

    def mutate(self) -> bool:
        if (
            randomness.next_float()
            >= config.configuration.search_algorithm.change_parameter_probability
        ):
            return False

        objects = self.test_case.get_objects(self.source.type, self.get_position())
        if (old_var := self._source.get_variable_reference()) is not None:
            objects.remove(old_var)
        if len(objects) > 0:
            self.source = randomness.choice(objects)
            return True
        return False

    @property
    def field(self) -> gao.GenericField:
        """The used field.

        Returns:
            The used field
        """
        return self._field

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return FieldStatement(test_case, self._field, self._source.clone(memo))

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_field_statement(self)

    def get_variable_references(self) -> set[vr.VariableReference]:
        refs = {self.ret_val}
        if (var := self._source.get_variable_reference()) is not None:
            refs.add(var)
        return refs

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self._source == old:
            self._source = new
        else:
            self._source.replace_variable_reference(old, new)
        if self._ret_val == old:
            self._ret_val = new

    def structural_eq(
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, FieldStatement):
            return False
        return (
            self._field == other._field
            and self._ret_val.structural_eq(other._ret_val, memo)
            and self._source.structural_eq(other._source, memo)
        )

    def structural_hash(self) -> int:
        return 31 + 17 * hash(self._field) + 17 * self._ret_val.structural_hash()


class ParametrizedStatement(
    VariableCreatingStatement, metaclass=ABCMeta
):  # pylint: disable=W0223
    """An abstract statement that has parameters.

    Superclass for e.g., method or constructor statement.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: gao.GenericCallableAccessibleObject,
        args: dict[str, vr.VariableReference] | None = None,
    ):
        """
        Create a new statement with parameters.

        Args:
            test_case: the containing test case.
            generic_callable: the callable
            args: A map of parameter names to their values.
        """
        super().__init__(
            test_case,
            vr.VariableReference(test_case, generic_callable.generated_type()),
        )
        self._generic_callable = generic_callable
        self._args = args if args else {}

    @property
    def args(self) -> dict[str, vr.VariableReference]:
        """The dictionary mapping parameter names to the used values.

        Returns:
            A dict mapping parameter names to their values.
        """
        return self._args

    @args.setter
    def args(self, args: dict[str, vr.VariableReference]):
        self._args = args

    @property
    def raised_exceptions(self) -> set[str]:
        """Provides the set of exceptions raised by this call.

        Returns:
            The set of exceptions that can be raised by this call
        """
        return self._generic_callable.raised_exceptions

    def get_variable_references(self) -> set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self.args.values())
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        for key, value in self._args.items():
            if value == old:
                self._args[key] = new

    def _clone_args(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> dict[str, vr.VariableReference]:
        """Small helper method, to clone the args into a new test case.

        Args:
            memo: foo

        Returns:
            A dictionary of key-value argument references
        """
        new_args = {}
        for name, var in self._args.items():
            new_args[name] = var.clone(memo)
        return new_args

    def mutate(self) -> bool:
        if (
            randomness.next_float()
            >= config.configuration.search_algorithm.change_parameter_probability
        ):
            return False

        changed = False
        mutable_param_count = self._mutable_argument_count()
        if mutable_param_count > 0:
            p_per_param = 1.0 / mutable_param_count
            changed |= self._mutate_special_parameters(p_per_param)
            changed |= self._mutate_parameters(p_per_param)
        return changed

    def _mutable_argument_count(self) -> int:
        """Returns the amount of mutable parameters.

        Returns:
            The amount of mutable parameters
        """
        return len(self.args)

    # pylint: disable=unused-argument,no-self-use
    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        """Overwrite this method to mutate any parameter, which is not in arg or kwargs.
        e.g., the callee in an instance method call.

        Args:
            p_per_param: the probability per parameter

        Returns:
            Whether or not mutation should be applied
        """
        return False

    def _mutate_parameters(self, p_per_param: float) -> bool:
        """Mutates args and kwargs with the given probability.

        Args:
            p_per_param: The probability for one parameter to be mutated.

        Returns:
            Whether or not mutation changed anything
        """
        changed = False
        for param_name in self._generic_callable.inferred_signature.parameters:
            if randomness.next_float() < p_per_param:
                changed |= self._mutate_parameter(
                    param_name, self._generic_callable.inferred_signature
                )

        return changed

    def _mutate_parameter(self, param_name: str, inf_sig: InferredSignature) -> bool:
        """Replace the given parameter with another one that also fits the parameter
        type.

        Args:
            param_name: the name of the parameter that should be mutated.
            inf_sig: the inferred signature for the parameters

        Returns:
            True, if the parameter was mutated.
        """
        current = self._args.get(param_name, None)
        param_type = inf_sig.parameters[param_name]
        possible_replacements = self.test_case.get_objects(
            param_type, self.get_position()
        )

        # Param has to be optional, otherwise it would be set.
        if current is None:
            # Create value for currently unset parameter.
            if (
                randomness.next_float()
                > config.configuration.test_creation.skip_optional_parameter_probability
            ):
                if len(possible_replacements) > 0:
                    self._args[param_name] = randomness.choice(possible_replacements)
                    return True
            return False

        if (
            is_optional_parameter(inf_sig, param_name)
            and randomness.next_float()
            < config.configuration.test_creation.skip_optional_parameter_probability
        ):
            # unset parameters that are not necessary with a certain probability,
            # e.g., if they have default value or are *args, **kwargs.
            self._args.pop(param_name)

        if current in possible_replacements:
            possible_replacements.remove(current)

        # Consider duplicating an existing statement/variable.
        copy: Statement | None = None
        if self._param_count_of_type(param_type) > len(possible_replacements) + 1:
            original_param_source = self.test_case.get_statement(
                current.get_statement_position()
            )
            copy = cast(
                VariableCreatingStatement,
                original_param_source.clone(
                    self.test_case,
                    {
                        s.ret_val: s.ret_val
                        for s in self.test_case.statements
                        if s.ret_val is not None
                    },
                ),
            )
            possible_replacements.append(copy.ret_val)

        # TODO(fk) Use param_type instead of to_mutate.variable_type,
        # to make the selection broader, but this requires access to
        # the test cluster, to select a concrete type.
        # Using None as parameter value is also a possibility.
        none_statement = NoneStatement(self.test_case, current.type)
        possible_replacements.append(none_statement.ret_val)

        replacement = randomness.choice(possible_replacements)

        if copy and replacement == copy.ret_val:
            # The chosen replacement is a copy, so we have to add it to the test case.
            self.test_case.add_statement(copy, self.get_position())
            copy.mutate()
        elif replacement is none_statement.ret_val:
            # The chosen replacement is a none statement, so we have to add it to the
            # test case.
            self.test_case.add_statement(none_statement, self.get_position())

        self._args[param_name] = replacement
        return True

    def _param_count_of_type(self, type_: type | None) -> int:
        """Return the number of parameters that have the specified type.

        Args:
            type_: The type, whose occurrences should be counted.

        Returns:
            The number of occurrences.
        """
        count = 0
        if not type_:
            return 0
        for var_ref in self.args.values():
            if is_assignable_to(var_ref.type, type_):
                count += 1
        return count

    def _get_parameter_type(self, arg: int | str) -> type | None:
        parameters = self._generic_callable.inferred_signature.parameters
        if isinstance(arg, int):

            return list(parameters.values())[arg]
        return parameters[arg]

    @property
    def affects_assertions(self) -> bool:
        return True

    def structural_hash(self) -> int:
        return (
            31
            + 17 * self._ret_val.structural_hash()
            + 17 * hash(self._generic_callable)
            + 17
            * hash(frozenset((k, v.structural_hash()) for k, v in self._args.items()))
        )

    def structural_eq(
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self._ret_val.structural_eq(other._ret_val, memo)
            and self._generic_callable == other._generic_callable
            and self._args.keys() == other._args.keys()
            and all(
                {v.structural_eq(other._args[k], memo) for k, v in self._args.items()}
            )
        )


class ConstructorStatement(ParametrizedStatement):
    """A statement that constructs an object."""

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return ConstructorStatement(
            test_case, self.accessible_object(), self._clone_args(memo)
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_constructor_statement(self)

    def accessible_object(self) -> gao.GenericConstructor:
        """The used constructor.

        Returns:
            The used constructor
        """
        return cast(gao.GenericConstructor, self._generic_callable)

    def __repr__(self) -> str:
        return (
            f"ConstructorStatement({self._test_case}, "
            + f"{self._generic_callable}(args={self._args})"
        )

    def __str__(self) -> str:
        return f"{self._generic_callable}(args={self._args})" + "-> None"


class MethodStatement(ParametrizedStatement):
    """A statement that calls a method on an object."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: gao.GenericMethod,
        callee: vr.VariableReference,
        args: dict[str, vr.VariableReference] | None = None,
    ):
        """Create new method statement.

        Args:
            test_case: The containing test case
            generic_callable: The generic callable method
            callee: the object on which the method is called
            args: the arguments
        """
        super().__init__(test_case, generic_callable, args)
        self._callee = callee

    def accessible_object(self) -> gao.GenericMethod:
        """The used method.

        Returns:
            The used method
        """
        return cast(gao.GenericMethod, self._generic_callable)

    def _mutable_argument_count(self) -> int:
        # We add +1 to the count, because the callee itself can also be mutated.
        return super()._mutable_argument_count() + 1

    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        # We mutate the callee here, as the special parameter.
        if randomness.next_float() < p_per_param:
            callee = self.callee
            objects = self.test_case.get_objects(callee.type, self.get_position())
            objects.remove(callee)

            if len(objects) > 0:
                self.callee = randomness.choice(objects)
                return True
        return False

    def get_variable_references(self) -> set[vr.VariableReference]:
        references = super().get_variable_references()
        references.add(self._callee)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        super().replace(old, new)
        if self._callee == old:
            self._callee = new

    @property
    def callee(self) -> vr.VariableReference:
        """Provides the variable on which the method is invoked.

        Returns:
            The variable on which the method is invoked
        """
        return self._callee

    @callee.setter
    def callee(self, new_callee: vr.VariableReference) -> None:
        """Set new callee on which the method is invoked.

        Args:
            new_callee: Sets a new callee
        """
        self._callee = new_callee

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return MethodStatement(
            test_case,
            self.accessible_object(),
            self._callee.clone(memo),
            self._clone_args(memo),
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_method_statement(self)

    def structural_hash(self) -> int:
        return hash((super().structural_hash(), self._callee.structural_hash()))

    def structural_eq(
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        return super().structural_eq(other, memo) and self._callee.structural_eq(
            other._callee, memo
        )

    def __repr__(self) -> str:
        return (
            f"MethodStatement({self._test_case}, "
            f"{self._generic_callable}, {self._callee.type}, "
            f"args={self._args})"
        )

    def __str__(self) -> str:
        return (
            f"{self._generic_callable}(args={self._args}) -> "
            f"{self._generic_callable.generated_type()}"
        )


class FunctionStatement(ParametrizedStatement):
    """A statement that calls a function."""

    def accessible_object(self) -> gao.GenericFunction:
        """The used function.

        Returns:
            The used function
        """
        return cast(gao.GenericFunction, self._generic_callable)

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return FunctionStatement(
            test_case, self.accessible_object(), self._clone_args(memo)
        )

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_function_statement(self)

    def __repr__(self) -> str:
        return (
            f"FunctionStatement({self._test_case}, "
            f"{self._generic_callable}, {self._ret_val.type}, "
            f"args={self._args})"
        )

    def __str__(self) -> str:
        return (
            f"{self._generic_callable}(args={self._args}) -> " + f"{self._ret_val.type}"
        )


class PrimitiveStatement(Generic[T], VariableCreatingStatement):
    """Abstract primitive statement which holds a value."""

    def __init__(
        self,
        test_case: tc.TestCase,
        variable_type: type | None,
        value: T | None = None,
        constant_provider: constants.ConstantProvider | None = None,
    ) -> None:
        super().__init__(test_case, vr.VariableReference(test_case, variable_type))
        self._value = value
        self._constant_provider: constants.ConstantProvider | None = constant_provider
        if value is None:
            self.randomize_value()

    @property
    def value(self) -> T | None:
        """Provides the primitive value of this statement.

        Returns:
            The primitive value
        """
        return self._value

    @value.setter
    def value(self, value: T) -> None:
        self._value = value

    def accessible_object(self) -> gao.GenericAccessibleObject | None:
        return None

    def mutate(self) -> bool:
        old_value = self._value
        while self._value == old_value and self._value is not None:
            if (
                randomness.next_float()
                < config.configuration.search_algorithm.random_perturbation
            ):
                self.randomize_value()
            else:
                self.delta()
        return True

    def get_variable_references(self) -> set[vr.VariableReference]:
        return {self.ret_val}

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new

    @abstractmethod
    def randomize_value(self) -> None:
        """Randomize the primitive value of this statement."""

    @abstractmethod
    def delta(self) -> None:
        """Add a random delta to the value."""

    def __repr__(self) -> str:
        return (
            f"PrimitiveStatement({self._test_case}, {self._ret_val}, "
            + f"{self._value})"
        )

    def __str__(self) -> str:
        return f"{self._value}: {self._ret_val}"

    def structural_eq(
        self,
        other: Statement,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self._ret_val.structural_eq(other._ret_val, memo)
            and self._value == other._value
        )

    def structural_hash(self) -> int:
        return 31 + self._ret_val.structural_hash() + hash(self._value)


class IntPrimitiveStatement(PrimitiveStatement[int]):
    """Primitive Statement that creates an int."""

    def __init__(
        self,
        test_case: tc.TestCase,
        value: int | None = None,
        constant_provider: constants.ConstantProvider | None = None,
    ) -> None:
        super().__init__(test_case, int, value, constant_provider=constant_provider)

    def randomize_value(self) -> None:
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(int))
            is not None
        ):
            self._value = seeded_value
        else:
            self._value = int(
                randomness.next_gaussian() * config.configuration.test_creation.max_int
            )

    def delta(self) -> None:
        assert self._value is not None
        delta = math.floor(
            randomness.next_gaussian() * config.configuration.test_creation.max_delta
        )
        self._value += delta

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> IntPrimitiveStatement:
        return IntPrimitiveStatement(
            test_case, self._value, constant_provider=self._constant_provider
        )

    def __repr__(self) -> str:
        return f"IntPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: int"

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_int_primitive_statement(self)


class FloatPrimitiveStatement(PrimitiveStatement[float]):
    """Primitive Statement that creates a float."""

    def __init__(
        self,
        test_case: tc.TestCase,
        value: float | None = None,
        constant_provider: constants.ConstantProvider | None = None,
    ) -> None:
        super().__init__(test_case, float, value, constant_provider=constant_provider)

    def randomize_value(self) -> None:
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(float))
            is not None
        ):
            self._value = seeded_value
        else:
            val = (
                randomness.next_gaussian() * config.configuration.test_creation.max_int
            )
            precision = randomness.next_int(0, 7)
            self._value = round(val, precision)

    def delta(self) -> None:
        assert self._value is not None
        probability = randomness.next_float()
        if probability < 1.0 / 3.0:
            self._value += (
                randomness.next_gaussian()
                * config.configuration.test_creation.max_delta
            )
        elif probability < 2.0 / 3.0:
            self._value += randomness.next_gaussian()
        else:
            self._value = round(self._value, randomness.next_int(0, 7))

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> FloatPrimitiveStatement:
        return FloatPrimitiveStatement(
            test_case, self._value, constant_provider=self._constant_provider
        )

    def __repr__(self) -> str:
        return f"FloatPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: float"

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_float_primitive_statement(self)


class StringPrimitiveStatement(PrimitiveStatement[str]):
    """Primitive Statement that creates a String."""

    def __init__(
        self,
        test_case: tc.TestCase,
        value: str | None = None,
        constant_provider: constants.ConstantProvider | None = None,
    ) -> None:
        super().__init__(test_case, str, value, constant_provider=constant_provider)

    def randomize_value(self) -> None:
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(str))
            is not None
        ):
            self._value = seeded_value
        else:
            length = randomness.next_int(
                0, config.configuration.test_creation.string_length + 1
            )
            self._value = randomness.next_string(length)

    def delta(self) -> None:
        assert self._value is not None
        working_on = list(self._value)
        p_perform_action = 1.0 / 3.0
        if randomness.next_float() < p_perform_action and len(working_on) > 0:
            working_on = self._random_deletion(working_on)

        if randomness.next_float() < p_perform_action and len(working_on) > 0:
            working_on = self._random_replacement(working_on)

        if randomness.next_float() < p_perform_action:
            working_on = self._random_insertion(working_on)

        self._value = "".join(working_on)

    @staticmethod
    def _random_deletion(working_on: list[str]) -> list[str]:
        p_per_char = 1.0 / len(working_on)
        return [char for char in working_on if randomness.next_float() >= p_per_char]

    @staticmethod
    def _random_replacement(working_on: list[str]) -> list[str]:
        p_per_char = 1.0 / len(working_on)
        return [
            randomness.next_char() if randomness.next_float() < p_per_char else char
            for char in working_on
        ]

    @staticmethod
    def _random_insertion(working_on: list[str]) -> list[str]:
        pos = 0
        if len(working_on) > 0:
            pos = randomness.next_int(0, len(working_on) + 1)
        alpha = 0.5
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and len(working_on) < config.configuration.test_creation.string_length
        ):
            exponent += 1
            working_on = working_on[:pos] + [randomness.next_char()] + working_on[pos:]
        return working_on

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> StringPrimitiveStatement:
        return StringPrimitiveStatement(
            test_case, self._value, constant_provider=self._constant_provider
        )

    def __repr__(self) -> str:
        return f"StringPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: str"

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_string_primitive_statement(self)


class BytesPrimitiveStatement(PrimitiveStatement[bytes]):
    """Primitive Statement that creates bytes."""

    def __init__(
        self,
        test_case: tc.TestCase,
        value: bytes | None = None,
        constant_provider: constants.ConstantProvider | None = None,
    ) -> None:
        super().__init__(test_case, bytes, value, constant_provider=constant_provider)

    def randomize_value(self) -> None:
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(bytes))
            is not None
        ):
            self._value = seeded_value
        else:
            length = randomness.next_int(
                0, config.configuration.test_creation.bytes_length + 1
            )
            self._value = randomness.next_bytes(length)

    def delta(self) -> None:
        assert self._value is not None
        working_on = list(self._value)
        p_perform_action = 1.0 / 3.0
        if randomness.next_float() < p_perform_action and len(working_on) > 0:
            working_on = self._random_deletion(working_on)

        if randomness.next_float() < p_perform_action and len(working_on) > 0:
            working_on = self._random_replacement(working_on)

        if randomness.next_float() < p_perform_action:
            working_on = self._random_insertion(working_on)

        self._value = bytes(working_on)

    @staticmethod
    def _random_deletion(working_on: list[int]) -> list[int]:
        p_per_char = 1.0 / len(working_on)
        return [char for char in working_on if randomness.next_float() >= p_per_char]

    @staticmethod
    def _random_replacement(working_on: list[int]) -> list[int]:
        p_per_char = 1.0 / len(working_on)
        return [
            randomness.next_byte() if randomness.next_float() < p_per_char else byte
            for byte in working_on
        ]

    @staticmethod
    def _random_insertion(working_on: list[int]) -> list[int]:
        pos = 0
        if len(working_on) > 0:
            pos = randomness.next_int(0, len(working_on) + 1)
        alpha = 0.5
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and len(working_on) < config.configuration.test_creation.bytes_length
        ):
            exponent += 1
            working_on = working_on[:pos] + [randomness.next_byte()] + working_on[pos:]
        return working_on

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> BytesPrimitiveStatement:
        return BytesPrimitiveStatement(
            test_case, self._value, constant_provider=self._constant_provider
        )

    def __repr__(self) -> str:
        return f"BytesPrimitiveStatement({self._test_case}, {self._value!r})"

    def __str__(self) -> str:
        return f"{self._value!r}: bytes"

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_bytes_primitive_statement(self)


class BooleanPrimitiveStatement(PrimitiveStatement[bool]):
    """Primitive Statement that creates a boolean."""

    def __init__(self, test_case: tc.TestCase, value: bool | None = None) -> None:
        super().__init__(test_case, bool, value)

    def randomize_value(self) -> None:
        self._value = bool(randomness.RNG.getrandbits(1))

    def delta(self) -> None:
        assert self._value is not None
        self._value = not self._value

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> BooleanPrimitiveStatement:
        return BooleanPrimitiveStatement(test_case, self._value)

    def __repr__(self) -> str:
        return f"BooleanPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: bool"

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_boolean_primitive_statement(self)


class EnumPrimitiveStatement(PrimitiveStatement[int]):
    """Primitive Statement that references the value of an enum.
    We simply store the index of the element in the Enum."""

    def __init__(
        self,
        test_case: tc.TestCase,
        generic_enum: gao.GenericEnum,
        value: int | None = None,
    ):
        self._generic_enum = generic_enum
        super().__init__(test_case, generic_enum.generated_type(), value)

    def accessible_object(self) -> gao.GenericEnum:
        return self._generic_enum

    @property
    def value_name(self) -> str:
        """Convenience method to access the enum name that is associated with
        the stored index.

        Returns:
            The associated enum value."""
        assert self._value is not None
        return self._generic_enum.names[self._value]

    def randomize_value(self) -> None:
        self._value = randomness.next_int(0, len(self._generic_enum.names))

    def delta(self) -> None:
        assert self._value is not None
        self._value += randomness.choice([-1, 1])
        self._value = (self._value + len(self._generic_enum.names)) % len(
            self._generic_enum.names
        )

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> EnumPrimitiveStatement:
        return EnumPrimitiveStatement(test_case, self._generic_enum, value=self.value)

    def __repr__(self) -> str:
        return f"EnumPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self.value_name}: Enum"

    def structural_eq(
        self,
        other: Statement,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        return (
            super().structural_eq(other, memo)
            and isinstance(other, EnumPrimitiveStatement)
            and other._generic_enum == self._generic_enum
        )

    def structural_hash(self) -> int:
        return hash((super().structural_hash(), self._generic_enum))

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_enum_statement(self)


class NoneStatement(PrimitiveStatement):
    """A statement serving as a None reference."""

    def clone(
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> NoneStatement:
        return NoneStatement(test_case, self.ret_val.type)

    def accept(self, visitor: StatementVisitor) -> None:
        visitor.visit_none_statement(self)

    def randomize_value(self) -> None:
        pass

    def delta(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"NoneStatement({self._test_case})"

    def __str__(self) -> str:
        return "None"
