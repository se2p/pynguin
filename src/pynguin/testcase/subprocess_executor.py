#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""TestCaseExecutor that runs test cases in a subprocess."""

from __future__ import annotations

import dataclasses
import enum
import itertools
import logging
import signal
import sys
from typing import TYPE_CHECKING, Any

import dill  # noqa: S403
import multiprocess as mp
import multiprocess.connection as mp_conn

import pynguin.assertion.assertion as ass
import pynguin.utils.execution_recorder as ter
from pynguin.instrumentation.machinery import InstrumentationFinder
from pynguin.testcase.crash_minimization import minimize_and_safe
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.execution_isolation import PatchRandomOnUnpickle
from pynguin.testcase.execution_result import ExecutionResult
from pynguin.utils import randomness
from pynguin.utils.statistics import stats as stat
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable

    import pynguin.assertion.assertion_trace as at
    import pynguin.testcase.testcase as tc
    import pynguin.utils.typetracing as tt
    from pynguin.analyses.typesystem import ProperType
    from pynguin.instrumentation.tracer import ExecutedAssertion, ExecutionTracer, SubjectProperties
    from pynguin.testcase.execution import ModuleProvider
    from pynguin.testcase.execution_observers import RemoteExecutionObserver

_LOGGER = logging.getLogger(__name__)

SUPPORTED_EXIT_CODE_MESSAGES = {}

if hasattr(signal, "SIGILL"):
    SUPPORTED_EXIT_CODE_MESSAGES[-signal.SIGILL] = "Illegal instruction signal detected"

if hasattr(signal, "SIGABRT"):
    SUPPORTED_EXIT_CODE_MESSAGES[-signal.SIGABRT] = "Abort signal detected"

if hasattr(signal, "SIGBUS"):
    SUPPORTED_EXIT_CODE_MESSAGES[-signal.SIGBUS] = "Bus error signal detected"

if hasattr(signal, "SIGFPE"):
    SUPPORTED_EXIT_CODE_MESSAGES[-signal.SIGFPE] = "Floating-point exception signal detected"

if hasattr(signal, "SIGKILL"):
    SUPPORTED_EXIT_CODE_MESSAGES[-signal.SIGKILL] = (
        "Kill signal detected, most likely due to an out of memory"
    )

if hasattr(signal, "SIGSEGV"):
    SUPPORTED_EXIT_CODE_MESSAGES[-signal.SIGSEGV] = "Segmentation fault detected"


