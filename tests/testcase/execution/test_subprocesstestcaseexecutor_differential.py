#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import threading

import pynguin.configuration as config

from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import SubprocessTestCaseExecutor
from pynguin.testcase.execution import TestCaseExecutor


def test_simple_execution(short_test_case):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    subprocess_tracer = ExecutionTracer()
    subprocess_tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)

        result = executor.execute(short_test_case)

    with install_import_hook(config.configuration.module_name, subprocess_tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)

        subprocess_executor = SubprocessTestCaseExecutor(subprocess_tracer)

        subprocess_result = subprocess_executor.execute(short_test_case)

    assert result == subprocess_result
