#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
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

    def visit_default_test_case(  # noqa: D102
        self, test_case: dtc.DefaultTestCase
    ) -> None:
        self._test_case_ast = []
        return_type_trace = (
            None if self._exec_result is None else self._exec_result.proper_return_type_trace
        )
        variables = ns.VariableTypeNamingScope(return_type_trace=return_type_trace)
        for idx, statement in enumerate(test_case.statements):
            store_call_return = True
            if (
                self._exec_result is not None
                and self._exec_result.get_first_position_of_thrown_exception() == idx
            ):
                store_call_return = self._store_call_return

            # Only store the return value if it's used by subsequent statements or has assertions
            # If store_call_return is True, we always store the return value
            elif (
                not self._store_call_return
                and statement.ret_val is not None
                and not test_case.get_forward_dependencies(statement.ret_val)
                and not statement.assertions  # No assertions
            ):
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
                if self.__should_assertion_be_generated(assertion, statement):
                    assertion.accept(assertion_visitor)
                else:
                    self._common_modules.add("pytest")
                    self._is_failing_test = True
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

    @property
    def is_failing_test(self) -> bool:
        """Whether this test is a failing test.

        A failing test is defined as a test that raised an exception during execution
        which was not expected, i.e., declared by its implementation.

        Returns:
            Whether this test is a failing test
        """
        return self._is_failing_test

    @staticmethod
    def __should_assertion_be_generated(assertion, statement) -> bool:
        """Decide whether the assertion shall be generated.

        All assertion shall be generated, EXCEPT exception assertions that are not part
        of the set of explicitly raised exceptions to the statement.

        Args:
            assertion: The current assertion
            statement: The current statement

        Returns:
            Whether the assertion shall be generated for this statement
        """
        if isinstance(assertion, ass.ExceptionAssertion) and isinstance(
            statement, statmt.ParametrizedStatement
        ):
            return assertion.exception_type_name in statement.raised_exceptions
        return True
