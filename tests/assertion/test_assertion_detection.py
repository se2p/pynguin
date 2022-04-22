#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Tests if the assertions inside a pytest unit test are correctly traced by pynguin
to calculate the checked coverage metric."""

import importlib.util
import threading

import pynguin.configuration as config
from pynguin.instrumentation.instrumentation import (
    CheckedCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import AssertionData, ExecutionTracer, TestCaseExecutor
from tests.slicer.test_assertionslicer import get_plus_test_with_assertions


def test_single_assertion():
    trace = _get_assertion_trace_for_module("tests.fixtures.assertion.basic")

    assert len(trace.assertions) == 1
    assert trace.assertions[0].traced_assertion_pop_jump.lineno == 16


def test_multiple_assertions():
    trace = _get_assertion_trace_for_module("tests.fixtures.assertion.multiple")

    assert len(trace.assertions) == 3
    assert trace.assertions[0].traced_assertion_pop_jump.lineno == 16
    assert trace.assertions[1].traced_assertion_pop_jump.lineno == 17
    assert trace.assertions[2].traced_assertion_pop_jump.lineno == 18


def test_loop_assertions():
    trace = _get_assertion_trace_for_module("tests.fixtures.assertion.loop")

    assert len(trace.assertions) == 5
    for assertion in trace.assertions:
        assert assertion.traced_assertion_pop_jump.lineno == 13


def test_assertion_detection_of_generated_tests():
    module_name = "tests.fixtures.linecoverage.plus"
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = get_plus_test_with_assertions()

        executor.execute(chromosome.test_case, instrument_test=True)
        assertion_trace = tracer.get_trace().assertion_trace
        assert len(assertion_trace.assertions) == 1


def _get_assertion_trace_for_module(module_name: str) -> AssertionData:
    """Trace a given module name with the CheckedCoverage Instrumentation.
    The traced module must contain a test called test_foo()."""
    module = importlib.import_module(module_name)
    module = importlib.reload(module)

    # Setup
    tracer = ExecutionTracer()
    adapter = CheckedCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])

    # Instrument and call module
    module.test_foo.__code__ = transformer.instrument_module(module.test_foo.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    module.test_foo()

    return tracer.get_trace().assertion_trace
