#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.analyses.duckmock.typeanalysis import TypeAnalysis
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution.ducktestcaseexecutor import DuckTestCaseExecutor
from pynguin.testcase.execution.executiontracer import ExecutionTracer


@pytest.fixture
def executor_with_mocked_tracer() -> DuckTestCaseExecutor:
    config.INSTANCE.module_name = "tests.fixtures.examples.triangle"
    tracer = MagicMock(ExecutionTracer)
    with install_import_hook(config.INSTANCE.module_name, tracer):
        yield DuckTestCaseExecutor(tracer)


def test_type_analysis_illegal(executor_with_mocked_tracer):
    with pytest.raises(AssertionError):
        executor_with_mocked_tracer.type_analysis = None


def test_type_analysis(executor_with_mocked_tracer):
    analysis = MagicMock(TypeAnalysis)
    executor_with_mocked_tracer.type_analysis = analysis
    assert executor_with_mocked_tracer.type_analysis is analysis
