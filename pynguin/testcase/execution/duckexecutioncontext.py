#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""An execution context utilising duck mocks."""
import ast
import importlib
from typing import List

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executioncontext import ExecutionContext
from pynguin.utils.namingscope import NamingScope


class DuckExecutionContext(ExecutionContext):
    """An execution context utilising duck mocks."""

    def __init__(self, test_case: tc.TestCase) -> None:
        importlib.import_module("pynguin.utils.duckmock")
        super().__init__(test_case)

    @staticmethod
    def _to_ast_nodes(
        test_case: tc.TestCase,
        variable_names: NamingScope,
        modules_aliases: NamingScope,
    ) -> List[ast.stmt]:
        visitor = stmt_to_ast.DuckStatementToAstVisitor(modules_aliases, variable_names)
        for statement in test_case.statements:
            statement.accept(visitor)
        return visitor.ast_nodes
