#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import logging
import threading

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import ExecutionContext
from pynguin.testcase.execution import ModuleProvider
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.mocking import MockedLogger
from tests.testcase.execution.fixtures import file_to_open  # noqa: F401


def test_logging():
    importlib.reload(logging)
    module_name = "tests.fixtures.mocking.log_to_null_handler"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    executor = TestCaseExecutor(tracer)
    ctx = ExecutionContext(ModuleProvider())

    cluster = generate_test_cluster(module_name)
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    anything = module_0.log_to_null()
    """
        )
    )
    test_case = transformer.testcases[0]
    stmt = test_case.statements[0]

    ast_node = executor._before_statement_execution(stmt, ctx)
    executor.execute_ast(ast_node, ctx)

    # the logger should be a MockedLogger
    logger_from_ctx = ctx.global_namespace["module_0"].logging.getLogger()
    assert isinstance(logger_from_ctx, MockedLogger)

    own_logger = logging.getLogger()
    for handler in own_logger.handlers:
        if hasattr(handler, "baseFilename"):
            assert handler.baseFilename != "/dev/null"

    logging.shutdown()  # should not result in handlers that can not be released
