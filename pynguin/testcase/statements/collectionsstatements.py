#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides statements to create collections."""

from __future__ import annotations

from typing import Any, List, Optional, Set, Type

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.testcase.statements import statementvisitor as sv


class ListStatement(stmt.Statement):
    """Represents a list"""

    def __init__(
        self,
        test_case: tc.TestCase,
        type_: Optional[Type],
        elements: List[vr.VariableReference],
    ):
        """
        Create a collection which takes its values from parameters.

        Args:
            test_case: the containing test case.
            type_: the generated type
            elements: the elements, for list, set and tuple.
        """
        super().__init__(
            test_case,
            vri.VariableReferenceImpl(test_case, type_),
        )
        self._elements = elements

    @property
    def elements(self) -> List[vr.VariableReference]:
        """The elements of the list."""
        return self._elements

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> ListStatement:
        return ListStatement(
            test_case,
            self.ret_val.variable_type,
            [var.clone(test_case, offset) for var in self._elements],
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_list_statement(self)

    def accessible_object(self) -> Optional[gao.GenericAccessibleObject]:
        return None

    def mutate(self) -> bool:
        # TODO
        pass

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = [new if arg == old else arg for arg in self._elements]

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._ret_val) + 17 * hash(frozenset(self._elements))

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, ListStatement):
            return False
        return self._ret_val == other._ret_val and self._elements == other._elements


class SetStatement(stmt.Statement):
    """Represents a set."""

    def __init__(
        self,
        test_case: tc.TestCase,
        type_: Optional[Type],
        elements: Set[vr.VariableReference],
    ):
        """
        Create a set of given type and elements.

        Args:
            test_case: the containing test case.
            type_: the generated type
            elements: the elements, for list, set and tuple.
        """
        super().__init__(
            test_case,
            vri.VariableReferenceImpl(test_case, type_),
        )
        self._elements = elements

    @property
    def elements(self) -> Set[vr.VariableReference]:
        """The elements of the list."""
        return self._elements

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> SetStatement:
        return SetStatement(
            test_case,
            self.ret_val.variable_type,
            {var.clone(test_case, offset) for var in self._elements},
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_set_statement(self)

    def accessible_object(self) -> Optional[gao.GenericAccessibleObject]:
        return None

    def mutate(self) -> bool:
        # TODO
        pass

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self._elements)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        self._elements = {new if arg == old else arg for arg in self._elements}

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._ret_val) + 17 * hash(frozenset(self._elements))

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, SetStatement):
            return False
        return self._ret_val == other._ret_val and self._elements == other._elements
