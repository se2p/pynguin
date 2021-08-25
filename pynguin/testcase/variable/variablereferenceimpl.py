#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a simple implementation of a variable reference."""
from typing import Dict

import pynguin.testcase.variable.variablereference as vr


class VariableReferenceImpl(vr.VariableReference):
    """Basic implementation of a variable reference."""

    def clone(
        self, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> vr.VariableReference:
        return memo[self]

    def get_statement_position(self) -> int:
        for idx, stmt in enumerate(self._test_case.statements):
            if stmt.ret_val == self:
                return idx
        raise Exception(
            "Variable reference is not declared in the test case in which it is used"
        )
