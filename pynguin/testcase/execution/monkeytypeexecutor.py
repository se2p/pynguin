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
from typing import Any, Dict, Iterable, List, Optional

import astor
from monkeytype.config import DefaultConfig
from monkeytype.db.base import CallTraceStore, CallTraceThunk
from monkeytype.encoding import CallTraceRow, serialize_traces
from monkeytype.tracing import CallTrace, CallTraceLogger, CallTracer

import pynguin.configuration as config
import pynguin.testcase.execution.executioncontext as ctx
import pynguin.testcase.testcase as tc


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
        result: List[CallTraceThunk] = []
        for stored_module, row in self._values.items():
            is_qualname = qualname_prefix is not None and qualname_prefix in row[0]
            if stored_module == module or is_qualname:
                result.append(
                    CallTraceRow(
                        module=module,
                        qualname=row[0],
                        arg_types=row[1],
                        return_type=row[2],
                        yield_type=row[3],
                    )
                )
        return result if len(result) < limit else result[:limit]

    @classmethod
    def make_store(cls, connection_string: str) -> "CallTraceStore":
        return cls()

    def list_modules(self) -> List[str]:
        return [k for k, _ in self._values.items()]


class _MonkeyTypeCallTraceLogger(CallTraceLogger):
    def __init__(self) -> None:
        self._traces: List[CallTrace] = []

    def log(self, trace: CallTrace) -> None:
        self._traces.append(trace)

    @property
    def traces(self) -> List[CallTrace]:
        """Provides the collected traces

        Returns:
            The list of collected traces
        """
        return self._traces


class _MonkeyTypeConfig(DefaultConfig):
    def trace_store(self) -> CallTraceStore:
        return _MonkeyTypeCallTraceStore()

    def trace_logger(self) -> CallTraceLogger:
        return _MonkeyTypeCallTraceLogger()


# pylint:disable=too-few-public-methods
class MonkeyTypeExecutor:
    """An executor that executes a test under the inspection of the MonkeyType tool."""

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """"""
        self._config = _MonkeyTypeConfig()
        self._tracer = CallTracer(
            logger=self._config.trace_logger(),
            max_typed_dict_size=1_000_000,
            code_filter=self._config.code_filter(),
            sample_rate=self._config.sample_rate(),
        )
        self._call_traces: List[CallTrace] = []

    def execute(self, test_cases: List[tc.TestCase]) -> List[CallTrace]:
        """Execute the given test cases.

        Args:
            test_cases: A list of test cases to execute

        Returns:
            A list of call traces of the results
        """
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for test_case in test_cases:
                    exec_ctx = ctx.ExecutionContext(test_case)
                    self._execute_ast_nodes(exec_ctx)
        self._filter_and_append_call_traces()
        return self._call_traces

    def _execute_ast_nodes(self, exec_ctx: ctx.ExecutionContext):
        for node in exec_ctx.executable_nodes():
            try:
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug("Executing %s", astor.to_source(node))
                code = compile(node, "<ast>", "exec")
                sys.setprofile(self._tracer)
                # pylint: disable=exec-used
                exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
            except BaseException as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                self._logger.info(
                    "Fatal! Failed to execute statement with MonkeyType\n%s%s",
                    failed_stmt,
                    err.args,
                )
                break
            finally:
                sys.setprofile(None)

    def _filter_and_append_call_traces(self) -> None:
        assert isinstance(self._tracer.logger, _MonkeyTypeCallTraceLogger)
        module_name = config.INSTANCE.module_name
        for trace in self._tracer.logger.traces:
            func_name = trace.funcname
            if func_name.startswith(module_name):
                self._call_traces.append(trace)
