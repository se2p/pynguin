#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides statements to create collections."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Generic, List, Optional, Set, Tuple, Type, TypeVar

from typing_inspect import get_args

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.testcase.statements import statementvisitor as sv

# pylint:disable=invalid-name
from pynguin.utils import randomness

T = TypeVar("T")


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
        """The elements of the list."""
        return self._elements

    def accessible_object(self) -> Optional[gao.GenericAccessibleObject]:
        return None

    def mutate(self) -> bool:
        p_perform_action = 1.0 / 3.0
        changed = False
        if randomness.next_float() < p_perform_action and len(self._elements) > 0:
            changed |= self._random_deletion()

        if randomness.next_float() < p_perform_action and len(self._elements) > 0:
            changed |= self._random_replacement()

        if randomness.next_float() < p_perform_action:
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
    def _random_replacement(self) -> bool:
        pass

    @abstractmethod
    def _random_insertion(self) -> bool:
        pass

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._ret_val) + 17 * hash(frozenset(self._elements))

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, self.__class__):
            return False
        return self._ret_val == other._ret_val and self._elements == other._elements


class ListStatement(CollectionStatement[vr.VariableReference]):
    """Represents a list"""

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

    def _random_replacement(self) -> bool:
        p_per_element = 1.0 / len(self._elements)
        changed = False
        for i, elem in enumerate(self._elements):
            if randomness.next_float() < p_per_element:
                # TODO(fk) what if the current type is not correct?
                replace = randomness.choice(
                    self.test_case.get_objects(elem.variable_type, self.get_position())
                    + [elem]
                )
                self._elements[i] = replace
                changed |= replace != elem
        return changed

    def _random_insertion(self) -> bool:
        changed = False
        pos = 0
        if len(self._elements) > 0:
            pos = randomness.next_int(0, len(self._elements) + 1)
        # This is so ugly...
        arg_type = (
            get_args(self.ret_val.variable_type)[0]
            if get_args(self.ret_val.variable_type)
            else None
        )
        possibles_insertions = self.test_case.get_objects(arg_type, self.get_position())
        alpha = 0.5
        exponent = 1
        while randomness.next_float() <= pow(alpha, exponent):
            exponent += 1
            if len(possibles_insertions) > 0:
                self._elements.insert(pos, randomness.choice(possibles_insertions))
                changed = True
        return changed


class SetStatement(CollectionStatement[vr.VariableReference]):
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

    def _random_replacement(self) -> bool:
        p_per_element = 1.0 / len(self._elements)
        changed = False
        for i, elem in enumerate(self._elements):
            if randomness.next_float() < p_per_element:
                # TODO(fk) what if the current type is not correct?
                replace = randomness.choice(
                    self.test_case.get_objects(elem.variable_type, self.get_position())
                    + [elem]
                )
                self._elements[i] = replace
                changed |= replace != elem
        return changed

    def _random_insertion(self) -> bool:
        changed = False
        pos = 0
        if len(self._elements) > 0:
            pos = randomness.next_int(0, len(self._elements) + 1)
        # This is so ugly...
        arg_type = (
            get_args(self.ret_val.variable_type)[0]
            if get_args(self.ret_val.variable_type)
            else None
        )
        possibles_insertions = self.test_case.get_objects(arg_type, self.get_position())
        alpha = 0.5
        exponent = 1
        while randomness.next_float() <= pow(alpha, exponent):
            exponent += 1
            if len(possibles_insertions) > 0:
                self._elements.insert(pos, randomness.choice(possibles_insertions))
                changed = True
        return changed


class TupleStatement(CollectionStatement[vr.VariableReference]):
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

    def _random_replacement(self) -> bool:
        p_per_element = 1.0 / len(self._elements)
        changed = False
        for i, elem in enumerate(self._elements):
            if randomness.next_float() < p_per_element:
                # TODO(fk) what if the current type is not correct?
                replace = randomness.choice(
                    self.test_case.get_objects(elem.variable_type, self.get_position())
                    + [elem]
                )
                self._elements[i] = replace
                changed |= replace != elem
        return changed

    # No deletion or insertion on tuple
    def _random_insertion(self) -> bool:
        return False

    def _random_deletion(self) -> bool:
        return False


class DictStatement(
    CollectionStatement[Tuple[vr.VariableReference, vr.VariableReference]]
):
    """Represents a dict. The tuple represents key-value pairs."""

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

    def _random_replacement(self) -> bool:
        p_per_element = 1.0 / len(self._elements)
        changed = False
        for i, elem in enumerate(self._elements):
            if randomness.next_float() < p_per_element:
                if randomness.next_bool():
                    # TODO(fk) what if the current type is not correct?
                    new_key = randomness.choice(
                        self.test_case.get_objects(
                            elem[0].variable_type, self.get_position()
                        )
                        + [elem[0]]
                    )
                    replace = (new_key, elem[1])
                else:
                    new_value = randomness.choice(
                        self.test_case.get_objects(
                            elem[1].variable_type, self.get_position()
                        )
                        + [elem[1]]
                    )
                    replace = (elem[0], new_value)
                self._elements[i] = replace
                changed |= replace != elem
        return changed

    def _random_insertion(self) -> bool:
        changed = False
        pos = 0
        if len(self._elements) > 0:
            pos = randomness.next_int(0, len(self._elements) + 1)
        # This is so ugly...
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
        alpha = 0.5
        exponent = 1
        while randomness.next_float() <= pow(alpha, exponent):
            exponent += 1
            if len(possibles_keys) > 0 and len(possibles_values) > 0:
                self._elements.insert(
                    pos,
                    (
                        randomness.choice(possibles_keys),
                        randomness.choice(possibles_values),
                    ),
                )
                changed = True
        return changed

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
