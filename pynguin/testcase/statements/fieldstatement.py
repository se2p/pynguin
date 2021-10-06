#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""
Provides a statement that accesses public fields/properties.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Set

import pynguin.configuration as config
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericField,
)

if TYPE_CHECKING:
    import pynguin.testcase.statements.statementvisitor as sv
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.variable.variablereference as vr


class FieldStatement(stmt.Statement):
    """A statement which accesses a public field or a property of an object."""

    def __init__(
        self,
        test_case: tc.TestCase,
        field: GenericField,
        source: vr.VariableReference,
    ):
        super().__init__(
            test_case, vri.VariableReferenceImpl(test_case, field.generated_type())
        )
        self._field = field
        self._source = source

    @property
    def source(self) -> vr.VariableReference:
        """Provides the variable that is accessed.

        Returns:
            The variable that is accessed
        """
        return self._source

    @source.setter
    def source(self, new_source: vr.VariableReference) -> None:
        """Set new source.

        Args:
            new_source: The new variable to access
        """
        self._source = new_source

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return self._field

    def mutate(self) -> bool:
        if (
            randomness.next_float()
            >= config.configuration.search_algorithm.change_parameter_probability
        ):
            return False

        objects = self.test_case.get_objects(
            self.source.variable_type, self.get_position()
        )
        objects.remove(self.source)
        if len(objects) > 0:
            self.source = randomness.choice(objects)
            return True
        return False

    @property
    def field(self) -> GenericField:
        """The used field.

        Returns:
            The used field
        """
        return self._field

    def clone(
        self,
        test_case: tc.TestCase,
        memo: Dict[vr.VariableReference, vr.VariableReference],
    ) -> stmt.Statement:
        return FieldStatement(test_case, self._field, self._source.clone(memo))

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_field_statement(self)

    def get_variable_references(self) -> Set[vr.VariableReference]:
        return {self.source}

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.source == old:
            self.source = new

    def structural_eq(
        self, other: Any, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> bool:
        if not isinstance(other, FieldStatement):
            return False
        return self._field == other._field and self._ret_val.structural_eq(
            other._ret_val, memo
        )

    def structural_hash(self) -> int:
        return 31 + 17 * hash(self._field) + 17 * self._ret_val.structural_hash()
