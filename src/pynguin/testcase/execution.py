#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Contains all code related to test-case execution."""

from __future__ import annotations

import abc
import contextlib
import inspect
import logging
import sys
import threading
import time
from abc import abstractmethod
from queue import Empty, Queue
from types import ModuleType
from typing import TYPE_CHECKING, Any

import libcst as cst

# Needs to be loaded, i.e., in sys.modules for the execution of assertions to work.
import pytest

import pynguin.configuration as config
import pynguin.utils.execution_recorder as ter
import pynguin.utils.statistics.stats as stat
import pynguin.utils.typetracing as tt
from pynguin.instrumentation import AST_FILENAME
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import CheckedCoverageInstrumentation
from pynguin.testcase.execution_isolation import (
    OutputSuppressionContext,
    PatchRandomOnUnpickle,
    _make_deterministic,
    suppress_logging,
)
from pynguin.testcase.execution_observers import (
    ExecutionObserver,
    RemoteAssertionExecutionObserver,
    RemoteExecutionObserver,
    RemoteReturnTypeObserver,
    RemoteTypeTracingObserver,
    ReturnTypeObserver,
    TypeTracingObserver,
    find_call,
    map_args_to_params,
)
from pynguin.testcase.execution_result import ExecutionResult
from pynguin.utils import randomness
from pynguin.utils.exceptions import (
    ModuleNotImportedError,
    TracingAbortedException,
)
from pynguin.utils.fs_isolation import FilesystemIsolation
from pynguin.utils.naming import get_module_alias
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

# Public API of this facade module: the executor classes defined here plus the
# symbols re-exported from the focused ``pynguin.testcase`` execution modules.
__all__ = [
    "AbstractTestCaseExecutor",
    "ExecutionObserver",
    "ExecutionResult",
    "ModuleProvider",
    "OutputSuppressionContext",
    "PatchRandomOnUnpickle",
    "RemoteAssertionExecutionObserver",
    "RemoteExecutionObserver",
    "RemoteReturnTypeObserver",
    "RemoteTypeTracingObserver",
    "ReturnTypeObserver",
    "SubprocessTestCaseExecutor",
    "TestCaseExecutor",
    "TypeTracingObserver",
    "TypeTracingTestCaseExecutor",
    "find_call",
    "map_args_to_params",
    "suppress_logging",
]

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from contextlib import AbstractContextManager
    from types import ModuleType

    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.instrumentation.tracer import SubjectProperties


_LOGGER = logging.getLogger(__name__)


class ModuleProvider:
    """Class for providing modules."""

    def __init__(self):  # noqa: D107
        self._mutated_module_aliases: dict[str, ModuleType] = {}

    @staticmethod
    def __get_imported_module(module_name: str) -> ModuleType:
        module = sys.modules.get(module_name)

        if module is not None:
            return module

        try:
            package_name, submodule_name = module_name.rsplit(".", 1)
        except ValueError as e:
            raise ModuleNotImportedError(module_name) from e

        try:
            package = ModuleProvider.__get_imported_module(package_name)
        except ModuleNotImportedError as e:
            raise ModuleNotImportedError(module_name) from e

        try:
            submodule = getattr(package, submodule_name)
        except AttributeError as e:
            raise ModuleNotImportedError(module_name) from e

        if not inspect.ismodule(submodule):
            raise ModuleNotImportedError(module_name)

        return submodule

    def get_module(self, module_name: str) -> ModuleType:
        """Provides a module.

        Either from sys.modules or if a mutated version for the given module name exists
        then the mutated version of the module will be returned.

        Args:
            module_name: string for the module alias, which should be loaded

        Raises:
            ModuleNotImportedError: If the module is not imported.

        Returns:
            the module which should be loaded.
        """
        if (mutated_module := self._mutated_module_aliases.get(module_name, None)) is not None:
            return mutated_module
        return self.__get_imported_module(module_name)

    def add_mutated_version(self, module_name: str, mutated_module: ModuleType) -> None:
        """Adds a mutated version of a module to the collection of mutated modules.

        Args:
            module_name: for the module name of the module, which should be mutated.
            mutated_module: the custom module, which should be used.
        """
        self._mutated_module_aliases[module_name] = mutated_module

    def clear_mutated_modules(self):
        """Clear the existing aliases."""
        self._mutated_module_aliases.clear()


