#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from __future__ import annotations

from typing import Dict, List, Optional, Set
from unittest import mock

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr


class DummyCollectionStatement(stmt.CollectionStatement[vr.VariableReference]):
    def structural_eq(
        self,
        other: stmt.Statement,
        memo: Dict[vr.VariableReference, vr.VariableReference],
    ) -> bool:
        return True  # pragma: no cover

    def structural_hash(self) -> int:
        return True  # pragma: no cover

    def _replacement_supplier(
        self, element: vr.VariableReference
    ) -> vr.VariableReference:
        return self.elements[0]

    def _insertion_supplier(self) -> Optional[vr.VariableReference]:
        return self.elements[0]

    def clone(
        self, test_case: tc.TestCase, offset: int = 0
    ) -> DummyCollectionStatement:
        pass  # pragma: no cover

    def accept(self, visitor: stmt.StatementVisitor) -> None:
        pass  # pragma: no cover

    def get_variable_references(self) -> Set[vr.VariableReference]:
        pass  # pragma: no cover

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        pass  # pragma: no cover


def test_elements():
    test_case = dtc.DefaultTestCase()
    int0 = stmt.IntPrimitiveStatement(test_case, 3)
    dummy = DummyCollectionStatement(test_case, List[int], [int0.ret_val])
    test_case.add_statements([int0, dummy])
    assert dummy.elements == [int0.ret_val]


def test_accessible_element():
    test_case = dtc.DefaultTestCase()
    dummy = DummyCollectionStatement(test_case, List[int], [])
    assert dummy.accessible_object() is None


def test_random_replacement():
    test_case = dtc.DefaultTestCase()
    int0 = stmt.IntPrimitiveStatement(test_case, 3)
    int1 = stmt.IntPrimitiveStatement(test_case, 5)
    dummy = DummyCollectionStatement(test_case, List[int], [int0.ret_val, int1.ret_val])
    test_case.add_statements([int0, int1, dummy])
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [1, 0]
        assert dummy._random_replacement()
        assert dummy.elements == [int0.ret_val, int0.ret_val]


def test_random_insertion():
    test_case = dtc.DefaultTestCase()
    int0 = stmt.IntPrimitiveStatement(test_case, 3)
    int1 = stmt.IntPrimitiveStatement(test_case, 5)
    dummy = DummyCollectionStatement(test_case, List[int], [int0.ret_val])
    test_case.add_statements([int0, int1, dummy])
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.2
        assert dummy._random_insertion()
        assert dummy.elements == [
            int0.ret_val,
            int0.ret_val,
            int0.ret_val,
            int0.ret_val,
        ]


def test_random_deletion():
    test_case = dtc.DefaultTestCase()
    int0 = stmt.IntPrimitiveStatement(test_case, 3)
    int1 = stmt.IntPrimitiveStatement(test_case, 5)
    dummy = DummyCollectionStatement(test_case, List[int], [int0.ret_val, int1.ret_val])
    test_case.add_statements([int0, int1, dummy])
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [1, 0]
        assert dummy._random_deletion()
        assert dummy.elements == [int0.ret_val]
