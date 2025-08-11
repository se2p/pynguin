#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib

import pynguin.configuration as config

from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import SubprocessTestCaseExecutor
from pynguin.testcase.execution import TestCaseExecutor


def test_simple_execution(short_test_case, subject_properties: SubjectProperties):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"

    with install_import_hook(config.configuration.module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(config.configuration.module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)

        result = executor.execute(short_test_case)

    with install_import_hook(config.configuration.module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(config.configuration.module_name)
            importlib.reload(module)

        subprocess_executor = SubprocessTestCaseExecutor(subject_properties)

        subprocess_result = subprocess_executor.execute(short_test_case)

    assert result == subprocess_result
