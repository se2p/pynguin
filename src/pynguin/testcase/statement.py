#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a base implementation of a statement representation."""

from __future__ import annotations

import abc
import ast
import copy
import enum
import logging
import math
import typing
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from faker import Faker

    if TYPE_CHECKING:
        from fandango.language.grammar import DerivationTree, Grammar

    FANDANGO_FAKER_AVAILABLE = True
except ImportError:
    FANDANGO_FAKER_AVAILABLE = False

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao

if config.configuration.pynguinml.ml_testing_enabled or TYPE_CHECKING:
    import pynguin.utils.pynguinml.ml_parsing_utils as mlpu

from pynguin.analyses.typesystem import (
    ANY,
    AnyType,
    InferredSignature,
    Instance,
    NoneType,
    ProperType,
    TypeInfo,
    UnionType,
)
from pynguin.large_language_model.parsing import astscoping
from pynguin.utils import mutation_utils, randomness
from pynguin.utils.fandango_faker_utils import load_fandango_grammars
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.type_utils import is_optional_parameter

if TYPE_CHECKING:
    from collections.abc import Callable

    import pynguin.testcase.testcase as tc
    from pynguin.analyses import constants
    from pynguin.testcase.testcase import TestCase

T = TypeVar("T")


class Statement(abc.ABC):
    """An abstract base class of a statement representation."""

    _logger = logging.getLogger(__name__)

    def __init__(self, test_case: tc.TestCase) -> None:
        """Constructs a new statement.

        Args:
            test_case: The test case the statement belongs to
        """
        self._test_case = test_case
        self._assertions: OrderedSet[ass.Assertion] = OrderedSet()

        # The variable defined by this statement, if any.
        # This is intentionally not named 'return_value' because that name is reserved
        # by the mocking framework which is used in our tests.
        self.ret_val: vr.VariableReference | None = None

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
            Whether this statement makes use of the given variable
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
            RuntimeError: if the statement is not found in the test case

        Returns:
            The position of this statement

        """
        for idx, stmt in enumerate(self._test_case.statements):
            if stmt == self:
                return idx
        raise RuntimeError("Statement is not part of it's test case")

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

    def has_only_exception_assertion(self) -> bool:
        """Does this statement only have an exception assertion?

        Returns:
            True, if there is only an exception assertion.
        """
        return len(self._assertions) == 1 and isinstance(
            next(iter(self._assertions)), ass.ExceptionAssertion
        )

    @property
    def assertions(self) -> OrderedSet[ass.Assertion]:
        """Provides the assertions of this statement.

        The assertions are expected to hold after the execution of this statement.

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
        """Implements a structural equivalence criterion.

        Comparing a statement with another statement only makes sense in the context
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
    def structural_hash(self, memo: dict[vr.VariableReference, int]) -> int:
        """Required for structural_eq to work.

        Args:
            memo: A dictionary that maps variables to their position in this test case.

        Returns:
            A hash.
        """


def create_statement(test_case: TestCase, value) -> VariableCreatingStatement | None:
    """Creates a new statement to the corresponding value.

    Currently, this supports primitive types, collections, and enums.

    Args:
        test_case: The test case to which the statement belongs
        value: The value for which a statement should be created

    Returns:
        A new statement that corresponds to the value, or None if no statement could be created.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Trying of creating new statement of type %r", value)
    primitive_map: Any = {
        bool: BooleanPrimitiveStatement,
        int: IntPrimitiveStatement,
        str: StringPrimitiveStatement,
        float: FloatPrimitiveStatement,
        complex: ComplexPrimitiveStatement,
        bytes: BytesPrimitiveStatement,
    }

    collection_map: Any = {
        list: ListStatement,
        tuple: TupleStatement,
        set: SetStatement,
        dict: DictStatement,
    }

    if value is None:
        return NoneStatement(test_case)
    if isinstance(value, enum.Enum):
        return EnumPrimitiveStatement(test_case, gao.GenericEnum(TypeInfo(enum.Enum)), value.value)

    value_type = type(value)
    if value_type in primitive_map:
        return primitive_map[value_type](test_case, value)
    if value_type in collection_map:
        return (
            collection_map[value_type](test_case, AnyType(), list(value))
            if value_type is not dict
            else (collection_map[value_type](value, AnyType(), value.items()))
        )
    logger.debug("Couldn't create a statement for value %r", value)
    return None


class VariableCreatingStatement(Statement, abc.ABC):
    """Abstract superclass for statements that create new variables."""

    def __init__(self, test_case: tc.TestCase, ret_val: vr.VariableReference):
        """Constructs a variable-creating statement.

        Args:
            test_case: The test case the statement belongs to
            ret_val: The reference to the statement's return value
        """
        super().__init__(test_case)
        self.ret_val: vr.VariableReference = ret_val