class SubprocessTestCaseExecutor(TestCaseExecutor):
    """An executor that executes the generated test cases in a subprocess."""

    class ConnectionStatus(enum.Enum):
        """Status of the connection to the subprocess."""

        HAS_RESULTS = enum.auto()
        NO_RESULTS = enum.auto()

    @dataclasses.dataclass
    class SubprocessResultContext:
        """Context for processing subprocess results."""

        test_cases_tuple: tuple[tc.TestCase, ...]
        references_bindings: tuple[dict[int, str], ...]
        process: mp.Process
        receiving_connection: mp_conn.Connection
        connection_status: SubprocessTestCaseExecutor.ConnectionStatus
        remote_observers: tuple[RemoteExecutionObserver, ...]

    def __init__(
        self,
        subject_properties: SubjectProperties,
        module_provider: ModuleProvider | None = None,
        maximum_test_execution_timeout: int = 5,
        test_execution_time_per_statement: int = 1,
    ) -> None:
        """Create new subprocess test case executor.

        Args:
            subject_properties: The subject properties
            module_provider: The used module provider
            maximum_test_execution_timeout: The minimum timeout time (in seconds)
                before a test case execution times out.
            test_execution_time_per_statement: The amount of time (in seconds) that is
                added to the timeout per statement, up to minimum_test_execution_timeout
        """
        super().__init__(
            subject_properties,
            module_provider,
            maximum_test_execution_timeout,
            test_execution_time_per_statement,
        )

    def execute(  # noqa: D102
        self,
        test_case: tc.TestCase,
    ) -> ExecutionResult:
        return next(iter(self.execute_multiple((test_case,))))

    def execute_with_exit_code(
        self,
        test_case: tc.TestCase,
    ) -> int | None:
        """Execute a test case in a subprocess and return the exit code.

        This method executes a single test case in a separate subprocess and returns
        the exit code of the subprocess. If the subprocess crashes or times out,
        it returns None or a non-zero exit code.

        Args:
            test_case: The test case to execute

        Returns:
            The exit code of the subprocess. A None or non-zero exit code indicates a
            crash.
        """
        self._before_remote_test_case_execution(test_case)

        with ter.ExecutionRecorder(test_case):
            process, receiving_connection = self._setup_subprocess_execution(
                (test_case,),
                (self._create_variable_binding(test_case),),
            )

            # Calculate timeout based on test case size
            timeout = self._calculate_timeout(test_case)

            # We need to use `poll` here because `recv` cannot take a timeout argument and
            # `join` does not return until the pipe is closed in both processes.
            has_results = receiving_connection.poll(timeout=timeout)

            if has_results:
                try:
                    with self._subject_properties.instrumentation_tracer.temporarily_disable():
                        receiving_connection.recv()
                except (EOFError, OSError):
                    _LOGGER.error("Error during receiving results from subprocess")

                receiving_connection.close()

                process.join(timeout=self._maximum_test_execution_timeout)

                if process.exitcode is None:
                    process.kill()
                    return None
            elif test_case.size() == 0:
                return 0
            else:
                receiving_connection.close()

                if process.exitcode is None:
                    process.kill()
                    return None

            return process.exitcode or 0

    def _calculate_timeout(self, test_case: tc.TestCase) -> float:
        """Calculate timeout for a test case based on its size.

        Args:
            test_case: The test case

        Returns:
            The calculated timeout in seconds
        """
        return min(
            self._maximum_test_execution_timeout,
            self._test_execution_time_per_statement * test_case.size(),
        )

    def _calculate_timeout_for_multiple(self, test_cases: tuple[tc.TestCase, ...]) -> float:
        """Calculate timeout for multiple test cases based on their sizes.

        Args:
            test_cases: The test cases

        Returns:
            The calculated timeout in seconds
        """
        return min(
            self._maximum_test_execution_timeout * len(test_cases),
            sum(
                self._test_execution_time_per_statement * test_case.size()
                for test_case in test_cases
            ),
        )

    def execute_multiple(  # noqa: D102
        self, test_cases: Iterable[tc.TestCase]
    ) -> Iterable[ExecutionResult]:
        test_cases_tuple = tuple(test_cases)

        if not test_cases_tuple:
            return ()

        self._executed_test_cases += len(test_cases_tuple)
        stat.track_output_variable(RuntimeVariable.Executed, self._executed_test_cases)

        for test_case in test_cases_tuple:
            self._before_remote_test_case_execution(test_case)

        references_bindings = tuple(
            self._create_variable_binding(test_case) for test_case in test_cases_tuple
        )

        process, receiving_connection = self._setup_subprocess_execution(
            test_cases_tuple,
            references_bindings,
        )

        # We need to use `poll` here because `recv` cannot take a timeout argument and
        # `join` does not return until the pipe is closed in both processes.
        has_results = receiving_connection.poll(
            timeout=self._calculate_timeout_for_multiple(test_cases_tuple),
        )

        remote_observers = tuple(self._yield_remote_observers())
        connection_status = (
            self.ConnectionStatus.HAS_RESULTS if has_results else self.ConnectionStatus.NO_RESULTS
        )
        context = self.SubprocessResultContext(
            test_cases_tuple=test_cases_tuple,
            references_bindings=references_bindings,
            process=process,
            receiving_connection=receiving_connection,
            connection_status=connection_status,
            remote_observers=remote_observers,
        )
        results = self._process_subprocess_results(context)

        for test_case, result in zip(test_cases_tuple, results, strict=True):
            self._after_remote_test_case_execution(test_case, result)

        return results

    def _setup_subprocess_execution(
        self,
        test_cases_tuple: tuple[tc.TestCase, ...],
        references_bindings: tuple[dict[int, str], ...],
    ) -> tuple[mp.Process, mp_conn.Connection]:
        """Set up subprocess execution for test cases.

        Args:
            test_cases_tuple: The test cases to execute
            references_bindings: The variable bindings for each test case

        Returns:
            A tuple containing the process and the receiving connection
        """
        receiving_connection, sending_connection = mp.Pipe(duplex=False)

        remote_observers = tuple(self._yield_remote_observers())

        args = (
            PatchRandomOnUnpickle(),
            self._subject_properties,
            self._module_provider,
            self._maximum_test_execution_timeout,
            self._test_execution_time_per_statement,
            remote_observers,
            test_cases_tuple,
            references_bindings,
            sending_connection,
        )

        process = mp.Process(
            target=self._execute_test_cases_in_subprocess,
            args=args,
            daemon=True,
        )

        process.start()

        sending_connection.close()

        return process, receiving_connection

    def _process_subprocess_results(
        self,
        context: SubprocessResultContext,
    ) -> tuple[ExecutionResult, ...]:
        """Process the results from subprocess execution.

        Args:
            context: The context containing all necessary information for processing

        Returns:
            The execution results
        """
        results: tuple[ExecutionResult, ...]
        if context.connection_status == self.ConnectionStatus.NO_RESULTS:
            context.receiving_connection.close()
            results = self._fallback_on_failure(
                context.test_cases_tuple, context.process, context.remote_observers
            )
        else:
            try:
                with self._subject_properties.instrumentation_tracer.temporarily_disable():
                    return_value: tuple[
                        ExecutionTracer,
                        ModuleProvider,
                        tuple[ExecutionResult, ...],
                        tuple[dict[int, str] | None, ...],
                        tuple[Any, ...],
                    ] = context.receiving_connection.recv()
            except (EOFError, OSError):
                _LOGGER.error("Error during receiving results from subprocess")
                context.receiving_connection.close()
                results = self._fallback_on_failure(
                    context.test_cases_tuple, context.process, context.remote_observers
                )
            else:
                (
                    new_tracer,
                    new_module_provider,
                    results,
                    new_references_bindings,
                    random_state,
                ) = return_value

                context.receiving_connection.close()

                context.process.join(timeout=self._maximum_test_execution_timeout)

                if context.process.exitcode is None:
                    context.process.kill()

                randomness.RNG.setstate(random_state)

                self._module_provider = new_module_provider

                for result, reference_bindings, new_reference_bindings in zip(
                    results, context.references_bindings, new_references_bindings, strict=True
                ):
                    if new_reference_bindings is not None:
                        self._fix_assertion_trace(
                            result.assertion_trace, reference_bindings, new_reference_bindings
                        )

                self._subject_properties.instrumentation_tracer.tracer.state = new_tracer.state

        return results

    def _fallback_on_failure(
        self,
        test_cases_tuple: tuple[tc.TestCase, ...],
        process: mp.Process,
        remote_observers: tuple[RemoteExecutionObserver, ...],
    ) -> tuple[ExecutionResult, ...]:
        if len(test_cases_tuple) == 1:
            if process.exitcode is None:
                process.kill()
                _LOGGER.warning("Experienced timeout from test-case execution")
            elif process.exitcode in SUPPORTED_EXIT_CODE_MESSAGES:
                _LOGGER.warning(
                    "%s. Saving the test-case that caused the crash and continuing as"
                    " if a timeout occurred.",
                    SUPPORTED_EXIT_CODE_MESSAGES[process.exitcode],
                )
                self._minimize_and_safe(test_cases_tuple[0], process.exitcode)
            else:
                _LOGGER.error(
                    "Finished process exited with code %s and did not return a result.",
                    process.exitcode,
                )
                _LOGGER.error("Bug in Pynguin!")

            return (ExecutionResult(timeout=True),)
        if process.exitcode is None:
            process.kill()
            _LOGGER.warning(
                "Timeout occurred. Falling back to executing each test-case in a separate process."
            )
        elif process.exitcode in SUPPORTED_EXIT_CODE_MESSAGES:
            _LOGGER.warning(
                "%s. Falling back to executing each test-case in a separate process.",
                SUPPORTED_EXIT_CODE_MESSAGES[process.exitcode],
            )
        else:
            _LOGGER.error(
                "Finished process exited with code %s and did not return the results.",
                process.exitcode,
            )
            _LOGGER.error("Bug in Pynguin!")

        # Fallback to executing each test-case in separate subprocesses
        # if the execution of multiple test-cases in a single subprocess failed.
        # We need to use another executor because we already called
        # `_before_remote_test_case_execution` so we only need to run the
        # remote observers.
        executor = SubprocessTestCaseExecutor(
            self._subject_properties,
            self._module_provider,
            self._maximum_test_execution_timeout,
            self._test_execution_time_per_statement,
        )

        for remote_observer in remote_observers:
            executor.add_remote_observer(remote_observer)

        return tuple(executor.execute(test_case) for test_case in test_cases_tuple)

    def _minimize_and_safe(self, test_case: tc.TestCase, exit_code: int | None) -> None:
        minimize_and_safe(self, test_case, exit_code)

    @staticmethod
    def _create_variable_binding(
        test_case: tc.TestCase,
    ) -> dict[int, str]:
        """Create binding between statement positions and variable references.

        This is important because the `Assertion`s added to the `AssertionTrace` use
        `Reference`s to indicate on which line they should be used. This causes a
        problem because when data is returned from the subprocess to the main process,
        it creates new references and so we need a way to link the old references to
        the new ones.

        Args:
            test_case: The test case
        """
        _LOGGER.debug("Creating variable bindings for test case of size %d", test_case.size())
        # In the libcst representation variables are referenced by name; bind each
        # statement position to the name of the variable it binds (if any).
        return {
            position: statement.bound_variable
            for position, statement in enumerate(test_case.statements())
            if statement.bound_variable is not None
        }

    @staticmethod
    def _fix_assertion_trace(
        assertion_trace: at.AssertionTrace,
        old_reference_bindings: dict[int, str],
        new_reference_bindings: dict[int, str],
    ) -> None:
        """Fix the assertion trace after the test case execution.

        See the docstring of `_create_variable_binding` for more information.

        Args:
            assertion_trace: The assertion trace
            old_reference_bindings: The old reference bindings
            new_reference_bindings: The new reference bindings
        """
        memo = {
            new_reference: old_reference_bindings[position]
            for position, new_reference in new_reference_bindings.items()
        }

        all_assertions = assertion_trace.get_all_assertions()
        assertion_trace.clear()
        for position, assertions in all_assertions.items():
            for assertion in assertions:
                assertion_trace.add_entry(position, assertion.clone(memo))

    @staticmethod
    def _execute_test_cases_in_subprocess(  # noqa: PLR0917
        _patch_random_hook: object,
        subject_properties: SubjectProperties,
        module_provider: ModuleProvider,
        maximum_test_execution_timeout: int,
        test_execution_time_per_statement: int,
        remote_observers: tuple[RemoteExecutionObserver, ...],
        test_cases: tuple[tc.TestCase, ...],
        references_bindings: tuple[dict[int, str], ...],
        sending_connection: mp_conn.Connection,
    ) -> None:
        try:
            SubprocessTestCaseExecutor._replace_tracer(
                subject_properties.instrumentation_tracer.tracer
            )

            executor = TestCaseExecutor(
                subject_properties,
                module_provider,
                maximum_test_execution_timeout,
                test_execution_time_per_statement,
            )

            for remote_observer in remote_observers:
                executor.add_remote_observer(remote_observer)

            results = tuple(executor.execute_multiple(test_cases))

            # We need to activate the tracer because pickle can execute code of the
            # instrumented module and it would kill the subprocess which is not what we want.
            with subject_properties.instrumentation_tracer:
                for result in results:
                    SubprocessTestCaseExecutor._fix_result_for_pickle(result)

                new_references_bindings = tuple(
                    SubprocessTestCaseExecutor._create_new_reference_bindings(  # noqa: FURB140
                        result,
                        reference_bindings,
                    )
                    for result, reference_bindings in zip(results, references_bindings, strict=True)
                )

                sending_connection.send((
                    subject_properties.instrumentation_tracer.tracer,
                    module_provider,
                    results,
                    new_references_bindings,
                    randomness.RNG.getstate(),
                ))

                sending_connection.close()
        except Exception as e:  # noqa: BLE001
            # Suppress all exceptions from the subprocess
            _LOGGER.warning(
                "Suppressed exception in subprocess: %s",
                e,
            )

    @staticmethod
    def _create_new_reference_bindings(
        result: ExecutionResult,
        reference_bindings: dict[int, str],
    ) -> dict[int, str] | None:
        """Create new reference bindings.

        See the docstring of `_create_variable_binding` for more information.

        Args:
            result: The result to create new reference bindings for
            reference_bindings: The old reference bindings

        Returns:
            The new reference bindings
        """
        try:
            return (
                reference_bindings
                if result.assertion_trace.trace and not dill.detect.baditems(reference_bindings)
                else None
            )
        except Exception as exception:  # noqa: BLE001
            SubprocessTestCaseExecutor._log_different_results(
                "Failed to fix reference bindings for pickle",
                exception,
            )
            return None

    @staticmethod
    def _replace_tracer(tracer: ExecutionTracer) -> None:
        """Replace the tracer used for instrumentation.

        This is necessary because the tracer used in the instrumented module is
        inaccessible from the function running in the subprocess and we need to have
        access to it otherwise it would kill the subprocess because we would not be able
        to change the `current_thread_identifier`.
        """
        instrumentation_finder = sys.meta_path[0]

        if isinstance(instrumentation_finder, InstrumentationFinder):
            instrumentation_finder.subject_properties.instrumentation_tracer.tracer = tracer

    @staticmethod
    def _log_different_results(reason: str, obj: Any) -> None:
        _LOGGER.warning(
            "%s, final results might differ from classic execution with same seed: %s",
            reason,
            obj,
        )

    @staticmethod
    def _fix_unpicklable(
        obj: Any,
        filter_bad_items_label: str,
        filter_function: Callable[[Any], None],
        clear_bad_items_label: str,
        clear_function: Callable[[], None],
    ) -> None:
        try:
            if bad_items := dill.detect.baditems(obj):
                SubprocessTestCaseExecutor._log_different_results(
                    filter_bad_items_label,
                    bad_items,
                )
                filter_function(bad_items)
        except Exception as exception:  # noqa: BLE001
            SubprocessTestCaseExecutor._log_different_results(
                clear_bad_items_label,
                exception,
            )
            clear_function()

    @staticmethod
    def _fix_result_for_pickle(result: ExecutionResult) -> None:
        """Fix the result for pickling.

        This method removes unpicklable objects from the result because it would cause
        the subprocess to crash when sending the result back to the main process.

        Args:
            result: The result to fix
        """
        SubprocessTestCaseExecutor._fix_unpicklable(
            result.exceptions,
            "Unpicklable exceptions",
            lambda bad: _filter_bad_exceptions(result, bad),
            "Failed to fix exceptions for pickle",
            lambda: _clear_bad_exceptions(result),
        )

        SubprocessTestCaseExecutor._fix_unpicklable(
            list(itertools.chain(*result.assertion_trace.trace.values())),
            "Unpicklable assertions",
            lambda bad: _filter_bad_assertions(result, bad),
            "Failed to fix assertions for pickle",
            lambda: _clear_bad_assertions(result),
        )

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.execution_trace.executed_assertions,
            "Unpicklable executed assertions",
            lambda bad: _filter_bad_executed_assertions(result, bad),
            "Failed to fix executed assertions for pickle",
            lambda: _clear_bad_executed_assertions(result),
        )

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.proxy_knowledge,
            "Unpicklable proxy knowledges",
            lambda bad: _filter_bad_proxy_knowledges(result, bad),
            "Failed to fix proxy knowledges for pickle",
            lambda: _clear_bad_proxy_knowledges(result),
        )

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.proper_return_type_trace,
            "Unpicklable proper return type traces",
            lambda bad: _filter_bad_proper_return_type_traces(result, bad),
            "Failed to fix proper return type traces for pickle",
            lambda: _clear_bad_proper_return_type_traces(result),
        )

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.raw_return_type_generic_args,
            "Unpicklable raw return type generic args",
            lambda bad: _filter_bad_raw_return_type_generic_args(result, bad),
            "Failed to fix raw return type generic args for pickle",
            lambda: _clear_bad_raw_return_type_generic_args(result),
        )

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.raw_return_types,
            "Unpicklable raw return types",
            lambda bad: _filter_bad_raw_return_types(result, bad),
            "Failed to fix raw return types for pickle",
            lambda: _clear_bad_raw_return_types(result),
        )


