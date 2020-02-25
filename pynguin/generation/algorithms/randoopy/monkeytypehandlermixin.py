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
from typing import List, Callable, Union

from monkeytype.tracing import CallTrace

import pynguin.testcase.testcase as tc
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.monkeytypeexecutor import MonkeyTypeExecutor
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)


class MonkeyTypeHandlerMixin:
    """A mixin handling the execution of a test case with MonkeyType."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._monkey_type_executor = MonkeyTypeExecutor()

    def handle_test_case(
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
        results = self._monkey_type_executor.execute(test_case)
        for result in results:
            self._update_type_inference(result, test_cluster)

    def handle_test_suite(
        self, test_suite: List[tc.TestCase], test_cluster: TestCluster
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
        results = self._monkey_type_executor.execute_test_suite(test_suite)
        for result in results:
            self._update_type_inference(result, test_cluster)

    def _update_type_inference(self, call_trace: CallTrace, test_cluster: TestCluster):
        objects_under_test = {
            self._full_name(out.callable): out
            for out in test_cluster.accessible_objects_under_test
            if isinstance(out, GenericCallableAccessibleObject)
        }
        if call_trace.funcname in objects_under_test:
            self._logger.debug("Update type information for %s", call_trace.funcname)
            object_under_test: GenericCallableAccessibleObject = objects_under_test[
                call_trace.funcname
            ]
            signature = object_under_test.inferred_signature
            arg_types = call_trace.arg_types
            for name, type_ in signature.parameters.items():
                if name in arg_types:
                    new_type = Union[type_, arg_types[name]]  # type: ignore
                    signature.update_parameter_type(name, new_type)  # type: ignore
            return_type = call_trace.return_type
            new_return_type = Union[signature.return_type, return_type]  # type: ignore
            signature.update_return_type(new_return_type)  # type: ignore

    @staticmethod
    def _full_name(callable_: Callable) -> str:
        assert hasattr(callable_, "__module__")
        return f"{callable_.__module__}.{callable_.__qualname__}"
