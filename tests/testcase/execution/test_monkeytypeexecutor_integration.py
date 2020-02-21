# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
import pytest
from monkeytype.encoding import CallTraceRow
from monkeytype.tracing import CallTrace

import pynguin.configuration as config
from pynguin.testcase.execution.monkeytypeexecutor import (
    MonkeyTypeExecutor,
    _MonkeyTypeCallTraceStore,
    _MonkeyTypeCallTraceLogger,
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
    result = executor.execute(short_test_case)
    assert len(result) == 1
    assert (
        result[0].funcname == "tests.fixtures.accessibles.accessible.SomeType.__init__"
    )
    assert result[0].arg_types["y"] == int


def test_no_exceptions_test_suite(short_test_case):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    executor = MonkeyTypeExecutor()
    result = executor.execute_test_suite([short_test_case])
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
