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
    import pynguin.testcase.execution as ex


class TestCaseToAstVisitor(TestCaseVisitor):
    """Transforms an arbitrary number of test cases to AST statements.

    The modules that are required by the individual test cases are gathered and given
    an alias.
    """

    def __init__(
        self,
        module_aliases: ns.NamingScope,
        common_modules: set[str],
        exec_result: ex.ExecutionResult | None = None,
    ) -> None:
        """The module aliases are shared between test cases.

        Args:
            module_aliases: The aliases for used modules
            common_modules: The names of common modules that are not aliased
            exec_result: An optional execution result for the test case.
        """
        self._module_aliases: ns.NamingScope = module_aliases
        # Common modules (e.g. math) are not aliased.
        self._common_modules: set[str] = common_modules
        self._exec_result = exec_result
        self._test_case_ast: list[stmt] = []

    def visit_default_test_case(self, test_case: dtc.DefaultTestCase) -> None:
        self._test_case_ast = []
        return_type_trace = (
            None if self._exec_result is None else self._exec_result.return_type_trace
        )
        variables = ns.VariableTypeNamingScope(return_type_trace=return_type_trace)
        for idx, statement in enumerate(test_case.statements):
            store_call_return = True
            if (
                self._exec_result is not None
                and self._exec_result.get_first_position_of_thrown_exception() == idx
            ):
                # If a statement causes an exception and defines a new name, we don't
                # actually want to create that name, as it will not be stored anyway.
                store_call_return = False
            statement_visitor = stmt_to_ast.StatementToAstVisitor(
                self._module_aliases, variables, store_call_return=store_call_return
            )
            statement.accept(statement_visitor)
            # TODO(fk) better way. Nest visitors?
            assertion_visitor = ata.PyTestAssertionToAstVisitor(
                variables,
                self._module_aliases,
                self._common_modules,
                statement_node=statement_visitor.ast_node,
            )
            for assertion in statement.assertions:
                assertion.accept(assertion_visitor)
            # The visitor might wrap the generated statement node,
            # so append the nodes provided by the assertion visitor
            self._test_case_ast.extend(assertion_visitor.nodes)

    @property
    def test_case_ast(self) -> list[stmt]:
        """Provides the generated statement asts for a test case.

        Returns:
            A list of the generated statement asts for a test case
        """
        return self._test_case_ast
