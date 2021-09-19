#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.assertion.mutation_analysis.statecollectingobserver as sco
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executioncontext import ExecutionContext


class FooObserver(sco.StateCollectingObserver):
    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ) -> None:
        pass  # pragma: no cover

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        pass  # pragma: no cover


def test_after_test_case_execution():
    observer = FooObserver(MagicMock())
    observer._objects = {"foo": "bar"}
    observer.after_test_case_execution(MagicMock(), MagicMock())
    assert observer._objects == {}


@mock.patch.object(ExecutionContext, "get_variable_value", return_value=MagicMock())
def test_after_statement_execution(exec_ctx_mock):
    observer = FooObserver(MagicMock())
    exec_ctx = ExecutionContext()
    exec_ctx._local_namespace = {"foo": "bar"}
    with mock.patch.object(observer._storage, "collect_return_value") as cs_mock_rv:
        with mock.patch.object(observer._storage, "collect_objects") as cs_mock_obj:
            with mock.patch.object(observer._storage, "collect_globals") as cs_mock_g:
                observer.after_statement_execution(
                    ps.ConstructorStatement(
                        MagicMock(spec=dtc.DefaultTestCase), MagicMock()
                    ),
                    exec_ctx,
                )
                cs_mock_rv.assert_called_once()
                cs_mock_obj.assert_called_once()
                cs_mock_g.assert_called_once()


@mock.patch.object(cs.CollectorStorage, "collect_return_value")
@mock.patch.object(cs.CollectorStorage, "collect_objects")
@mock.patch.object(cs.CollectorStorage, "collect_globals")
def test_after_statement_execution_exception(cs_mock_rv, cs_mock_obj, cs_mock_g):
    observer = FooObserver(MagicMock())
    observer.after_statement_execution(MagicMock(), MagicMock(), TypeError(MagicMock()))
    cs_mock_rv.assert_not_called()
    cs_mock_obj.assert_not_called()
    cs_mock_g.assert_not_called()


@mock.patch.object(cs.CollectorStorage, "collect_return_value")
@mock.patch.object(cs.CollectorStorage, "collect_objects")
@mock.patch.object(cs.CollectorStorage, "collect_globals")
@mock.patch.object(ExecutionContext, "get_variable_value", return_value=MagicMock())
def test_after_statement_execution_ctor_statement(
    cs_mock_rv, cs_mock_obj, cs_mock_g, exec_ctx_mock
):
    observer = FooObserver(MagicMock())
    exec_ctx = ExecutionContext()
    exec_ctx._local_namespace = {"foo": "bar"}
    observer.after_statement_execution(
        ps.ConstructorStatement(MagicMock(spec=dtc.DefaultTestCase), MagicMock()),
        exec_ctx,
    )
    assert len(observer._objects) == 1
