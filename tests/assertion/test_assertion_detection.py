#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

import importlib.util
import threading
from typing import List

import pytest

import pynguin.configuration as config
from pynguin.instrumentation.instrumentation import (
    CheckedCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.testcase.execution import ExecutionTrace, ExecutionTracer


def test_single_assertion():
    """Problem assertion wird nicht getrackt, 'LOAD_ASSERTION_ERROR' instruction erst seit Python 3.9 """
    module_name = "tests.fixtures.assertion.basic"
    trace = _trace_call(module_name)

    assert trace.test_id == "basic.test_foo"
    assert len(trace.traced_assertions) == 1
    assert trace.traced_assertions[0].traced_assertion_call.lineno == 16


def test_multiple_assertions():
    module_name = "tests.fixtures.assertion.multiple"
    trace = _trace_call(module_name)

    assert len(trace.traced_assertions) == 3
    assert trace.traced_assertions[0].traced_assertion_call.lineno == 15
    assert trace.traced_assertions[1].traced_assertion_call.lineno == 16
    assert trace.traced_assertions[2].traced_assertion_call.lineno == 17


def test_loop_assertions():
    module_name = "tests.fixtures.assertion.loop"
    trace = _trace_call(module_name)

    assert len(trace.traced_assertions) == 5
    for assertion in trace.traced_assertions:
        assert assertion.traced_assertion_call.lineno == 24


def test_custom_assertion_specified():
    module_name = "tests.fixtures.assertion.custom"
    trace = _trace_call(module_name, custom_assertions=["assert_custom"])

    assert len(trace.traced_assertions) == 1


def test_custom_assertion_unspecified():
    module_name = "tests.fixtures.assertion.custom"
    trace = _trace_call(module_name)

    assert len(trace.traced_assertions) == 0


def _trace_call(module_name: str, custom_assertions: List = None) -> ExecutionTrace:
    module = importlib.import_module(module_name)
    module = importlib.reload(module)

    # Setup
    config.configuration.statistics_output.custom_assertions = custom_assertions
    tracer = ExecutionTracer()
    adapter = CheckedCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])

    # Instrument and call module
    module.test_foo.__code__ = transformer.instrument_module(module.test_foo.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    module.test_foo()

    return tracer.get_trace()
