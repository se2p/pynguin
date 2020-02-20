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
"""An executor that executes a test under the inspection of the MonkeyType tool."""
import contextlib
import logging
import os
import sys
from typing import List, Optional, Iterable, Dict, Any

import astor
from monkeytype.config import DefaultConfig
from monkeytype.db.base import CallTraceStore, CallTraceThunk
from monkeytype.encoding import serialize_traces
from monkeytype.tracing import CallTraceLogger, CallTrace, CallTracer

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor


class _MonkeyTypeCallTraceStore(CallTraceStore):
    def __init__(self):
        self._values: Dict[str, Any] = {}

    def add(self, traces: Iterable[CallTrace]) -> None:
        for row in serialize_traces(traces):
            self._values[row.module] = (
                row.qualname,
                row.arg_types,
                row.return_type,
                row.yield_type,
            )

    def filter(
        self, module: str, qualname_prefix: Optional[str] = None, limit: int = 2000
    ) -> List[CallTraceThunk]:
        pass

    @classmethod
    def make_store(cls, connection_string: str) -> "CallTraceStore":
        return cls()

    def list_modules(self) -> List[str]:
        pass


class _MonkeyTypeCallTraceLogger(CallTraceLogger):
    def __init__(self) -> None:
        self._traces: List[CallTrace] = []

    def log(self, trace: CallTrace) -> None:
        self._traces.append(trace)

    @property
    def traces(self) -> List[CallTrace]:
        """Provides the collected traces"""
        return self._traces


class _MonkeyTypeConfig(DefaultConfig):
    def trace_store(self) -> CallTraceStore:
        return _MonkeyTypeCallTraceStore()

    def trace_logger(self) -> CallTraceLogger:
        return _MonkeyTypeCallTraceLogger()


class MonkeyTypeExecutor(AbstractExecutor):
    """An executor that executes a test under the inspection of the MonkeyType tool."""

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """"""
        super().__init__()
        self._config = _MonkeyTypeConfig()
        self._tracer = CallTracer(
            logger=self._config.trace_logger(),
            code_filter=self._config.code_filter(),
            sample_rate=self._config.sample_rate(),
        )
        self._call_traces: List[CallTrace] = []

    def execute(self, test_case: tc.TestCase) -> List[CallTrace]:
        self.setup(test_case)
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                self._execute_ast_nodes()
        self._filter_and_append_call_traces()
        return self._call_traces

    def execute_test_suite(self, test_suite: List[tc.TestCase]) -> List[CallTrace]:
        pass

    def _execute_ast_nodes(self):
        for node in self._ast_nodes:
            self._logger.debug("Executing %s", astor.to_source(node))
            code = compile(self.wrap_node_in_module(node), "<ast>", "exec")
            # pylint: disable=exec-used
            sys.setprofile(self._tracer)
            exec(code, self._global_namespace, self._local_namespace)
            sys.setprofile(None)

    def _filter_and_append_call_traces(self) -> None:
        assert isinstance(self._tracer.logger, _MonkeyTypeCallTraceLogger)
        module_name = config.INSTANCE.module_name
        for trace in self._tracer.logger.traces:
            func_name = trace.funcname
            if func_name.startswith(module_name):
                self._call_traces.append(trace)
