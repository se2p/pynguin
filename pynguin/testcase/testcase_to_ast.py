#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a visitor that transforms test cases to asts."""
from ast import stmt
from typing import List

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement_to_ast as stmt_to_ast
from pynguin.testcase.testcasevisitor import TestCaseVisitor
from pynguin.utils.namingscope import NamingScope


class TestCaseToAstVisitor(TestCaseVisitor):
    """Transforms an arbitrary number of test cases to AST statements.

    The modules that are required by the individual test cases are gathered and given
    an alias.
    """

    def __init__(self, wrap_code: bool = False) -> None:
        """The module aliases are shared between test cases.

        Args:
            wrap_code: Whether or not exported code shall be wrapped
        """
        self._module_aliases = NamingScope("module")
        self._test_case_asts: List[List[stmt]] = []
        self._wrap_code = wrap_code

    def visit_default_test_case(self, test_case: dtc.DefaultTestCase) -> None:
        statement_visitor = stmt_to_ast.StatementToAstVisitor(
            self._module_aliases, NamingScope(), self._wrap_code
        )
        for statement in test_case.statements:
            statement.accept(statement_visitor)
        self._test_case_asts.append(statement_visitor.ast_nodes)

    @property
    def test_case_asts(self) -> List[List[stmt]]:
        """Provides the generated asts for each test case.

        Returns:
            A list of the generated ASTs for each test case
        """
        return self._test_case_asts

    @property
    def module_aliases(self) -> NamingScope:
        """Provides the module aliases that were used when transforming all test cases.

        Returns:
            The module aliases
        """
        return self._module_aliases
