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
from typing import Callable, List, Optional, Tuple, Union

import monkeytype.typing as mtt
from monkeytype.tracing import CallTrace

import pynguin.testcase.testcase as tc
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.monkeytypeexecutor import MonkeyTypeExecutor
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.statistics.timer import Timer


# pylint: disable=too-few-public-methods
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
        self, test_cases: List[tc.TestCase], test_cluster: TestCluster
    ) -> None:
        """Handles a list of test cases, i.e., executes them and propagates the results
        back.

        The test cases will be executed while MonkeyType is tracking all calls.
        Afterwards, the results, i.e., the tracked types for calls, are collected
        from the execution and the present type information gets updated accordingly.
        See the documentation of the `MonkeyTypeExecutor` for details.

        Currently, the update does only a simple `Union` of the existing and the
        newly inferred types.  See the documentation of `typing.Union` for details on
        how these `Union`s are handled.

        Args:
            test_cases: The test cases to execute
            test_cluster: The underlying test cluster
        """
        with Timer(name="MonkeyType execution", logger=None):
            results = self._monkey_type_executor.execute(test_cases)
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
            self._update_parameter_types(call_trace, signature)
            self._update_return_types(call_trace, signature)

    def _update_parameter_types(
        self, call_trace: CallTrace, signature: InferredSignature
    ) -> None:
        arg_types = call_trace.arg_types
        for name, type_ in signature.parameters.items():
            if name not in arg_types:
                continue
            current_type = self._rewrite_type(type_)
            inferred_type = self._rewrite_type(arg_types[name])
            if self._check_for_none(inferred_type):
                continue
            if self._check_for_none(current_type):
                new_type = inferred_type
            else:
                new_type = self._rewrite_type(Union[current_type, inferred_type])  # type: ignore
            if str(new_type) != str(current_type):
                self._logger.debug(
                    "Update type information for %s: parameter %s, old type %s, "
                    "new type %s",
                    call_trace.funcname,
                    name,
                    str(type_),
                    str(new_type),
                )
                signature.update_parameter_type(name, new_type)
                self._parameter_updates.append(
                    (call_trace.funcname, name, type_, new_type)
                )

    def _update_return_types(
        self, call_trace: CallTrace, signature: InferredSignature
    ) -> None:
        current_return_type = self._rewrite_type(signature.return_type)
        inferred_return_type = self._rewrite_type(call_trace.return_type)
        if self._check_for_none(inferred_return_type):
            return
        return_type_name = (
            inferred_return_type.__name__
            if inferred_return_type is not None
            and hasattr(inferred_return_type, "__name__")
            else str(inferred_return_type)
        )
        if mtt.DUMMY_TYPED_DICT_NAME in return_type_name:
            new_return_type = current_return_type
        elif self._check_for_none(current_return_type):
            new_return_type = inferred_return_type
        else:
            new_return_type = self._rewrite_type(
                Union[current_return_type, inferred_return_type]  # type: ignore
            )
        if isinstance(new_return_type, type(None)):
            new_return_type = None
        if str(new_return_type) != str(current_return_type):
            self._logger.debug(
                "Update type information for %s: return type, old type "
                "%s, new type %s",
                call_trace.funcname,
                str(current_return_type),
                str(new_return_type),
            )
            signature.update_return_type(new_return_type)
            self._return_type_updates.append(
                (call_trace.funcname, current_return_type, new_return_type)
            )

    @staticmethod
    def _rewrite_type(type_: Optional[type]) -> Optional[type]:
        return mtt.DEFAULT_REWRITER.rewrite(type_)

    @staticmethod
    def _check_for_none(type_: Optional[type]) -> bool:
        return (
            type_ is None
            or isinstance(type_, type(None))
            or type_ == type(None)  # noqa
        )

    def _full_name(self, callable_: Callable) -> str:
        if not hasattr(callable_, "__module__"):
            self._logger.debug(
                "Cannot find module for callable %s", callable_.__qualname__
            )
            return f"{callable.__qualname__}"
        assert hasattr(callable_, "__module__")
        return f"{callable_.__module__}.{callable_.__qualname__}"
