#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Observer collecting stating of various fields during the execution."""
from typing import List, Optional

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.execution.executionobserver as eo
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.testcase as tc
import pynguin.utils.collection_utils as cu
from pynguin.testcase.execution import executionresult as res
from pynguin.testcase.execution.executioncontext import ExecutionContext
from pynguin.testcase.statements import statement as stmt


class StateCollectingObserver(eo.ExecutionObserver):
    """Observer that collects the states of different fields during execution."""

    pos_default_val: int = 0
    pos_incr_step: int = 1

    def __init__(self):
        self._position: int = self.pos_default_val
        self._objects: List[object] = []

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        pass  # nothing to do here

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: res.ExecutionResult
    ) -> None:
        self._clear()

    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ) -> None:
        pass  # nothing to do here

    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Optional[Exception] = None,
    ) -> None:
        # When an exception was raised do not do anything
        if exception is not None:
            return

        # Get the test case id of the current statement
        assert isinstance(statement.test_case, dtc.DefaultTestCase)
        test_case_id: int = statement.test_case.id

        # If the statement was a constructor call, collect the returned object
        if isinstance(statement, ps.ConstructorStatement):
            self._objects.append(list(exec_ctx.local_namespace.values())[-1])

        if isinstance(
            statement,
            (ps.ConstructorStatement, ps.MethodStatement, ps.FunctionStatement),
        ):
            # Get the return value of the statement
            return_value = list(exec_ctx.local_namespace.values())[-1]

            # Get all loaded modules without the built in ones
            modules = cu.dict_without_keys(exec_ctx.global_namespace, {"__builtins__"})

            # Collect the states
            cs.CollectorStorage.collect_states(
                test_case_id=test_case_id,
                position=self._position,
                objects=self._objects,
                modules=modules,
                return_value=return_value,
            )
        self._increment_position()

    def _increment_position(self) -> None:
        self._position += self.pos_incr_step

    def _clear(self):
        self._position = self.pos_default_val
        self._objects = []
