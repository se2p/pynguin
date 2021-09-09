#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pynguin.assertion.mutation_analysis.collectorobserver as co
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executioncontext import ExecutionContext


class FooObserver(co.CollectionObserver):
    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ) -> None:
        pass  # pragma: no cover

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        pass  # pragma: no cover


def test_after_test_case_execution():
    observer = FooObserver()
    with mock.patch.object(observer, "_clear") as clear_mock:
        observer.after_test_case_execution(MagicMock(), MagicMock())
        clear_mock.assert_called_once()


def test_after_statement_execution():
    observer = FooObserver()
    with mock.patch.object(observer, "_increment_position") as incpos_mock:
        observer.after_statement_execution(MagicMock(), MagicMock())
        incpos_mock.assert_called_once()
