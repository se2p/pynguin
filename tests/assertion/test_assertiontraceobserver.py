#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast

from unittest import mock
from unittest.mock import MagicMock

import pynguin.assertion.assertiontraceobserver as ato

from pynguin.testcase.execution import ExecutionContext
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.statement import Statement


class FooObserver(ato.RemoteAssertionTraceObserver):
    def before_statement_execution(
        self, statement: Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        return node  # pragma: no cover

    def after_statement_execution(
        self,
        statement: Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        pass  # pragma: no cover


def test_clone():
    observer = FooObserver()
    with mock.patch.object(observer._assertion_local_state, "trace") as trace_mock:
        clone = object()
        trace_mock.clone.return_value = clone
        cloned = observer.get_trace()
        trace_mock.clone.assert_called_once()
        assert cloned == clone


def test_after_test_case_execution():
    observer = FooObserver()
    result = MagicMock()
    with mock.patch.object(observer._assertion_local_state, "trace") as trace_mock:
        clone = object()
        trace_mock.clone.return_value = clone
        observer.after_test_case_execution(MagicMock(), MagicMock(), result)
        assert result.assertion_trace == clone
