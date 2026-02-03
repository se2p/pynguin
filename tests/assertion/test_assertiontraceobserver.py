#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
from unittest import mock
from unittest.mock import MagicMock

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertiontraceobserver as ato
import pynguin.utils.typetracing as tt
from pynguin.testcase.execution import ExecutionContext, TestCaseExecutor
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


def test_check_reference_unwraps_object_proxy():
    """Regression test: _check_reference must unwrap ObjectProxy to generate assertions."""
    observer = ato.RemoteAssertionTraceObserver()

    wrapped_value = "test_string"
    proxy = tt.ObjectProxy(wrapped_value)

    exec_ctx = MagicMock()
    exec_ctx.get_reference_value.return_value = proxy
    module_provider = MagicMock()
    ref = MagicMock()

    trace = observer._assertion_local_state.trace
    observer._check_reference(module_provider, exec_ctx, ref, position=0, trace=trace)

    assertions = list(trace.trace.get(0, []))
    assert len(assertions) == 1
    assert isinstance(assertions[0], ass.ObjectAssertion)
    assert assertions[0].object == wrapped_value


def test_check_reference_unwraps_nested_object_proxy():
    """Regression test: _check_reference handles nested ObjectProxy correctly."""
    observer = ato.RemoteAssertionTraceObserver()

    inner_value = 42
    inner_proxy = tt.ObjectProxy(inner_value)
    outer_proxy = tt.ObjectProxy(inner_proxy)

    exec_ctx = MagicMock()
    exec_ctx.get_reference_value.return_value = outer_proxy
    module_provider = MagicMock()
    ref = MagicMock()

    trace = observer._assertion_local_state.trace
    observer._check_reference(module_provider, exec_ctx, ref, position=0, trace=trace)

    assertions = list(trace.trace.get(0, []))
    assert len(assertions) == 1
    assert isinstance(assertions[0], ass.ObjectAssertion)
    assert assertions[0].object == inner_value
