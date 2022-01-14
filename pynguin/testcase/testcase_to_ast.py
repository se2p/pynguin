#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a visitor that transforms test cases to asts."""
from __future__ import annotations

from ast import stmt
from typing import TYPE_CHECKING

import pynguin.assertion.assertion_to_ast as ata
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.utils.namingscope as ns
from pynguin.testcase.testcasevisitor import TestCaseVisitor

if TYPE_CHECKING:
    import pynguin.testcase.defaulttestcase as dtc


class TestCaseToAstVisitor(TestCaseVisitor):
    """Transforms an arbitrary number of test cases to AST statements.

    The modules that are required by the individual test cases are gathered and given
    an alias.
    """

    def __init__(self, wrap_code: bool = False) -> None:
        """The module aliases are shared between test cases.

        Args:
            wrap_code: Whether the exported code shall be wrapped
        """
        self._module_aliases = ns.NamingScope("module")
        # Common modules (e.g. math) are not aliased.
        self._common_modules: set[str] = set()
        self._test_case_asts: list[list[stmt]] = []
        self._wrap_code = wrap_code

    def visit_default_test_case(self, test_case: dtc.DefaultTestCase) -> None:
        variables = ns.VariableTypeNamingScope()
        statement_visitor = stmt_to_ast.StatementToAstVisitor(
            self._module_aliases, variables, self._wrap_code
        )
        for statement in test_case.statements:
            statement.accept(statement_visitor)
            # TODO(fk) better way. Nest visitors?
            assertion_visitor = ata.AssertionToAstVisitor(
                variables, self._module_aliases, self._common_modules
            )
            for assertion in statement.assertions:
                assertion.accept(assertion_visitor)
            statement_visitor.append_nodes(assertion_visitor.nodes)
        self._test_case_asts.append(statement_visitor.ast_nodes)

    @property
    def test_case_asts(self) -> list[list[stmt]]:
        """Provides the generated asts for each test case.

        Returns:
            A list of the generated ASTs for each test case
        """
        return self._test_case_asts

    @property
    def module_aliases(self) -> ns.NamingScope:
        """Provides the module aliases that were used when transforming all test cases.

        Returns:
            The module aliases
        """
        return self._module_aliases

    @property
    def common_modules(self) -> set[str]:
        """Provides the common modules that were used when transforming all test cases.
        This is used, because common modules (e.g., math) should not be aliased.

        Returns:
            A set of the modules names
        """
        return self._common_modules
