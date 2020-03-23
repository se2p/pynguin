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
"""A mixin handling the execution of a test case with MonkeyType."""
import logging
from typing import List, Callable, Union, Tuple, Optional, Type

from monkeytype.tracing import CallTrace

import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.monkeytypeexecutor import MonkeyTypeExecutor
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.statistics.timer import Timer


class MonkeyTypeHandlerMixin:
    """A mixin handling the execution of a test case with MonkeyType."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._monkey_type_executor = MonkeyTypeExecutor()
        self._monkey_type_executions = 0
        self._parameter_updates: List[
            Tuple[str, str, Optional[type], Optional[type]]
        ] = []
        self._return_type_updates: List[Tuple[str, Optional[type], Optional[type]]] = []

    def execute_test_case_monkey_type(
        self, test_case: tc.TestCase, test_cluster: TestCluster
    ) -> None:
        """Handles a test case, i.e., executes it and propagates the results back.

        The test case will be executed while MonkeyType is tracking all calls.
        Afterwards, the results, i.e., the tracked types for calls, are collected
        from the execution and the present type information gets updated accordingly.
        See the documentation of the `MonkeyTypeExecutor` for details.

        Currently, the update does only a simple `Union` of the existing and the
        newly inferred types.  See the documentation of `typing.Union` for details on
        how these `Union`s are handled.

        :param test_case: The test case to execute
        :param test_cluster: The underlying test cluster
        """
        with Timer(name="MonkeyType execution", logger=None):
            results = self._monkey_type_executor.execute(test_case)
            self._monkey_type_executions += 1
            for result in results:
                self._update_type_inference(result, test_cluster)

    def execute_test_suite_monkey_type(
        self, test_suite: tsc.TestSuiteChromosome, test_cluster: TestCluster
    ) -> None:
        """Handles a test suite, i.e., executes it and propagates the results back.

        Each test case will be executed while MonkeyType is tracking all calls.
        Afterwards, the results, i.e., the tracked types for calls, are collected
        from the execution and the present type information gets updated accordingly.
        See the documentation of the `MonkeyTypeExecutor` for details.

        Currently, the update does only a simple `Union` of the existing and the
        newly inferred types.  See the documentation of `typing.Union` for details on
        how these `Union`s are handled.

        :param test_suite: The test suite to execute
        :param test_cluster: The underlying test cluster
        """
        with Timer(name="MonkeyType execution", logger=None):
            results = self._monkey_type_executor.execute_test_suite(test_suite)
            self._monkey_type_executions += 1
            for result in results:
                self._update_type_inference(result, test_cluster)

    def _update_type_inference(self, call_trace: CallTrace, test_cluster: TestCluster):
        objects_under_test = {
            self._full_name(out.callable): out
            for out in test_cluster.accessible_objects_under_test
            if isinstance(out, GenericCallableAccessibleObject)
        }
        if call_trace.funcname in objects_under_test:
            object_under_test: GenericCallableAccessibleObject = objects_under_test[
                call_trace.funcname
            ]
            signature = object_under_test.inferred_signature
            arg_types = call_trace.arg_types
            for name, type_ in signature.parameters.items():
                if name in arg_types:
                    new_type: Type[...] = Union[type_, arg_types[name]]  # type: ignore
                    if new_type != arg_types[name]:
                        if isinstance(type_, type(None)) or type_ is None:
                            new_type = arg_types[name]
                        self._logger.debug(
                            "Update type information for %s: parameter %s, old type "
                            "%s, new type %s",
                            call_trace.funcname,
                            name,
                            str(type_),
                            str(new_type),
                        )
                        signature.update_parameter_type(name, new_type)
                        self._parameter_updates.append(
                            (call_trace.funcname, name, type_, new_type)
                        )
            return_type = call_trace.return_type
            new_return_type: Type[...] = Union[  # type: ignore
                signature.return_type, return_type
            ]
            if new_return_type != return_type:
                if (
                    isinstance(signature.return_type, type(None))
                    or signature.return_type is None
                ):
                    new_return_type = return_type  # type: ignore
                self._logger.debug(
                    "Update type information for %s: return type, old type "
                    "%s, new type %s",
                    call_trace.funcname,
                    str(return_type),
                    str(new_return_type),
                )
                signature.update_return_type(new_return_type)
                self._return_type_updates.append(
                    (call_trace.funcname, return_type, new_return_type)
                )

    def _full_name(self, callable_: Callable) -> str:
        if not hasattr(callable_, "__module__"):
            self._logger.debug(
                "Cannot find module for callable %s", callable_.__qualname__
            )
            return f"{callable.__qualname__}"
        assert hasattr(callable_, "__module__")
        return f"{callable_.__module__}.{callable_.__qualname__}"