class StatementVisitor(abc.ABC):  # noqa: PLR0904
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
    def visit_complex_primitive_statement(self, stmt) -> None:
        """Visit complex primitive.

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
    def visit_class_primitive_statement(self, stmt) -> None:
        """Visit class primitive statement.

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
    def visit_ast_assign_statement(self, stmt: ASTAssignStatement) -> None:
        """Visit ASTAssignStatement.

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
    def visit_ndarray_statement(self, stmt) -> None:
        """Visit ndarray.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_allowed_values_statement(self, stmt) -> None:
        """Visit allowed values.

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
    foo_0.baz = int_0
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        lhs: vr.Reference,
        rhs: vr.VariableReference,
    ):
        """Initializes a new assignment statement.

        Args:
            test_case: The test case the statement belongs to
            lhs: The left-hand side of the assignment
            rhs: The right-hand side of the assignment
        """
        super().__init__(test_case)
        self._lhs = lhs
        self._rhs = rhs

    @property
    def lhs(self) -> vr.Reference:
        """The reference that is used on the left-hand side.

        Returns:
            The reference that is used on the left-hand side
        """
        return self._lhs

    @property
    def rhs(self) -> vr.VariableReference:
        """The variable that is used as the right-hand side.

        Returns:
            The variable used as the right-hand side
        """
        return self._rhs

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return AssignmentStatement(
            test_case,
            self._lhs.clone(memo),
            self._rhs.clone(memo),
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_assignment_statement(self)

    def accessible_object(self) -> gao.GenericAccessibleObject | None:  # noqa: D102
        return None

    def mutate(self) -> bool:  # noqa: D102
        raise NotImplementedError("Implement me")

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        refs = {self._rhs}
        if (l_var := self._lhs.get_variable_reference()) is not None:
            refs.add(l_var)
        return refs

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        if self._lhs == old:
            self._lhs = new
        else:
            self._lhs.replace_variable_reference(old, new)
        if self._rhs == old:
            self._rhs = new

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((self._lhs.structural_hash(memo), self._rhs.structural_hash(memo)))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, AssignmentStatement):
            return False
        return self._lhs.structural_eq(
            other._lhs,  # noqa: SLF001
            memo,
        ) and self._rhs.structural_eq(
            other._rhs,  # noqa: SLF001
            memo,
        )


class CollectionStatement(VariableCreatingStatement, Generic[T]):
    """Abstract base class for collection statements."""

    def __init__(
        self,
        test_case: tc.TestCase,
        type_: ProperType,
        elements: list[T],
    ):
        """Initializes the collection statement.

        Args:
            test_case: The test case the statement belongs to
            type_: The type of the elements in the collection
            elements: A list of elements
        """
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

    @elements.setter
    def elements(self, elements: list[T]) -> None:
        """Sets the elements of the collection.

        Args:
            elements: The new elements of the collection
        """
        self._elements = elements

    def accessible_object(self) -> gao.GenericAccessibleObject | None:  # noqa: D102
        return None

    def mutate(self) -> bool:  # noqa: D102
        changed = False
        if (
            randomness.next_float() < config.configuration.search_algorithm.test_delete_probability
            and len(self._elements) > 0
        ):
            changed |= self._random_deletion()

        if (
            randomness.next_float() < config.configuration.search_algorithm.test_change_probability
            and len(self._elements) > 0
        ):
            changed |= self._random_replacement()

        if randomness.next_float() < config.configuration.search_algorithm.test_insert_probability:
            changed |= self._random_insertion()
        return changed

    def _random_deletion(self) -> bool:
        p_per_element = 1.0 / len(self._elements)
        previous_length = len(self._elements)
        self._elements = [
            element for element in self._elements if randomness.next_float() >= p_per_element
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
        return mutation_utils.alpha_exponent_insertion(self._elements, self._insertion_supplier)


class NdArrayStatement(CollectionStatement):
    """Represents an n-dimensional array, i.e., a nested list.

    Is also used for 1 dimensional lists and tuples in ML testing.
    """

    nd_array_types = int | float | bool | complex

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        elements: list | tuple,
        np_dtype: typing.Any,  # np.generic | str
        low: float,
        high: float,
        *,
        should_be_tuple: bool,
    ):
        if not NUMPY_AVAILABLE:
            raise ValueError(
                "NumPy is not available. You can install it with poetry install --with numpy."
            )
        super().__init__(test_case, ANY, elements)  # type: ignore[arg-type]
        self._np_dtype = np.dtype(np_dtype)
        assert self._np_dtype.kind in "iufcb"
        self._low = low
        self._high = high
        self._should_be_tuple = should_be_tuple

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = set()
        references.add(self.ret_val)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:  # noqa: D102
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> NdArrayStatement:
        return NdArrayStatement(
            test_case,
            copy.deepcopy(self._elements),
            cast("np.generic", self._np_dtype),
            self._low,
            self._high,
            should_be_tuple=self._should_be_tuple,
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_ndarray_statement(self)

    def _random_deletion(self) -> bool:
        """Randomly removes elements while keeping shape valid."""
        shape = mlpu.get_shape(self._elements)

        deletable_axes = [axis for axis, size in enumerate(shape) if size > 0]
        if not deletable_axes:
            return False

        axis_index = randomness.next_int(0, len(deletable_axes))
        chosen_axis = deletable_axes[axis_index]

        axis_size = shape[chosen_axis]

        deletion_indices = [i for i in range(axis_size) if randomness.next_float() >= 0.5]

        if not deletion_indices:
            return False

        deletion_indices.sort(reverse=True)

        self._elements = mutation_utils.remove_indices_at_axis(
            self._elements, chosen_axis, deletion_indices
        )
        return True

    def _replacement_supplier(self, element: nd_array_types) -> nd_array_types:
        if self._np_dtype.kind in {"i", "u"}:
            return randomness.next_int(int(self._low), int(self._high) + 1)
        if self._np_dtype.kind == "f":
            value = self._low + (self._high - self._low) * randomness.next_float()
            precision = randomness.next_int(0, 7)
            return round(value, precision)
        if self._np_dtype.kind == "c":
            real = self._low + (self._high - self._low) * randomness.next_float()
            imag = self._low + (self._high - self._low) * randomness.next_float()
            precision_real = randomness.next_int(0, 7)
            precision_imag = randomness.next_int(0, 7)
            return complex(round(real, precision_real), round(imag, precision_imag))
        if self._np_dtype.kind == "b":
            return randomness.next_bool()
        return element

    def _random_replacement(self) -> bool:
        """Replaces elements while keeping shape valid."""
        shape = mlpu.get_shape(self._elements)
        if shape[-1] == 0:
            return False

        total_leaves = math.prod(shape)
        p = max(1.0 / total_leaves**0.5, 0.05)

        self._elements, changed = mutation_utils.apply_random_replacement(
            self._elements, p, self._replacement_supplier
        )

        return changed

    def mutate(self) -> bool:  # noqa: D102
        if self._should_be_tuple:
            assert len(mlpu.get_shape(self._elements)) == 1
            # convert tuple to list so that mutation works right
            self._elements = list(self._elements)

        mutated = super().mutate()

        if self._should_be_tuple:
            # convert it again into tuple
            self._elements = tuple(self._elements)  # type: ignore[assignment]

        return mutated

    def _insertion_supplier(self) -> nd_array_types:
        return self._replacement_supplier(0)

    def _random_insertion(self) -> bool:
        """Insert elements while keeping shape valid."""
        shape = mlpu.get_shape(self._elements)

        self._elements, changed = mutation_utils.multiple_alpha_exponent_insertion(
            self._elements, shape, self._insertion_supplier
        )

        return changed

    def _nested_to_tuple(self, nested):
        """Recursively convert a nested list into a nested tuple."""
        if isinstance(nested, list):
            return tuple(self._nested_to_tuple(item) for item in nested)
        return nested

    def structural_hash(self, memo: dict[vr.VariableReference, int]) -> int:  # noqa: D102
        ret_hash = self.ret_val.structural_hash(memo)
        nested_tuple = self._nested_to_tuple(self._elements)
        return hash((ret_hash, nested_tuple))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False

        if not self.ret_val.structural_eq(other.ret_val, memo):
            return False

        return self._elements == other._elements  # noqa: SLF001


class NonDictCollection(CollectionStatement[vr.VariableReference], abc.ABC):
    """Abstract base class for collections that are not dicts.

    We have to handle dicts in a special way, because mutation can affect either
    the key or the value of an item.
    """

    def _insertion_supplier(self) -> vr.VariableReference | None:
        # TODO(fk) what if the current type is not correct?
        if isinstance(self.ret_val.type, AnyType | NoneType | UnionType):
            arg_type: ProperType = self.ret_val.type
        else:
            instance = cast("Instance", self.ret_val.type)
            arg_type = instance.args[0] if instance.args else ANY
        possible_insertions = self.test_case.get_objects(arg_type, self.get_position())
        if len(possible_insertions) == 0:
            return None
        return randomness.choice(possible_insertions)

    def _replacement_supplier(self, element: vr.VariableReference) -> vr.VariableReference:
        # TODO(fk) what if the current type is not correct?
        return randomness.choice([
            *self.test_case.get_objects(element.type, self.get_position()),
            element,
        ])

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((
            self.ret_val.structural_hash(memo),
            frozenset((v.structural_hash(memo)) for v in self._elements),
        ))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self.ret_val.structural_eq(other.ret_val, memo)
            and len(self._elements) == len(other._elements)  # noqa: SLF001
            and all(
                left.structural_eq(right, memo)
                for left, right in zip(
                    self._elements,
                    other._elements,  # noqa: SLF001
                    strict=True,
                )
            )
        )


class ListStatement(NonDictCollection):
    """Represents a list."""

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> ListStatement:
        return ListStatement(
            test_case,
            self.ret_val.type,
            [var.clone(memo) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_list_statement(self)


class SetStatement(NonDictCollection):
    """Represents a set."""

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> SetStatement:
        return SetStatement(
            test_case,
            self.ret_val.type,
            [var.clone(memo) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_set_statement(self)


class TupleStatement(NonDictCollection):
    """Represents a tuple."""

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> TupleStatement:
        return TupleStatement(
            test_case,
            self.ret_val.type,
            [var.clone(memo) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_tuple_statement(self)

    # No deletion or insertion on tuple
    # Maybe consider if structure of tuple is unknown?
    def _random_insertion(self) -> bool:
        return False

    def _random_deletion(self) -> bool:
        return False


class DictStatement(CollectionStatement[tuple[vr.VariableReference, vr.VariableReference]]):
    """Represents a dict. The tuples represent key-value pairs."""

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = set()
        references.add(self.ret_val)
        for entry in self._elements:
            references.add(entry[0])
            references.add(entry[1])
        return references

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
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
        new[change_idx] = randomness.choice([
            *self.test_case.get_objects(element[change_idx].type, self.get_position()),
            element[change_idx],
        ])
        assert len(new) == 2, "Tuple must consist of key and value"
        return new[0], new[1]

    def _insertion_supplier(
        self,
    ) -> tuple[vr.VariableReference, vr.VariableReference] | None:
        # TODO(fk) what if the current type is not correct?
        if isinstance(self.ret_val.type, AnyType | NoneType | UnionType):
            key_type: ProperType = self.ret_val.type
            val_type: ProperType = self.ret_val.type
        else:
            instance = cast("Instance", self.ret_val.type)
            key_type = instance.args[0] if instance.args else ANY
            val_type = instance.args[1] if len(instance.args) > 1 else ANY
        possibles_keys = self.test_case.get_objects(key_type, self.get_position())
        possibles_values = self.test_case.get_objects(val_type, self.get_position())
        if len(possibles_keys) == 0 or len(possibles_values) == 0:
            return None
        return (
            randomness.choice(possibles_keys),
            randomness.choice(possibles_values),
        )

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> DictStatement:
        return DictStatement(
            test_case,
            self.ret_val.type,
            [(var[0].clone(memo), var[1].clone(memo)) for var in self._elements],
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_dict_statement(self)

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((
            self.ret_val.structural_hash(memo),
            frozenset(
                (k.structural_hash(memo), v.structural_hash(memo)) for k, v in self._elements
            ),
        ))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self.ret_val.structural_eq(other.ret_val, memo)
            and len(self._elements) == len(other._elements)  # noqa: SLF001
            and all(
                lk.structural_eq(rk, memo) and lv.structural_eq(rv, memo)
                for (lk, lv), (rk, rv) in zip(
                    self._elements,
                    other._elements,  # noqa: SLF001
                    strict=True,
                )
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
        """Initializes a new field statement.

        Args:
            test_case: The test case the statement belongs to
            field: The reference to the field
            source: The reference to the object the field belongs to
        """
        super().__init__(test_case, vr.VariableReference(test_case, field.generated_type()))
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

    def accessible_object(self) -> gao.GenericAccessibleObject | None:  # noqa: D102
        return self._field

    def mutate(self) -> bool:  # noqa: D102
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

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return FieldStatement(test_case, self._field, self._source.clone(memo))

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_field_statement(self)

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        refs = {self.ret_val}
        if (var := self._source.get_variable_reference()) is not None:
            refs.add(var)
        return refs

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        if self._source == old:
            self._source = new
        else:
            self._source.replace_variable_reference(old, new)
        if self.ret_val == old:
            self.ret_val = new

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, FieldStatement):
            return False
        return (
            self._field == other._field  # noqa: SLF001
            and self.ret_val.structural_eq(other.ret_val, memo)
            and self._source.structural_eq(other._source, memo)  # noqa: SLF001
        )

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((self._field, self.ret_val.structural_hash(memo)))


class ParametrizedStatement(VariableCreatingStatement, abc.ABC):
    """An abstract statement that has parameters.

    Superclass for e.g., method or constructor statement.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: gao.GenericCallableAccessibleObject,
        args: dict[str, vr.VariableReference] | None = None,
    ):
        """Create a new statement with parameters.

        Args:
            test_case: the containing test case.
            generic_callable: the callable
            args: A map of parameter names to their values.
        """
        super().__init__(
            test_case,
            vr.CallBasedVariableReference(test_case, generic_callable),
        )
        self._generic_callable = generic_callable
        self._args = args or {}

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

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = set()
        references.add(self.ret_val)
        references.update(self.args.values())
        return references

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
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
        return {name: var.clone(memo) for name, var in self._args.items()}

    def mutate(self) -> bool:  # noqa: D102
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

    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        """Overwrite this method to mutate any parameter.

        The parameter must not be in arg or kwargs, e.g., the callee in an instance
        method call.

        Args:
            p_per_param: the probability per parameter

        Returns:
            Whether mutation should be applied
        """
        return False

    def _mutate_parameters(self, p_per_param: float) -> bool:
        """Mutates args and kwargs with the given probability.

        Args:
            p_per_param: The probability for one parameter to be mutated.

        Returns:
            Whether mutation changed anything
        """
        changed = False
        for param_name in self._generic_callable.inferred_signature.original_parameters:
            if randomness.next_float() < p_per_param:
                changed |= self._mutate_parameter(
                    param_name, self._generic_callable.inferred_signature
                )

        return changed

    def _mutate_parameter(self, param_name: str, inf_sig: InferredSignature) -> bool:
        """Replace the given parameter with another one that also fits the type.

        Args:
            param_name: the name of the parameter that should be mutated.
            inf_sig: the inferred signature for the parameters

        Returns:
            True, if the parameter was mutated.
        """
        current = self._args.get(param_name, None)
        param_type = inf_sig.get_parameter_types({})[param_name]
        possible_replacements = self.test_case.get_objects(param_type, self.get_position())

        # Param has to be optional, otherwise it would be set.
        if current is None:
            # Create value for currently unset parameter.
            if (
                randomness.next_float()
                > config.configuration.test_creation.skip_optional_parameter_probability
                and len(possible_replacements) > 0
            ):
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
            original_param_source = self.test_case.get_statement(current.get_statement_position())
            copy = cast(
                "VariableCreatingStatement",
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

        # to make the selection broader, but this requires access to
        # the test cluster, to select a concrete type.
        # Using None as parameter value is also a possibility.
        none_statement = NoneStatement(self.test_case)
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

    def _param_count_of_type(self, type_: ProperType) -> int:
        """Return the number of parameters that have the specified type.

        Args:
            type_: The type, whose occurrences should be counted.

        Returns:
            The number of occurrences.
        """
        count = 0
        if type_ is None:
            return 0
        for var_ref in self.args.values():
            if self.test_case.test_cluster.type_system.is_maybe_subtype(var_ref.type, type_):
                count += 1
        return count

    @property
    def affects_assertions(self) -> bool:  # noqa: D102
        return True

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((
            self.ret_val.structural_hash(memo),
            self._generic_callable,
            frozenset((k, v.structural_hash(memo)) for k, v in self._args.items()),
        ))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self.ret_val.structural_eq(other.ret_val, memo)
            and self._generic_callable == other._generic_callable  # noqa: SLF001
            and self._args.keys() == other._args.keys()  # noqa: SLF001
            and all(
                v.structural_eq(other._args[k], memo)  # noqa: SLF001
                for k, v in self._args.items()
            )
        )