def _filter_bad_exceptions(result: ExecutionResult, bad_exceptions: Collection[Exception]) -> None:
    result.exceptions = {
        position: exception
        for position, exception in result.exceptions.items()
        if exception not in bad_exceptions
    }


def _clear_bad_exceptions(result: ExecutionResult) -> None:
    result.exceptions.clear()


def _filter_bad_assertions(
    result: ExecutionResult, bad_assertions: Collection[ass.Assertion]
) -> None:
    for assertions in result.assertion_trace.trace.values():
        assertions.difference_update(bad_assertions)


def _clear_bad_assertions(result: ExecutionResult) -> None:
    result.assertion_trace.clear()


def _filter_bad_executed_assertions(
    result: ExecutionResult, bad_executed_assertions: Collection[ExecutedAssertion]
) -> None:
    result.execution_trace.executed_assertions = [
        assertion
        for assertion in result.execution_trace.executed_assertions
        if assertion not in bad_executed_assertions
    ]


def _clear_bad_executed_assertions(result: ExecutionResult) -> None:
    result.execution_trace.executed_assertions.clear()


def _filter_bad_proxy_knowledges(
    result: ExecutionResult, bad_proxy_knowledges: Collection[tt.UsageTraceNode]
) -> None:
    result.proxy_knowledge = {
        position: proxy
        for position, proxy in result.proxy_knowledge.items()
        if proxy not in bad_proxy_knowledges
    }


