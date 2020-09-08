#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides artificial statements that are only used during test generation.

These artificial statements are meant as helper statements that shall never be
exported into a final test case.
"""
from abc import ABCMeta
from typing import Any, Optional, Set

import pynguin.testcase.statements.statement as stmt
from pynguin.testcase import testcase as tc
from pynguin.testcase.statements import statementvisitor as sv
from pynguin.testcase.variable import variablereference as vr
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class ArtificialStatement(stmt.Statement, metaclass=ABCMeta):
    """An abstract base class for an artificial statement."""

    def mutate(self) -> bool:
        self._logger.debug("Mutation on ArtificialStatement not possible!")
        return False


class DuckMockArtificialStatement(ArtificialStatement):
    """An artificial statement that will be replaced by a duck mock."""

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return DuckMockArtificialStatement(test_case, self._return_value)

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_duck_mock_artificial_statement(self)

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return None

    def get_variable_references(self) -> Set[vr.VariableReference]:
        return {self._return_value}

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self._return_value == old:
            self._return_value = new

    def __repr__(self) -> str:
        return (
            f"DuckMockArtificialStatement(test_case={self._test_case}, "
            f"return_value={self._return_value})"
        )

    def __str__(self) -> str:
        return f"DuckMockArtificialStatement({self._test_case}, {self._return_value})"

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, DuckMockArtificialStatement):
            return False
        return self._return_value == other._return_value

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._return_value)
