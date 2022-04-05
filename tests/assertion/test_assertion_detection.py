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

from pynguin.instrumentation.instrumentation import (
    CheckedCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.testcase.execution import AssertionTrace, ExecutionTracer


def test_single_assertion():
    trace = _get_assertion_trace_for_module("tests.fixtures.assertion.basic")

    assert len(trace.traced_assertions) == 1
    assert trace.traced_assertions[0].traced_assertion_pop_jump.lineno == 16


def test_multiple_assertions():
    trace = _get_assertion_trace_for_module("tests.fixtures.assertion.multiple")

    assert len(trace.traced_assertions) == 3
    assert trace.traced_assertions[0].traced_assertion_pop_jump.lineno == 16
    assert trace.traced_assertions[1].traced_assertion_pop_jump.lineno == 17
    assert trace.traced_assertions[2].traced_assertion_pop_jump.lineno == 18


def test_loop_assertions():
    trace = _get_assertion_trace_for_module("tests.fixtures.assertion.loop")

    assert len(trace.traced_assertions) == 5
    for assertion in trace.traced_assertions:
        assert assertion.traced_assertion_pop_jump.lineno == 13


def _get_assertion_trace_for_module(module_name: str) -> AssertionTrace:
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
