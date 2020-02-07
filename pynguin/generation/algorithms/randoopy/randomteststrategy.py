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
"""Provides a random test generation algorithm similar to Randoop."""
import datetime
import inspect
import logging
import random
from typing import Type, List, Tuple, Any, Callable

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.configuration as config
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.generation.symboltable import SymbolTable
from pynguin.typeinference.strategy import TypeInferenceStrategy, InferredSignature
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.recorder import CoverageRecorder

# pylint: disable=too-few-public-methods
from pynguin.utils.utils import get_members_from_module


class RandomTestStrategy(TestGenerationStrategy):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        recorder: CoverageRecorder,
        executor: TestCaseExecutor,
        symbol_table: SymbolTable,
        type_inference_strategy: TypeInferenceStrategy,
    ) -> None:
        super().__init__()
        self._recorder = recorder
        self._executor = executor
        self._symbol_table = symbol_table
        self._type_inference_strategy = type_inference_strategy

    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[tc.TestCase], List[tc.TestCase]]:
        self._logger.info("Start generating sequences using random algorithm")
        self._logger.debug("Time limit: %d", time_limit)
        self._logger.debug("Modules: %s", modules)

        test_cases: List[tc.TestCase] = []
        failing_test_cases: List[tc.TestCase] = []
        start_time = datetime.datetime.now()
        execution_counter: int = 0

        objects_under_test = self._find_objects_under_test(modules)

        while (datetime.datetime.now() - start_time).total_seconds() < time_limit:
            try:
                execution_counter += 1
                self._generate_sequence(
                    test_cases, failing_test_cases, objects_under_test,
                )
            except GenerationException as exception:
                self._logger.debug(
                    "Generate test case failed with exception %s", exception
                )

        self._logger.info("Finish generating sequences with random algorithm")
        self._logger.debug("Generated %d passing test cases", len(test_cases))
        self._logger.debug("Generated %d failing test cases", len(failing_test_cases))
        self._logger.debug("Number of algorithm iterations: %d", execution_counter)

        return test_cases, failing_test_cases

    def _generate_sequence(
        self,
        test_cases: List[tc.TestCase],
        failing_test_cases: List[tc.TestCase],
        objects_under_test: List[Type],
    ) -> None:
        """Implements one step of the adapted Randoop algorithm.

        :param test_cases: The list of currently successful test cases
        :param failing_test_cases: The list of currently not successful test cases
        :param objects_under_test: The list of available types in the current context
        """
        # Create new test case, i.e., sequence in Randoop paper terminology
        method = self._random_public_method(objects_under_test)
        method_type = self._type_inference_strategy.infer_type_info(method)
        tests = self._random_test_cases(test_cases)
        values = self._random_values(
            test_cases, method, method_type, failing_test_cases
        )
        new_test_case = self._extend(method, tests, values, method_type)

        # Discard duplicates
        if new_test_case in test_cases or new_test_case in failing_test_cases:
            return

        # Execute new sequence
        # TODO(sl) what shall be the return values of the execution step?
        # TODO(sl) think about the contracts from Randoop paper…
        exec_result = self._executor.execute(new_test_case)

        # Classify new test case and outputs
        if exec_result.has_test_exceptions():
            failing_test_cases.append(new_test_case)
        else:
            test_cases.append(new_test_case)
            # TODO(sl) what about extensible flags?

    @staticmethod
    def _find_objects_under_test(types: List[Type]) -> List[Type]:
        objects_under_test = types.copy()
        for module in types:
            members = get_members_from_module(module)
            # members is tuple (name, module/class/function/method)
            objects_under_test = objects_under_test + [x[1] for x in members]
        return objects_under_test

    def _random_public_method(self, objects_under_test: List[Type]) -> Callable:
        def inspect_member(member):
            try:
                return (
                    inspect.isclass(member)
                    or inspect.ismethod(member)
                    or inspect.isfunction(member)
                )
            except BaseException as exception:
                self._logger.debug(exception)
                raise GenerationException("Test member: " + exception.__repr__())

        object_under_test = random.choice(objects_under_test)
        members = inspect.getmembers(object_under_test, inspect_member)

        public_members = [
            m[1]
            for m in members
            if not m[0][0] == "_" and not m[1].__name__ == "_recording_isinstance"
        ]

        if not public_members:
            raise GenerationException(
                object_under_test.__name__ + " has no public callables."
            )

        method = random.choice(public_members)
        return method

    def _random_test_cases(self, test_cases: List[tc.TestCase]) -> List[tc.TestCase]:
        if config.INSTANCE.max_sequence_length == 0:
            selectables = test_cases
        else:
            selectables = [
                test_case
                for test_case in test_cases
                if len(test_case.statements) < config.INSTANCE.max_sequence_length
            ]
        if config.INSTANCE.max_sequences_combined == 0:
            upper_bound = len(selectables)
        else:
            upper_bound = min(len(selectables), config.INSTANCE.max_sequences_combined)
        new_test_cases = random.sample(selectables, random.randint(0, upper_bound))
        self._logger.debug(
            "Selected %d new test cases from %d available ones",
            len(new_test_cases),
            len(test_cases),
        )
        return new_test_cases

    # pylint: disable=unused-argument
    def _random_values(
        self,
        test_cases: List[tc.TestCase],
        callable_: Callable,
        method_type: InferredSignature,
        failing_test_cases: List[tc.TestCase],
    ) -> List[Tuple[str, Type, Any]]:
        assert method_type.parameters  # TODO(sl) implement handling for other cases
        parameters = [(k, v) for k, v in method_type.parameters.items() if k != "self"]
        values: List[Tuple[str, Type, Any]] = []
        for parameter in parameters:
            name, param = parameter
            assert param  # TODO(sl) this should always be true when we have parameters
            value = 42
            self._logger.debug(
                "Selected Method: %s, Parameter: %s: %s, Value: %s",
                callable_.__name__,
                name,
                param,
                value,
            )
            values.append((name, param, value))
        return values

    def _extend(
        self,
        callable_: Callable,
        test_cases: List[tc.TestCase],
        values: List[Tuple[str, Type, Any]],
        method_type: InferredSignature,
    ) -> tc.TestCase:
        new_test = dtc.DefaultTestCase()
        for test_case in test_cases:
            new_test.append_test_case(test_case)

        statements: List[stmt.Statement] = []
        self._logger.debug(
            "Generated %d statements for method %s", len(statements), callable_.__name__
        )
        for statement in statements:
            self._logger.debug("    Statement %s", statement)
        new_test.add_statements(statements)
        return new_test
