#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Observer collecting stating of various fields during the execution."""
from typing import Any, Dict, Optional

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.testcase.execution.executionobserver as eo
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.utils.collection_utils as cu
from pynguin.testcase.execution import executionresult as res
from pynguin.testcase.execution.executioncontext import ExecutionContext
from pynguin.testcase.statements import statement as stmt


class StateCollectingObserver(eo.ExecutionObserver):
    """Observer that collects the states of different fields during execution."""

    def __init__(self, storage: cs.CollectorStorage):
        self._storage = storage

        self._objects: Dict[vr.VariableReference, Any] = {}

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        pass  # nothing to do here

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: res.ExecutionResult
    ) -> None:
        self._objects = {}

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

        # If the statement was a constructor call, collect the returned object
        if isinstance(statement, ps.ConstructorStatement):
            self._objects[statement.ret_val] = exec_ctx.get_variable_value(
                statement.ret_val
            )

        if isinstance(
            statement,
            (ps.ConstructorStatement, ps.MethodStatement, ps.FunctionStatement),
        ):
            # Get the return value of the statement
            return_value = exec_ctx.get_variable_value(statement.ret_val)
            self._storage.collect_return_value(statement, return_value)

            # Get all loaded modules without the built in ones
            modules = cu.dict_without_keys(exec_ctx.global_namespace, {"__builtins__"})
            self._storage.collect_globals(statement, modules)

            # Get all fields of the objects
            self._storage.collect_objects(statement, self._objects)