class AbstractTestCaseExecutor(abc.ABC):
    """Interface for a test case executor."""

    @property
    @abstractmethod
    def module_provider(self) -> ModuleProvider:
        """The module provider used by this executor.

        Returns:
            The used module provider
        """

    @abstractmethod
    def add_observer(self, observer: ExecutionObserver) -> None:
        """Add an execution observer.

        Args:
            observer: the observer to be added.
        """

    @abstractmethod
    def clear_observers(self) -> None:
        """Remove all existing observers."""

    @abstractmethod
    def temporarily_add_observer(self, observer: ExecutionObserver) -> AbstractContextManager[None]:
        """Temporarily add the given observer.

        Args:
            observer: The observer to add.
        """

    @abstractmethod
    def add_remote_observer(self, remote_observer: RemoteExecutionObserver) -> None:
        """Add a remote execution observer.

        Args:
            remote_observer: the remote observer to be added.
        """

    @abstractmethod
    def clear_remote_observers(self) -> None:
        """Remove all existing remote observers."""

    @abstractmethod
    def temporarily_add_remote_observer(
        self, remote_observer: RemoteExecutionObserver
    ) -> AbstractContextManager[None]:
        """Temporarily add a remote observer.

        Args:
            remote_observer: The remote observer to add.
        """

    @property
    @abstractmethod
    def subject_properties(self) -> SubjectProperties:
        """Provide access to the subject properties.

        Returns:
            The subject properties
        """

    @abstractmethod
    def execute(self, test_case: tc.TestCase) -> ExecutionResult:
        """Executes all statements of the given test case.

        Args:
            test_case: the test case that should be executed.

        Raises:
            RuntimeError: If something goes wrong inside Pynguin during execution.

        Returns:
            Result of the execution
        """

    def execute_multiple(self, test_cases: Iterable[tc.TestCase]) -> Iterable[ExecutionResult]:
        """Executes multiple test cases.

        Args:
            test_cases: The test cases that should be executed.

        Raises:
            RuntimeError: If something goes wrong inside Pynguin during execution.

        Yields:
            The results of the execution
        """
        for test_case in test_cases:
            yield self.execute(test_case)


