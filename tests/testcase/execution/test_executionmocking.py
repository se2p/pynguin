#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import threading
from unittest.mock import MagicMock

import pynguin.testcase.defaulttestcase as dtc
from pynguin.testcase.execution import ExecutionContext, ExecutionTracer, TestCaseExecutor
from pynguin.testcase.execution import ModuleProvider
from pynguin.testcase.mocking import MockedLogger
from pynguin.testcase.statement import NoneStatement


def test_logging_mocked():
    module_name = "tests.fixtures.mocking.log_to_null_handler"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    executor = TestCaseExecutor(tracer)
    ctx = ExecutionContext(ModuleProvider())
    logging_module = importlib.import_module(module_name)
    ctx._global_namespace = {"module_0": logging_module}

    test_case = MagicMock(dtc.DefaultTestCase)
    stmt = NoneStatement(test_case)

    ast_node = executor._before_statement_execution(stmt, ctx)
    executor.execute_ast(ast_node, ctx)

    logger_from_ctx = ctx.global_namespace["module_0"].logging.getLogger()
    assert isinstance(logger_from_ctx, MockedLogger)


