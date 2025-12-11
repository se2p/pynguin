#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a visitor that transforms test cases to asts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_to_ast as ata
import pynguin.testcase.statement as statmt
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.utils.namingscope as ns
from pynguin.testcase.testcasevisitor import TestCaseVisitor

if TYPE_CHECKING:
    from ast import stmt

    import pynguin.testcase.defaulttestcase as dtc
    import pynguin.testcase.execution as ex

import logging

_LOGGER = logging.getLogger(__name__)


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
        *,
        store_call_return: bool = False,
    ) -> None:
        """The module aliases are shared between test cases.

        Args:
            module_aliases: The aliases for used modules
            common_modules: The names of common modules that are not aliased
            exec_result: An optional execution result for the test case.
            store_call_return: Whether to store the call return.
        """
        self._module_aliases: ns.NamingScope = module_aliases
        # Common modules (e.g. math) are not aliased.
        self._common_modules: set[str] = common_modules
        self._exec_result = exec_result
        self._test_case_ast: list[stmt] = []
        self._is_failing_test: bool = False
        self._store_call_return: bool = store_call_return

    def visit_default_test_case(  # noqa: D102, C901
        self, test_case: dtc.DefaultTestCase
    ) -> None:
        return_type_trace = (
            None if self._exec_result is None else self._exec_result.proper_return_type_trace
        )
        variable_names = ns.VariableTypeNamingScope(return_type_trace=return_type_trace)
        self._test_case_ast = []
        self._is_failing_test = False
        self._unexpected_exceptions = set()
        self._expected_exceptions = set()

        for idx, statement in enumerate(test_case.statements):
            # Transform the statement
            must_store_for_assertions = any(
                not isinstance(a, ass.ExceptionAssertion) for a in statement.assertions
            )
            must_store_for_future_use = False
            if isinstance(statement, statmt.VariableCreatingStatement):
                ret_val = statement.ret_val
                for later_stmt in test_case.statements[idx + 1 :]:
                    if later_stmt.references(ret_val):
                        must_store_for_future_use = True
                        break

            stmt_visitor = stmt_to_ast.StatementToAstVisitor(
                self._module_aliases,
                variable_names,
                store_call_return=self._store_call_return
                or must_store_for_assertions
                or must_store_for_future_use,
            )
            statement.accept(stmt_visitor)
            stmt_node = stmt_visitor.ast_node

            # Detect unexpected exceptions
            for assertion in statement.assertions:
                if isinstance(assertion, ass.ExceptionAssertion) and isinstance(
                    statement, statmt.ParametrizedStatement
                ):
                    raised = statement.expected_exceptions
                    if assertion.exception_type_name not in raised:
                        self._unexpected_exceptions.add((idx, assertion.exception_type_name))
                    else:
                        self._expected_exceptions.add((idx, assertion.exception_type_name))

            # Transform assertions and collect nodes
            assertion_visitor = ata.PyTestAssertionToAstVisitor(
                variable_names=variable_names,
                module_aliases=self._module_aliases,
                common_modules=self._common_modules,
                statement_node=stmt_node,
            )
            for assertion in statement.assertions:
                if not isinstance(assertion, ass.ExceptionAssertion) or (
                    (idx, assertion.exception_type_name) not in self._unexpected_exceptions
                ):
                    assertion.accept(assertion_visitor)

            self._test_case_ast.extend(assertion_visitor.nodes)

        # Determine failing status based on execution evidence
        if self._exec_result is not None:
            for idx, exception in self._exec_result.exceptions.items():
                if (idx, exception.__class__.__name__) not in self._expected_exceptions:
                    self._is_failing_test = True
                    break

    @property
    def test_case_ast(self) -> list[stmt]:
        """Provides the generated statement asts for a test case.

        Returns:
            A list of the generated statement asts for a test case
        """
        return self._test_case_ast

    @property
    def is_failing_test(self) -> bool:
        """Whether this test is a failing test.

        A failing test is defined as a test that raised an exception during execution
        which was not expected, i.e., declared by its implementation.

        Returns:
            Whether this test is a failing test
        """
        return self._is_failing_test
