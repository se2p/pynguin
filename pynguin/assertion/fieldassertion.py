#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a field assertion."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pynguin.assertion.assertion as ass
import pynguin.testcase.variable.variablereference as vr
from pynguin.assertion import assertionvisitor as av


class FieldAssertion(ass.Assertion):
    """An assertion for asserting fields."""

    def __init__(self,
                 source: Optional[vr.VariableReference],
                 value: Any,
                 field: str,
                 module: str = None,
                 owners: List[str] = None):
        """Creates a new field assertion.

        Args:
            source: optional for a variable in the testcase on which we assert something.
            value: the expected value of the assertion.
            field: the field which should be asserted
            module: the module which contains the field
            owners: the list of owners of the field.
                    If this is set to 'None' the field is an attribute
        """
        super().__init__(source, value)

        self._field = field
        self._module = module
        self._owners = owners

    @property
    def field(self) -> str:
        """Provides the field which should be asserted.

        Returns:
            a string of the field which should be asserted
        """
        return self._field

    @property
    def module(self) -> str:
        """Provides the module which contains the field to assert.

        Returns:
            a string with the name of alias of the module.
        """
        return self._module

    @property
    def owners(self) -> List[str]:
        """Provides a list of owners of the field.
        If this is set to 'None' the field is an attribute from an object.

        Returns:
            the list of owners of the field.
        """
        return self._owners

    def accept(self, visitor: av.AssertionVisitor) -> None:
        visitor.visit_field_assertion(self)

    def clone(
        self, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> FieldAssertion:
        return FieldAssertion(self._source.clone(memo)
                              if self._source else None,
                              self.value,
                              self._field,
                              self._module,
                              self._owners)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FieldAssertion)
            and self._source == other._source
            and self._value == other._value
            and self._field == other._field
            and self._module == other._module
            and self._owners == other._owners
        )

    def __hash__(self) -> int:
        return hash((self._source, self._field, self._module))
