#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Observer collecting stating of various fields during the execution."""
import dataclasses
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


@dataclasses.dataclass
class _ExecutionState:
    position: int = 0
    objects: List[object] = dataclasses.field(default_factory=list)

    def increment(self):
        """Increments the position by one."""
        self.position += 1


class StateCollectingObserver(eo.ExecutionObserver):
    """Observer that collects the states of different fields during execution."""

    def __init__(self, storage: cs.CollectorStorage):
        self._execution_state = _ExecutionState()
        self._storage = storage

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        pass  # nothing to do here

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: res.ExecutionResult
    ) -> None:
        self._execution_state = _ExecutionState()

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
        # When an exception was raised do not do anything.
        # This is done because after an exception has occurred, the execution of the
        # test case stops and fields may be in an undefined state.
        if exception is not None:
            return

        # Get the test case id of the current statement
        assert isinstance(statement.test_case, dtc.DefaultTestCase)
        test_case_id: int = statement.test_case.id

        # If the statement was a constructor call, collect the returned object
        if isinstance(statement, ps.ConstructorStatement):
            self._execution_state.objects.append(
                exec_ctx.get_variable_value(statement.ret_val)
            )

        if isinstance(
            statement,
            (ps.ConstructorStatement, ps.MethodStatement, ps.FunctionStatement),
        ):
            # Get the return value of the statement
            return_value = exec_ctx.get_variable_value(statement.ret_val)

            # Get all loaded modules without the built in ones
            modules = cu.dict_without_keys(exec_ctx.global_namespace, {"__builtins__"})

            # Collect the states
            self._storage.collect_states(
                test_case_id=test_case_id,
                position=self._execution_state.position,
                objects=self._execution_state.objects,
                modules=modules,
                return_value=return_value,
            )
        self._execution_state.increment()
