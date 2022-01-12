#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Observer collecting stating of various fields during the execution."""
from __future__ import annotations

from typing import Any

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.testcase.execution as ex
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.collection_utils as cu


class StateCollectingObserver(ex.ExecutionObserver):
    """Observer that collects the states of different fields during execution."""

    def __init__(self, storage: cs.CollectorStorage):
        self._storage = storage

        self._objects: dict[vr.VariableReference, Any] = {}

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        pass  # nothing to do here

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ) -> None:
        self._objects = {}

    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ex.ExecutionContext
    ) -> None:
        pass  # nothing to do here

    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ex.ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        # When an exception was raised do not do anything.
        # This is done because after an exception has occurred, the execution of the
        # test case stops and fields may be in an undefined state.
        if exception is not None:
            return

        # If the statement was a constructor call, collect the returned object
        if isinstance(statement, stmt.ConstructorStatement):
            self._objects[statement.ret_val] = exec_ctx.get_reference_value(
                statement.ret_val
            )

        if isinstance(
            statement,
            (stmt.ConstructorStatement, stmt.MethodStatement, stmt.FunctionStatement),
        ):
            # Get the return value of the statement
            return_value = exec_ctx.get_reference_value(statement.ret_val)

            # Get all loaded modules without the built in ones
            modules = cu.dict_without_keys(exec_ctx.global_namespace, {"__builtins__"})

            # Collect all states
            self._storage.collect(statement, return_value, self._objects, modules)
