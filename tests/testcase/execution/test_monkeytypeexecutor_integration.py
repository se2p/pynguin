#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest
from monkeytype.encoding import CallTraceRow
from monkeytype.tracing import CallTrace

import pynguin.configuration as config
from pynguin.testcase.execution.monkeytypeexecutor import (
    MonkeyTypeExecutor,
    _MonkeyTypeCallTraceLogger,
    _MonkeyTypeCallTraceStore,
    _MonkeyTypeConfig,
)


@pytest.fixture
def trace_store():
    return _MonkeyTypeCallTraceStore.make_store("")


@pytest.fixture
def trace(provide_callables_from_fixtures_modules):
    return CallTrace(
        func=provide_callables_from_fixtures_modules["triangle"],
        arg_types={"x": int, "y": int, "z": int},
        return_type=None,
        yield_type=None,
    )


def test_no_exceptions(short_test_case):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    executor = MonkeyTypeExecutor()
    result = executor.execute([short_test_case])
    assert len(result) == 1
    assert (
        result[0].funcname == "tests.fixtures.accessibles.accessible.SomeType.__init__"
    )
    assert result[0].arg_types["y"] == int


def test_store_list_modules(trace_store, trace):
    trace_store.add([trace])
    result = trace_store.list_modules()
    assert result == ["tests.fixtures.examples.triangle"]


def test_store_filter(trace_store, trace):
    trace_store.add([trace])
    expected = CallTraceRow(
        module="tests.fixtures.examples.triangle",
        qualname="triangle",
        arg_types='{"x": {"module": "builtins", "qualname": "int"}, '
        '"y": {"module": "builtins", "qualname": "int"}, '
        '"z": {"module": "builtins", "qualname": "int"}}',
        return_type=None,
        yield_type=None,
    )
    result = trace_store.filter("", "triangle")
    assert len(result) == 1
    assert expected.__eq__(result)


def test_store_filter_no_result(trace_store, trace):
    trace_store.add([trace])
    result = trace_store.filter("foobar")
    assert result == []


def test_logger(trace):
    logger = _MonkeyTypeCallTraceLogger()
    logger.log(trace)
    assert logger.traces == [trace]


def test_config():
    monkey_type_config = _MonkeyTypeConfig()
    tracer = monkey_type_config.trace_store()
    assert isinstance(tracer, _MonkeyTypeCallTraceStore)