def _clear_bad_proxy_knowledges(result: ExecutionResult) -> None:
    result.proxy_knowledge.clear()


def _filter_bad_proper_return_type_traces(
    result: ExecutionResult, bad_proper_return_type_traces: Collection[ProperType]
) -> None:
    result.proper_return_type_trace = {
        position: proper_return_type
        for position, proper_return_type in result.proper_return_type_trace.items()
        if proper_return_type not in bad_proper_return_type_traces
    }


def _clear_bad_proper_return_type_traces(result: ExecutionResult) -> None:
    result.proper_return_type_trace.clear()


def _filter_bad_raw_return_type_generic_args(
    result: ExecutionResult, bad_raw_return_type_generic_args: Collection[type]
) -> None:
    result.raw_return_type_generic_args = {
        position: generic_args
        for position, generic_args in result.raw_return_type_generic_args.items()
        if all(type_ not in bad_raw_return_type_generic_args for type_ in generic_args)
    }


def _clear_bad_raw_return_type_generic_args(result: ExecutionResult) -> None:
    result.raw_return_type_generic_args.clear()


def _filter_bad_raw_return_types(
    result: ExecutionResult, bad_raw_return_types: Collection[type]
) -> None:
    result.raw_return_types = {
        position: type_
        for position, type_ in result.raw_return_types.items()
        if type_ not in bad_raw_return_types
    }


def _clear_bad_raw_return_types(result: ExecutionResult) -> None:
    result.raw_return_types.clear()
