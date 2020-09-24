#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide an execution observer"""

from abc import abstractmethod

import pynguin.testcase.statements.statement as stmt
from pynguin.testcase.execution.executioncontext import ExecutionContext


# pylint:disable=too-few-public-methods
class ExecutionObserver:
    """An Observer that can be used to observer statement execution"""

    @abstractmethod
    def after_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ) -> None:
        """
        Called after a statement was executed.

        Args:
            statement: the statement that was executed.
            exec_ctx: the current execution context.

        """