class ConstructorStatement(ParametrizedStatement):
    """A statement that constructs an object."""

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return ConstructorStatement(test_case, self.accessible_object(), self._clone_args(memo))

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_constructor_statement(self)

    def accessible_object(self) -> gao.GenericConstructor:
        """The used constructor.

        Returns:
            The used constructor
        """
        return cast("gao.GenericConstructor", self._generic_callable)

    def __repr__(self) -> str:
        return (
            f"ConstructorStatement({self._test_case}, {self._generic_callable}(args={self._args})"
        )

    def __str__(self) -> str:
        return f"{self._generic_callable}(args={self._args})" + "-> None"


class MethodStatement(ParametrizedStatement):
    """A statement that calls a method on an object."""

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
        return cast("gao.GenericMethod", self._generic_callable)

    def _mutable_argument_count(self) -> int:
        # We add +1 to the count, because the callee itself can also be mutated.
        return super()._mutable_argument_count() + 1

    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        # We mutate the callee here, as the special parameter.
        if randomness.next_float() < p_per_param:
            callee = self.callee
            typ = (
                ANY
                if randomness.next_float()
                < config.configuration.test_creation.use_random_object_for_call
                else callee.type
            )
            objects = self.test_case.get_objects(typ, self.get_position())
            if callee in objects:
                objects.remove(callee)

            if len(objects) > 0:
                self.callee = randomness.choice(objects)
                return True
        return False

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        references = super().get_variable_references()
        references.add(self._callee)
        return references

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
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

    def clone(  # noqa: D102
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

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_method_statement(self)

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((super().structural_hash(memo), self._callee.structural_hash(memo)))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        return super().structural_eq(other, memo) and self._callee.structural_eq(
            other._callee,  # noqa: SLF001
            memo,
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

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        generic_callable: gao.GenericCallableAccessibleObject,
        args: dict[str, vr.VariableReference] | None = None,
        *,
        should_mutate: bool = True,
    ):
        super().__init__(test_case, generic_callable, args)
        self.should_mutate = should_mutate

    def mutate(self) -> bool:
        """If the function should be mutated.

        For ML-specific testing, certain function statements should not be mutated.
        """
        if self.should_mutate:
            return super().mutate()
        return False

    def accessible_object(self) -> gao.GenericFunction:
        """The used function.

        Returns:
            The used function
        """
        return cast("gao.GenericFunction", self._generic_callable)

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        return FunctionStatement(
            test_case,
            self.accessible_object(),
            self._clone_args(memo),
            should_mutate=self.should_mutate,
        )

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_function_statement(self)

    def __repr__(self) -> str:
        return (
            f"FunctionStatement({self._test_case}, "
            f"{self._generic_callable}, {self.ret_val.type}, "
            f"args={self._args})"
        )

    def __str__(self) -> str:
        return f"{self._generic_callable}(args={self._args}) -> " + f"{self.ret_val.type}"


class PrimitiveStatement(VariableCreatingStatement, Generic[T]):
    """Abstract primitive statement which holds a value."""

    def __init__(
        self,
        test_case: tc.TestCase,
        variable_type: ProperType,
        value: T | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        """Initializes a primitive statement.

        Args:
            test_case: The test case this statement belongs to
            variable_type: The type of the value
            value: The value
            constant_provider: The provider for seeded constants
            local_search_applied: Whether local search has been applied
        """
        super().__init__(test_case, vr.VariableReference(test_case, variable_type))
        self._local_search_applied: bool = local_search_applied
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

    def accessible_object(self) -> gao.GenericAccessibleObject | None:  # noqa: D102
        return None

    def mutate(self) -> bool:  # noqa: D102
        old_value = self._value
        while self._value == old_value and self._value is not None:
            if randomness.next_float() < config.configuration.search_algorithm.random_perturbation:
                self.randomize_value()
            else:
                self.delta()
        return True

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        return {self.ret_val}

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        if self.ret_val == old:
            self.ret_val = new

    @abstractmethod
    def randomize_value(self) -> None:
        """Randomize the primitive value of this statement."""

    @abstractmethod
    def delta(self) -> None:
        """Add a random delta to the value."""

    def __repr__(self) -> str:
        return f"PrimitiveStatement({self._test_case}, {self.ret_val}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: {self.ret_val}"

    def structural_eq(  # noqa: D102
        self,
        other: Statement,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            self.ret_val.structural_eq(other.ret_val, memo) and self._value == other._value  # noqa: SLF001
        )

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((self.ret_val.structural_hash(memo), hash(self._value)))

    @property
    def local_search_applied(self) -> bool:
        """Gives back if local search has already been applied.

        If local search has been applied, it is likely that this statement is currently at a
        local optima.

        Returns:
            Gives back `True` if local search has been applied.
        """
        return self._local_search_applied

    @local_search_applied.setter
    def local_search_applied(self, applied: bool) -> None:
        self._local_search_applied = applied


class IntPrimitiveStatement(PrimitiveStatement[int]):
    """Primitive Statement that creates an int."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: int | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        local_search_applied: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(int)),
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(int)) is not None
        ):
            self._value = seeded_value
        else:
            self._value = int(
                randomness.next_gaussian() * config.configuration.test_creation.max_int
            )

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        delta = math.floor(
            randomness.next_gaussian() * config.configuration.test_creation.max_delta
        )
        self._value += delta

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> IntPrimitiveStatement:
        return IntPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"IntPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: int"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_int_primitive_statement(self)


class UIntPrimitiveStatement(PrimitiveStatement[int]):
    """Primitive Statement that creates an unsigned int."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: int | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(int)),
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    def randomize_value(self) -> None:  # noqa: D102
        if self._constant_provider:
            seeded_value = self._constant_provider.get_constant_for(int)
        else:
            seeded_value = None

        if (
            randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and seeded_value is not None
            and seeded_value >= 0
        ):
            self._value = seeded_value
        else:
            self._value = int(
                abs(randomness.next_gaussian()) * config.configuration.test_creation.max_int
            )

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        delta = math.floor(
            abs(randomness.next_gaussian()) * config.configuration.test_creation.max_delta
        )
        self._value += delta

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> UIntPrimitiveStatement:
        return UIntPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"UIntPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: int"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_int_primitive_statement(self)


class FloatPrimitiveStatement(PrimitiveStatement[float]):
    """Primitive Statement that creates a float."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: float | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(float)),
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(float)) is not None
        ):
            self._value = seeded_value
        else:
            val = randomness.next_gaussian() * config.configuration.test_creation.max_int
            precision = randomness.next_int(0, 7)
            self._value = round(val, precision)

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        probability = randomness.next_float()
        if probability < 1.0 / 3.0:
            self._value += randomness.next_gaussian() * config.configuration.test_creation.max_delta
        elif probability < 2.0 / 3.0:
            self._value += randomness.next_gaussian()
        else:
            self._value = round(self._value, randomness.next_int(0, 7))

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> FloatPrimitiveStatement:
        return FloatPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"FloatPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: float"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_float_primitive_statement(self)


class ComplexPrimitiveStatement(PrimitiveStatement[complex]):
    """Primitive Statement that creates a complex."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: complex | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(complex)),
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(complex)) is not None
        ):
            self._value = seeded_value
        else:
            real = randomness.next_gaussian() * config.configuration.test_creation.max_int
            precision_real = randomness.next_int(0, 7)
            imag = randomness.next_gaussian() * config.configuration.test_creation.max_int
            precision_imag = randomness.next_int(0, 7)
            self._value = complex(round(real, precision_real), round(imag, precision_imag))

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        probability = randomness.next_float()
        real_or_imag = randomness.next_bool()
        if probability < 1 / 3:
            if real_or_imag:
                self._value = complex(
                    self._value.real
                    + randomness.next_gaussian() * config.configuration.test_creation.max_delta,
                    self._value.imag,
                )
            else:
                self._value = complex(
                    self._value.real,
                    self._value.imag
                    + randomness.next_gaussian() * config.configuration.test_creation.max_delta,
                )
        elif probability < 2 / 3:
            if real_or_imag:
                self._value = complex(
                    self._value.real + randomness.next_gaussian(), self._value.imag
                )
            else:
                self._value = complex(
                    self._value.real, self._value.imag + +randomness.next_gaussian()
                )
        elif real_or_imag:
            self._value = complex(
                round(self._value.real, randomness.next_int(0, 7)), self._value.imag
            )
        else:
            self._value = complex(
                self._value.real, round(self._value.imag, randomness.next_int(0, 7))
            )

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> ComplexPrimitiveStatement:
        return ComplexPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"ComplexPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: complex"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_complex_primitive_statement(self)


