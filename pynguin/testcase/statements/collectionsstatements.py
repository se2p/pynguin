#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides statements to create collections."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, Set, Tuple, Type, TypeVar

from typing_inspect import get_args

import pynguin.configuration as config
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.testcase.statements import statementvisitor as sv
from pynguin.utils import randomness
from pynguin.utils.mutation_utils import alpha_exponent_insertion

T = TypeVar("T")  # pylint:disable=invalid-name


class CollectionStatement(Generic[T], stmt.Statement):
    """Abstract base class for collection statements."""

    def __init__(
        self,
        test_case: tc.TestCase,
        type_: Optional[Type],
        elements: List[T],
    ):
        super().__init__(
            test_case,
            vri.VariableReferenceImpl(test_case, type_),
        )
        self._elements = elements

    @property
    def elements(self) -> List[T]:
        """The elements of the collection."""
        return self._elements

    def accessible_object(self) -> Optional[gao.GenericAccessibleObject]:
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
    def _insertion_supplier(self) -> Optional[T]:
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

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._ret_val) + 17 * hash(frozenset(self._elements))

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, self.__class__):
            return False
        return self._ret_val == other._ret_val and self._elements == other._elements


class NonDictCollection(CollectionStatement[vr.VariableReference], ABC):
    """Abstract base class for collections that are not dicts.
    We have to handle dicts in a special way, because mutation can affect either
    the key or the value of an item."""

    def _insertion_supplier(self) -> Optional[vr.VariableReference]:
        arg_type = (
            get_args(self.ret_val.variable_type)[0]
            if get_args(self.ret_val.variable_type)
            else None
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
            self.test_case.get_objects(element.variable_type, self.get_position())
            + [element]
        )


class ListStatement(NonDictCollection):
    """Represents a list."""

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> ListStatement:
        return ListStatement(
            test_case,
            self.ret_val.variable_type,
            [var.clone(test_case, offset) for var in self._elements],
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_list_statement(self)


class SetStatement(NonDictCollection):
    """Represents a set."""

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> SetStatement:
        return SetStatement(
            test_case,
            self.ret_val.variable_type,
            [var.clone(test_case, offset) for var in self._elements],
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_set_statement(self)


class TupleStatement(NonDictCollection):
    """Represents a tuple."""

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> TupleStatement:
        return TupleStatement(
            test_case,
            self.ret_val.variable_type,
            [var.clone(test_case, offset) for var in self._elements],
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_tuple_statement(self)

    # No deletion or insertion on tuple
    # Maybe consider if structure of tuple is unknown?
    def _random_insertion(self) -> bool:
        return False

    def _random_deletion(self) -> bool:
        return False


class DictStatement(
    CollectionStatement[Tuple[vr.VariableReference, vr.VariableReference]]
):
    """Represents a dict. The tuples represent key-value pairs."""

    def get_variable_references(self) -> Set[vr.VariableReference]:
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
        self, element: Tuple[vr.VariableReference, vr.VariableReference]
    ) -> Tuple[vr.VariableReference, vr.VariableReference]:
        change_idx = randomness.next_int(0, 2)
        new = list(element)
        # TODO(fk) what if the current type is not correct?
        new[change_idx] = randomness.choice(
            self.test_case.get_objects(
                element[change_idx].variable_type, self.get_position()
            )
            + [element[change_idx]]
        )
        assert len(new) == 2, "Tuple must consist of key and value"
        return new[0], new[1]

    def _insertion_supplier(
        self,
    ) -> Optional[Tuple[vr.VariableReference, vr.VariableReference]]:
        # TODO(fk) what if the current type is not correct?
        key_type = (
            get_args(self.ret_val.variable_type)[0]
            if get_args(self.ret_val.variable_type)
            else None
        )
        val_type = (
            get_args(self.ret_val.variable_type)[1]
            if get_args(self.ret_val.variable_type)
            else None
        )
        possibles_keys = self.test_case.get_objects(key_type, self.get_position())
        possibles_values = self.test_case.get_objects(val_type, self.get_position())
        if len(possibles_keys) == 0 and len(possibles_values) == 0:
            return None
        return (
            randomness.choice(possibles_keys),
            randomness.choice(possibles_values),
        )

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> DictStatement:
        return DictStatement(
            test_case,
            self.ret_val.variable_type,
            [
                (var[0].clone(test_case, offset), var[1].clone(test_case, offset))
                for var in self._elements
            ],
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_dict_statement(self)