class TestCaseExecutor(AbstractTestCaseExecutor):
    """An executor that executes the generated test cases."""

    def __init__(
        self,
        subject_properties: SubjectProperties,
        module_provider: ModuleProvider | None = None,
        maximum_test_execution_timeout: int = 5,
        test_execution_time_per_statement: int = 1,
    ) -> None:
        """Create new test case executor.

        Args:
            subject_properties: The properties of the subject under test.
            module_provider: The used module provider
            maximum_test_execution_timeout: The minimum timeout time (in seconds)
                before a test case execution times out.
            test_execution_time_per_statement: The amount of time (in seconds) that is
                added to the timeout per statement, up to minimum_test_execution_timeout
        """
        self._maximum_test_execution_timeout = maximum_test_execution_timeout
        self._test_execution_time_per_statement = test_execution_time_per_statement

        self._module_provider = module_provider if module_provider is not None else ModuleProvider()
        self._subject_properties = subject_properties
        self._observers: list[ExecutionObserver] = []
        self._remote_observers: list[RemoteExecutionObserver] = []
        self._instrument = (
            config.CoverageMetric.CHECKED in config.configuration.statistics_output.coverage_metrics
        )
        checked_instrumentation = CheckedCoverageInstrumentation(self._subject_properties)
        self._checked_transformer = InstrumentationTransformer(
            self._subject_properties,
            [checked_instrumentation],
        )
        self._crash_revealing_hashes: set[str] = set()
        self._executed_test_cases: int = 0

    @property
    def module_provider(self) -> ModuleProvider:  # noqa: D102
        return self._module_provider

    def add_observer(self, observer: ExecutionObserver) -> None:  # noqa: D102
        self._observers.append(observer)

    def clear_observers(self) -> None:  # noqa: D102
        self._observers.clear()

    @contextlib.contextmanager
    def temporarily_add_observer(  # noqa: D102
        self, observer: ExecutionObserver
    ) -> Generator[None, None, None]:
        self._observers.append(observer)
        yield
        self._observers.remove(observer)

    def add_remote_observer(  # noqa: D102
        self, remote_observer: RemoteExecutionObserver
    ) -> None:
        self._remote_observers.append(remote_observer)

    def clear_remote_observers(self) -> None:  # noqa: D102
        self._remote_observers.clear()

    @contextlib.contextmanager
    def temporarily_add_remote_observer(  # noqa: D102
        self, remote_observer: RemoteExecutionObserver
    ) -> Generator[None, None, None]:
        self._remote_observers.append(remote_observer)
        yield
        self._remote_observers.remove(remote_observer)

    def _yield_remote_observers(self) -> Generator[RemoteExecutionObserver, None, None]:
        yield from self._remote_observers
        yield from (observer.remote_observer for observer in self._observers)

    @property
    def subject_properties(self) -> SubjectProperties:  # noqa: D102
        return self._subject_properties

    def register_crash_revealing_hash(self, test_case_hash: str) -> int | None:
        """Record a crash-revealing test-case hash.

        Args:
            test_case_hash: The hash of the crashing test case.

        Returns:
            The new number of distinct crash-revealing hashes if the hash was not
            seen before, otherwise ``None``.
        """
        if test_case_hash in self._crash_revealing_hashes:
            return None
        self._crash_revealing_hashes.add(test_case_hash)
        return len(self._crash_revealing_hashes)

    def set_instrument(self, instrument: bool) -> None:  # noqa: FBT001
        """Set if the test is to be instrumented as well.

        Args:
            instrument: Whether to instrument the test and its assertions.
        """
        self._instrument = instrument

    def execute(  # noqa: D102
        self,
        test_case: tc.TestCase,
    ) -> ExecutionResult:
        self._executed_test_cases += 1
        stat.track_output_variable(RuntimeVariable.Executed, self._executed_test_cases)
        self._before_remote_test_case_execution(test_case)

        with ter.ExecutionRecorder(test_case):
            output_suppression_context = OutputSuppressionContext()
            return_queue: Queue[ExecutionResult] = Queue()
            thread = threading.Thread(
                target=self._execute_test_case,
                args=(test_case, output_suppression_context, return_queue),
                daemon=True,
            )
            thread.start()
            thread.join(
                timeout=min(
                    self._maximum_test_execution_timeout,
                    self._test_execution_time_per_statement * test_case.size(),
                )
            )
            if thread.is_alive():
                # Kills the thread
                self._subject_properties.instrumentation_tracer.stop()
                # Wait for the thread so that stdout/stderr is not redirected anymore
                _LOGGER.debug("Waiting for thread to finish")
                thread.join(timeout=self._maximum_test_execution_timeout)
                # Restore stdout and stderr if it was not already done by the thread
                _LOGGER.debug("Restoring stdout and stderr")
                output_suppression_context.restore()
                result = ExecutionResult(timeout=True)
                _LOGGER.warning("Experienced timeout from test-case execution")
            else:
                try:
                    result = return_queue.get(block=False)
                except Empty:
                    _LOGGER.error("Finished thread did not return a result.")
                    # previously we re-raised the exception as a RuntimeError to have a marker in
                    # the logs, however, it is still not fully clear WHY this actually happens.
                    # Plus, it confuses users.  Thus, for now log the message, such that we can
                    # still search for it in the logs, but continue with an empty results.  This
                    # allows the EA to continue with the search process.
                    _LOGGER.error("Bug in Pynguin!")
                    result = ExecutionResult(timeout=True)
            self._after_remote_test_case_execution(test_case, result)
            self._subject_properties.validate_execution_trace(result.execution_trace)
            return result

    def _before_test_case_execution(self, test_case: tc.TestCase) -> None:
        _make_deterministic()
        self._subject_properties.instrumentation_tracer.init_trace()
        for observer in self._yield_remote_observers():
            observer.before_test_case_execution(test_case)

    def _execute_test_case(
        self,
        test_case: tc.TestCase,
        output_suppression_context: OutputSuppressionContext,
        result_queue: Queue,
    ) -> None:
        try:
            self._before_test_case_execution(test_case)
            result = ExecutionResult()
            with (
                FilesystemIsolation(),
                output_suppression_context,
                self._subject_properties.instrumentation_tracer,
            ):
                namespace = self._build_namespace()
                for idx, statement in enumerate(test_case.statements()):
                    node = self._before_statement_execution(statement, namespace)
                    exception = self._exec_statement(node, namespace)
                    self._after_statement_execution(statement, namespace, exception)
                    if exception is not None:
                        result.report_new_thrown_exception(idx, exception)
                        break
            self._after_test_case_execution(test_case, result)
        except ModuleNotImportedError as e:
            _LOGGER.warning(
                """Module %s was referenced in a __module__ attribute but was not imported.
                This may be due to a bug in the SUT, especially if it uses C-modules.
                """,
                e.name,
                exc_info=True,
            )
            result = ExecutionResult(timeout=True)
        except TracingAbortedException:
            return

        result_queue.put(result)

    def _build_namespace(self) -> dict[str, Any]:
        """Build the shared namespace used to execute a test case's statements.

        The namespace is used as both globals and locals for every statement's
        ``exec`` call, so that name resolution inside comprehensions and lambdas
        behaves the same way it would at module scope.

        Returns:
            The namespace, pre-populated with builtins, pytest, the SUT
            module's public members, and the SUT module under its alias.
        """
        module_name = config.configuration.module_name
        module = self._module_provider.get_module(module_name)
        module_alias = get_module_alias(module_name)
        namespace: dict[str, Any] = {
            "__builtins__": __builtins__,
            "pytest": pytest,
        }
        namespace.update(vars(module))
        namespace[module_alias] = module
        return namespace

    def execute_source(self, code_str: str, namespace: dict[str, Any]) -> BaseException | None:
        """Compile and execute source code against the shared namespace.

        Compiles with ``AST_FILENAME`` (matching the filename that the whole
        instrumentation/slicing stack special-cases for test code, see
        ``pynguin.instrumentation.AST_FILENAME``) and, if this executor was
        configured for checked-coverage instrumentation
        (``set_instrument(True)``), applies ``self._checked_transformer``
        before executing, so that every executed instruction is appended to
        the trace and can later be used as a dynamic-slicing criterion.

        Args:
            code_str: The source code to compile and execute.
            namespace: The shared namespace (used as both globals and locals).

        Returns:
            The raised exception, if any, otherwise ``None``.
        """
        code = compile(code_str, AST_FILENAME, "exec")
        if self._instrument:
            code = self._checked_transformer.instrument_code(code)
        try:
            exec(code, namespace)  # noqa: S102
        except TracingAbortedException:
            # Must always propagate, so the watchdog thread can be killed.
            raise
        except BaseException as exc:  # noqa: BLE001
            return exc
        return None

    def _exec_statement(
        self,
        node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
        namespace: dict[str, Any],
    ) -> BaseException | None:
        """Render and execute a single CST node against the shared namespace.

        Args:
            node: The (possibly observer-rewritten) CST node to execute.
            namespace: The shared namespace (used as both globals and locals).

        Returns:
            The raised exception, if any, otherwise ``None``.
        """
        code_str = cst.Module(body=[node]).code
        return self.execute_source(code_str, namespace)

    def _before_statement_execution(
        self, statement: tc.Statement, namespace: dict[str, Any]
    ) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        # Check if the current thread is still the one that should be executing
        # Otherwise raise an exception to kill it.
        self._subject_properties.instrumentation_tracer.check()

        # We need to disable the tracer, because an observer might interact with an
        # object of the SUT and trigger code execution, which is not caused by the
        # test case and should therefore not be in the trace.
        #
        # Observers may rewrite the node (e.g. type tracing injects proxies); the
        # node is threaded through all observers and the final one is executed.
        node: cst.SimpleStatementLine | cst.BaseCompoundStatement = statement.node
        with self._subject_properties.instrumentation_tracer.temporarily_disable():
            for observer in self._yield_remote_observers():
                node = observer.before_statement_execution(statement, node, namespace)
        return node

    def _after_statement_execution(
        self,
        statement: tc.Statement,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        # See comments in _before_statement_execution
        self._subject_properties.instrumentation_tracer.check()

        with self._subject_properties.instrumentation_tracer.temporarily_disable():
            for observer in reversed(tuple(self._yield_remote_observers())):
                observer.after_statement_execution(statement, self, namespace, exception)

    def _after_test_case_execution(self, test_case: tc.TestCase, result: ExecutionResult) -> None:
        """Collect the trace data after each executed test case.

        Args:
            test_case: The executed test case
            result: The execution result
        """
        result.execution_trace = self._subject_properties.instrumentation_tracer.get_trace()
        for observer in self._yield_remote_observers():
            observer.after_test_case_execution(self, test_case, result)

    def _before_remote_test_case_execution(self, test_case: tc.TestCase) -> None:
        """Process test case before remote execution.

        Args:
            test_case: The executed test case
        """
        for observer in self._observers:
            observer.before_remote_test_case_execution(test_case)

    def _after_remote_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Process results after remote execution.

        Args:
            test_case: The executed test case
            result: The execution result
        """
        for observer in self._observers:
            observer.after_remote_test_case_execution(test_case, result)


class TypeTracingTestCaseExecutor(AbstractTestCaseExecutor):
    """A test case executor that delegates to another executor.

    Every test case is executed twice, one time for the regular result
    and one time with proxies in order to refine parameter types.
    """

    def __init__(
        self,
        delegate: AbstractTestCaseExecutor,
        cluster: ModuleTestCluster,
        type_tracing_probability: float = 1.0,
    ):
        """Initializes the executor.

        Args:
            delegate: The delegate
            cluster: The test cluster
            type_tracing_probability: The probability to use type tracing during execution
        """
        self._delegate = delegate
        self._type_tracing_observer = TypeTracingObserver(cluster)
        self._return_type_observer = ReturnTypeObserver(cluster)
        self._type_tracing_probability = type_tracing_probability

    @property
    def module_provider(self) -> ModuleProvider:  # noqa: D102
        return self._delegate.module_provider

    def add_observer(self, observer: ExecutionObserver) -> None:  # noqa: D102
        self._delegate.add_observer(observer)

    def clear_observers(self) -> None:  # noqa: D102
        self._delegate.clear_observers()

    def temporarily_add_observer(  # noqa: D102
        self, observer: ExecutionObserver
    ) -> AbstractContextManager[None]:
        return self._delegate.temporarily_add_observer(observer)

    def add_remote_observer(  # noqa: D102
        self, remote_observer: RemoteExecutionObserver
    ) -> None:
        self._delegate.add_remote_observer(remote_observer)

    def clear_remote_observers(self) -> None:  # noqa: D102
        self._delegate.clear_remote_observers()

    def temporarily_add_remote_observer(  # noqa: D102
        self, remote_observer: RemoteExecutionObserver
    ) -> AbstractContextManager[None]:
        return self._delegate.temporarily_add_remote_observer(remote_observer)

    @property
    def subject_properties(self) -> SubjectProperties:  # noqa: D102
        return self._delegate.subject_properties

    def execute(self, test_case: tc.TestCase) -> ExecutionResult:  # noqa: D102
        if not (randomness.next_float() < self._type_tracing_probability):
            return self._delegate.execute(test_case)

        with self._delegate.temporarily_add_observer(self._return_type_observer):
            result = self._delegate.execute(test_case)
        if not result.timeout:
            # Only execute with proxies if the test case doesn't time out.
            # There is no need to stall another thread.
            with (
                self._delegate.temporarily_add_observer(self._type_tracing_observer),
                tt.shim_isinstance(),
            ):
                # TODO(fk) Do we record wrong stuff, i.e., type checks from observers?
                #  Make use of type errors?
                start = time.time_ns()
                self._delegate.execute(test_case)
                stat.add_to_runtime_variable(
                    RuntimeVariable.TypeTracingTime, time.time_ns() - start
                )
                stat.add_to_runtime_variable(RuntimeVariable.TypeTracingExecutions, 1)
        return result


# Re-exported here (at module end, after TestCaseExecutor is defined) so that
# `from pynguin.testcase.execution import SubprocessTestCaseExecutor` keeps working.
# subprocess_executor imports TestCaseExecutor from this module, so this import must
# stay below the TestCaseExecutor definition to avoid a circular-import failure.
from pynguin.testcase.subprocess_executor import (  # noqa: E402
    SubprocessTestCaseExecutor,
)