class StringPrimitiveStatementImpl(PrimitiveStatement[str]):
    """Abstract string primitive statement implementation."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: str | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(str)),
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    def __str__(self) -> str:
        return f"{self._value}: str"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_string_primitive_statement(self)


class RandomStringPrimitiveStatement(StringPrimitiveStatementImpl):
    """Primitive Statement that creates a random String."""

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(str)) is not None
        ):
            self._value = seeded_value
        else:
            length = randomness.next_int(0, config.configuration.test_creation.string_length + 1)
            self._value = randomness.next_string(length)

    def delta(self) -> None:  # noqa: D102
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
            working_on = [*working_on[:pos], randomness.next_char(), *working_on[pos:]]
        return working_on

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> RandomStringPrimitiveStatement:
        return RandomStringPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"RandomStringPrimitiveStatement({self._test_case}, {self._value})"


class FakerStringPrimitiveStatement(RandomStringPrimitiveStatement):
    """Primitive Statement that creates a String using Faker."""

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(str)) is not None
        ):
            self._value = seeded_value
        else:
            faker = Faker(use_weighting=False)
            generators: list[Callable[[], str | int]] = [
                faker.random_number,
                faker.xml,
                faker.csv,
                faker.json,
                faker.file_path,
                faker.email,
                faker.date,
                faker.ipv4,
                faker.ipv6,
                faker.hostname,
                faker.color,
                faker.file_name,
                faker.password,
            ]
            generator = randomness.choice(generators)
            self._value = str(generator())

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> FakerStringPrimitiveStatement:
        return FakerStringPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"FakerStringPrimitiveStatement({self._test_case}, {self._value})"


class FandangoStringPrimitiveStatement(RandomStringPrimitiveStatement):
    """Primitive Statement that creates a String using Fandango."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: str | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        self._grammar: Grammar = None
        self._node: DerivationTree = None
        super().__init__(
            test_case,
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    GRAMMARS: ClassVar[list[Grammar]] = load_fandango_grammars("src/pynguin/resources/fans")

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(str)) is not None
        ):
            self._value = seeded_value
        else:
            self._grammar = randomness.choice(self.__class__.GRAMMARS)

            self._node = self._grammar.fuzz()
            self._value = str(self._node)

    def delta(self) -> None:  # noqa: D102
        if self._grammar is None:
            # mutate seeded values using random delta
            super().delta()
            return

        nodes = self._node.flatten()
        mutable_nodes = [s for s in nodes if s.symbol.is_non_terminal]
        node_to_mutate = randomness.choice(mutable_nodes)
        mutated_node = self._grammar.fuzz(node_to_mutate.symbol)
        parent = node_to_mutate.parent
        if parent is None:
            # root node
            self._node = mutated_node
        else:
            children = parent.children
            children[children.index(node_to_mutate)] = mutated_node
            parent.set_children(children)
        self._value = str(self._node)

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> FandangoStringPrimitiveStatement:
        return FandangoStringPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"FandangoStringPrimitiveStatement({self._test_case}, {self._value})"


