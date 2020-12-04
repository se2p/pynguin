#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a simple implementation of a variable reference."""

import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr


class VariableReferenceImpl(vr.VariableReference):
    """Basic implementation of a variable reference."""

    def clone(
        self, new_test_case: tc.TestCase, offset: int = 0
    ) -> vr.VariableReference:
        return new_test_case.get_statement(
            self.get_statement_position() + offset
        ).ret_val

    def get_statement_position(self) -> int:
        for idx, stmt in enumerate(self._test_case.statements):
            if stmt.ret_val is self:
                return idx
        raise Exception(
            "Variable reference is not declared in the test case in which it is used"
        )