class FandangoFakerStringPrimitiveStatement(FandangoStringPrimitiveStatement):
    """Primitive Statement that creates a String using Fandango and Faker."""

    GRAMMARS = load_fandango_grammars("src/pynguin/resources/fans/faker")

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> FandangoFakerStringPrimitiveStatement:
        return FandangoFakerStringPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"FandangoFakerStringPrimitiveStatement({self._test_case}, {self._value})"


class StringPrimitiveStatement(PrimitiveStatement[str]):
    """Primitive Statement that creates a String."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: str | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        implementation: PrimitiveStatement[str] | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        if implementation is None:
            impl_type = StringPrimitiveStatement._get_implementation()
            implementation = impl_type(test_case, value, constant_provider)

        self._impl = implementation
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(str)),
            self.value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    @staticmethod
    def _get_implementation() -> type[StringPrimitiveStatementImpl]:
        if not FANDANGO_FAKER_AVAILABLE:
            return RandomStringPrimitiveStatement

        choices = [
            RandomStringPrimitiveStatement,
            FakerStringPrimitiveStatement,
            FandangoStringPrimitiveStatement,
            FandangoFakerStringPrimitiveStatement,
        ]
        weights = [
            config.configuration.string_statement.random_string_weight,
            config.configuration.string_statement.faker_string_weight,
            config.configuration.string_statement.fandango_string_weight,
            config.configuration.string_statement.fandango_faker_string_weight,
        ]

        return randomness.choices(choices, weights)[0]

    def randomize_value(self) -> None:  # noqa: D102
        impl = StringPrimitiveStatement._get_implementation()
        self._impl = impl(
            self.test_case,
            constant_provider=self._constant_provider,
        )
        self._impl.randomize_value()
        self._value = self._impl.value

    def delta(self) -> None:  # noqa: D102
        assert self._impl is not None
        self._impl.delta()
        self._value = self._impl.value

    @property
    def value(self) -> str | None:
        """Provides the primitive value of the current implementation.

        Returns:
            The primitive value
        """
        assert self._impl is not None
        return self._impl.value

    @value.setter
    def value(self, value: str) -> None:
        self._impl.value = value
        self._value = value

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> StringPrimitiveStatement:
        return StringPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            implementation=self._impl,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"StringPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: str"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_string_primitive_statement(self)


class BytesPrimitiveStatement(PrimitiveStatement[bytes]):
    """Primitive Statement that creates bytes."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: bytes | None = None,
        constant_provider: constants.ConstantProvider | None = None,
        *,
        local_search_applied: bool = False,
    ) -> None:
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(bytes)),
            value,
            constant_provider=constant_provider,
            local_search_applied=local_search_applied,
        )

    def randomize_value(self) -> None:  # noqa: D102
        if (
            self._constant_provider
            and randomness.next_float()
            <= config.configuration.seeding.seeded_primitives_reuse_probability
            and (seeded_value := self._constant_provider.get_constant_for(bytes)) is not None
        ):
            self._value = seeded_value
        else:
            length = randomness.next_int(0, config.configuration.test_creation.bytes_length + 1)
            self._value = randomness.next_bytes(length)

    def delta(self) -> None:  # noqa: D102
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
            working_on = [*working_on[:pos], randomness.next_byte(), *working_on[pos:]]
        return working_on

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> BytesPrimitiveStatement:
        return BytesPrimitiveStatement(
            test_case,
            self._value,
            constant_provider=self._constant_provider,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"BytesPrimitiveStatement({self._test_case}, {self._value!r})"

    def __str__(self) -> str:
        return f"{self._value!r}: bytes"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_bytes_primitive_statement(self)


class BooleanPrimitiveStatement(PrimitiveStatement[bool]):
    """Primitive Statement that creates a boolean."""

    def __init__(
        self,
        test_case: tc.TestCase,
        value: bool | None = None,  # noqa: FBT001
        *,
        local_search_applied: bool = False,
    ) -> None:
        """Initializes a primitive statement for a boolean.

        Args:
            test_case: The test case this statement belongs to
            value: The boolean value
            local_search_applied: Whether local search has been applied
        """
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(bool)),
            value,
            local_search_applied=local_search_applied,
        )

    def randomize_value(self) -> None:  # noqa: D102
        self._value = bool(randomness.RNG.getrandbits(1))

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        self._value = not self._value

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> BooleanPrimitiveStatement:
        return BooleanPrimitiveStatement(
            test_case, self._value, local_search_applied=self.local_search_applied
        )

    def __repr__(self) -> str:
        return f"BooleanPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: bool"

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_boolean_primitive_statement(self)


class EnumPrimitiveStatement(PrimitiveStatement[int]):
    """Primitive Statement that references the value of an enum.

    We simply store the index of the element in the Enum.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        generic_enum: gao.GenericEnum,
        value: int | None = None,
        *,
        local_search_applied: bool = False,
    ):
        """Initializes an enum statement.

        Args:
            test_case: The test case the statement belongs to
            generic_enum: The enum
            value: The value
            local_search_applied: Whether local search has been applied
        """
        self._generic_enum = generic_enum
        super().__init__(
            test_case,
            generic_enum.generated_type(),
            value,
            local_search_applied=local_search_applied,
        )

    def accessible_object(self) -> gao.GenericEnum:  # noqa: D102
        return self._generic_enum

    @property
    def value_name(self) -> str:
        """Convenience method to access the enum name that is associated with the index.

        Returns:
            The associated enum value.
        """
        assert self._value is not None
        return self._generic_enum.names[self._value]

    def randomize_value(self) -> None:  # noqa: D102
        self._value = randomness.next_int(0, len(self._generic_enum.names))

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        self._value += randomness.choice([-1, 1])
        self._value = (self._value + len(self._generic_enum.names)) % len(self._generic_enum.names)

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> EnumPrimitiveStatement:
        return EnumPrimitiveStatement(
            test_case,
            self._generic_enum,
            value=self.value,
            local_search_applied=self.local_search_applied,
        )

    def __repr__(self) -> str:
        return f"EnumPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        return f"{self.value_name}: Enum"

    def structural_eq(  # noqa: D102
        self,
        other: Statement,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        return (
            super().structural_eq(other, memo)
            and isinstance(other, EnumPrimitiveStatement)
            and other._generic_enum == self._generic_enum  # noqa: SLF001
        )

    def structural_hash(  # noqa: D102
        self, memo: dict[vr.VariableReference, int]
    ) -> int:
        return hash((super().structural_hash(memo), self._generic_enum))

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_enum_statement(self)


class ClassPrimitiveStatement(PrimitiveStatement[int]):
    """Primitive Statement that references a class."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        value: int | None = None,
        *,
        local_search_applied: bool = False,
    ):
        # TODO(fk) think about type being generic/bound, e.g., type[Foo]
        # We store the index in the global class list here.
        super().__init__(
            test_case,
            Instance(test_case.test_cluster.type_system.to_type_info(type)),
            value,
            local_search_applied=local_search_applied,
        )

    @property
    def type_info(self) -> TypeInfo:
        """Convenience method to access the type that is associated with the index.

        Returns:
            The associated type info.
        """
        assert self._value is not None
        return self._test_case.test_cluster.type_system.get_all_types()[self._value]

    def randomize_value(self) -> None:  # noqa: D102
        self._value = randomness.next_int(
            0, len(self._test_case.test_cluster.type_system.get_all_types())
        )

    def delta(self) -> None:  # noqa: D102
        assert self._value is not None
        num_classes = len(self._test_case.test_cluster.type_system.get_all_types())
        self._value += randomness.choice([-1, 1])
        self._value = (self._value + num_classes) % num_classes

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> ClassPrimitiveStatement:
        return ClassPrimitiveStatement(
            test_case, value=self.value, local_search_applied=self.local_search_applied
        )

    def __repr__(self) -> str:
        return f"ClassPrimitiveStatement({self._test_case}, {self._value})"

    def __str__(self) -> str:
        assert self._value is not None
        return f"{self.type_info.full_name}: type"

    def structural_eq(  # noqa: D102
        self,
        other: Statement,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        return super().structural_eq(other, memo) and isinstance(other, ClassPrimitiveStatement)

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_class_primitive_statement(self)


class NoneStatement(PrimitiveStatement[None]):
    """A statement serving as a None reference."""

    def __init__(self, test_case: tc.TestCase):  # noqa: D107
        super().__init__(test_case, NoneType())

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> NoneStatement:
        return NoneStatement(test_case)

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_none_statement(self)

    def randomize_value(self) -> None:
        """Cannot randomize a value for None."""

    def delta(self) -> None:
        """Cannot compute a delta for None."""

    def __repr__(self) -> str:
        return f"NoneStatement({self._test_case})"

    def __str__(self) -> str:
        return "None"


class ASTAssignStatement(VariableCreatingStatement, abc.ABC):
    """A statement creating a variable on the LHS.

    with an uninterpreted AST node as its RHS. These statements might
    not execute successfully.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        rhs: ast.AST | astscoping.VariableRefAST,
        ref_dict: dict[str, vr.VariableReference],
    ):
        """Initializes the ASTAssignStatement.

        Args:
            test_case: The test case to which this statement belongs.
            rhs: The right-hand side as an AST or VariableRefAST.
            ref_dict: A dictionary of variable references.
        """
        super().__init__(test_case, vr.VariableReference(test_case, ANY))
        if isinstance(rhs, astscoping.VariableRefAST):
            self._rhs = rhs
        elif isinstance(rhs, ast.AST):
            self._rhs = astscoping.VariableRefAST(rhs, ref_dict)
        else:
            raise ValueError(
                f"Tried to create an ASTAssignStatement with a RHS of type {type(rhs)}"
            )

    @property
    def rhs(self):
        """Provides access to the right-hand side (RHS) of the statement.

        Returns:
            astscoping.VariableRefAST: The RHS of the statement.
        """
        return self._rhs

    @rhs.setter
    def rhs(self, value: astscoping.VariableRefAST):
        """Updates the right-hand side (RHS) of the statement.

        Args:
            value (astscoping.VariableRefAST): The new RHS value.
        """
        self._rhs = value

    def clone(  # noqa: D102
        self,
        test_case: tc.TestCase,
        memo: dict[vr.VariableReference, vr.VariableReference],
    ) -> Statement:
        new_rhs = self.rhs.clone(memo)
        return ASTAssignStatement(test_case, new_rhs, {})

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_ast_assign_statement(self)

    def accessible_object(self) -> gao.GenericAccessibleObject | None:  # noqa: D102
        return None

    def mutate(self) -> bool:  # noqa: D102
        return self.rhs.mutate_var_ref(set(self._test_case.get_all_objects(self.get_position())))

    def get_variable_references(self) -> set[vr.VariableReference]:  # noqa: D102
        return self.rhs.get_all_var_refs()

    def replace(  # noqa: D102
        self, old: vr.VariableReference, new: vr.VariableReference
    ) -> None:
        self.rhs = self.rhs.replace_var_ref(old, new)

    def structural_hash(self, memo) -> int:  # noqa: D102
        return hash((self.ret_val.structural_hash(memo), self.rhs.structural_hash(memo)))

    def structural_eq(  # noqa: D102
        self, other: Any, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, ASTAssignStatement):
            return False
        return self.ret_val.structural_eq(other.ret_val, memo) and self.rhs.structural_eq(
            other.rhs, memo
        )

    def get_rhs_as_normal_ast(
        self, vr_replacer: Callable[[vr.VariableReference], ast.Name | ast.Attribute]
    ) -> ast.AST:
        """Converts the RHS into a standard AST.

        Args:
            vr_replacer: A function that replaces VariableReferences with ast.Names
                         or ast.Attributes.

        Returns:
            ast.AST: The converted AST.
        """
        return self.rhs.get_normal_ast(vr_replacer)

    def rhs_is_call(self) -> bool:
        """Checks if the RHS is a function call.

        Returns:
            bool: True if the RHS represents a function call, otherwise False.
        """
        return self.rhs.is_call()


class AllowedValuesStatement(PrimitiveStatement):
    """Primitive Statement that only allows certain values."""

    def __init__(  # noqa: D107
        self,
        test_case: tc.TestCase,
        allowed_values: list[int | float | bool | str],
        *,
        value: float | bool | str | None = None,
    ) -> None:
        super().__init__(
            test_case,
            ANY,
            value,
            constant_provider=None,
        )
        self._allowed_values = allowed_values

    def mutate(self) -> bool:  # noqa: D102
        self.randomize_value()
        return True

    def randomize_value(self) -> None:  # noqa: D102
        self._value = randomness.choice(self._allowed_values)

    def delta(self) -> None:
        """Cannot compute a delta for allowed values."""

    def clone(  # noqa: D102
        self, test_case: tc.TestCase, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> AllowedValuesStatement:
        return AllowedValuesStatement(test_case, self._allowed_values, value=self._value)

    def accept(self, visitor: StatementVisitor) -> None:  # noqa: D102
        visitor.visit_allowed_values_statement(self)

    def __repr__(self) -> str:
        return f"AllowedValuesStatement({self._test_case}, {self._allowed_values}, {self._value})"

    def __str__(self) -> str:
        return f"{self._value}: any"
