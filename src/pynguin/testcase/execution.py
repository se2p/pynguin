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
import copy
import dataclasses
import enum
import inspect
import itertools
import logging
import os
import random
import signal
import sys
import threading
import time
from abc import abstractmethod
from pathlib import Path
from queue import Empty, Queue
from types import ModuleType
from typing import TYPE_CHECKING, Any, TypeVar, cast

import dill  # noqa: S403
import libcst as cst
import multiprocess as mp
import multiprocess.connection as mp_conn

# Needs to be loaded, i.e., in sys.modules for the execution of assertions to work.
import pytest

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.configuration as config
import pynguin.ga.postprocess as pp
import pynguin.utils.execution_recorder as ter
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.statistics.stats as stat
import pynguin.utils.typetracing as tt
from pynguin.analyses.typesystem import Instance, ProperType, TupleType
from pynguin.assertion.assertion_to_ast import assertion_to_cst
from pynguin.instrumentation import AST_FILENAME
from pynguin.instrumentation.machinery import InstrumentationFinder
from pynguin.instrumentation.tracer import ExecutedAssertion, ExecutionTrace, ExecutionTracer
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import CheckedCoverageInstrumentation
from pynguin.utils import randomness
from pynguin.utils.exceptions import (
    MinimizationFailureError,
    ModuleNotImportedError,
    TracingAbortedException,
)
from pynguin.utils.fs_isolation import FilesystemIsolation
from pynguin.utils.naming import get_module_alias
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Generator, Iterable
    from contextlib import AbstractContextManager
    from types import ModuleType

    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import ModuleTestCluster, TestCluster
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.testcase.testcase import TestCase


_LOGGER = logging.getLogger(__name__)


class RemoteExecutionObserver(abc.ABC):
    """A remote observer that can be used to observe the execution of a test case.

    Important Note: If an observer is stateful, then this state must be encapsulated
    in a threading.local, i.e., be bound to a thread. Note that thread local data
    is initialized per thread, so there is no need to clear any pre-existing data
    (because there is none), as every thread gets its own instance.

    Methods in this class are not allowed to interact with the 'outside' because this
    class could be sent to a remote environment. The only thing that should leave an
    observer are results when they are written to the execution result in
    RemoteExecutionObserver::after_test_case_execution.

    You may interact with the 'outside' in
    ExecutionObserver::after_remote_test_case_execution.

    Note: Usage of threading.local may interfere with debugging tools, such as pydevd.
    In such a case, disable Cython by setting the following environment variable:
    PYDEVD_USE_CYTHON=NO

    For more details, look at some implementations, e.g., AssertionTraceObserver.
    """

    def __init__(self) -> None:  # noqa: B027
        """Initializes the remote observer."""

    @property
    def state(self) -> dict[str, Any]:
        """The state of the observer.

        Returns:
            The state of the observer
        """
        return {}

    @state.setter  # noqa: B027
    def state(self, state: dict[str, Any]) -> None:
        """Set the state of the observer.

        Args:
            state: The new state
        """

    @abstractmethod
    def before_test_case_execution(self, test_case: tc.TestCase):
        """Called before test case execution.

        Args:
            test_case: The test cases that will be executed.
        """

    def before_statement_execution(
        self,
        statement: tc.Statement,
        node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
        namespace: dict[str, Any],
    ) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        """Called before a single statement is executed.

        Returns ``node`` unchanged by default; observers that need to rewrite the
        node before it is executed (e.g. to inject proxies) should override this
        and return the modified node. The (possibly modified) node returned here is
        what actually gets executed, so overriders must return a valid node.

        Args:
            statement: The statement that is about to be executed.
            node: The CST node that is about to be executed for this statement.
            namespace: The shared namespace the statement will execute in.

        Returns:
            The CST node to execute (``node`` unchanged by default).
        """
        return node

    def after_statement_execution(  # noqa: B027
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        """Called after a single statement is executed.

        No-op by default; observers that need per-statement observation should
        override this.

        Args:
            statement: The statement that was executed.
            executor: The executor that executed the statement.
            namespace: The shared namespace the statement executed in.
            exception: The exception raised by the statement, if any.
        """

    @abstractmethod
    def after_test_case_execution(
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        """Called after test case execution.

        The call happens from the remote environment that executed the test case. You
        should override this method to extract information from the thread local storage
        to the execution result.

        Note: When a timeout occurs, then this method might not be called at all.

        Args:
            executor: The executor that executed the test case
            test_case: The test cases that was executed
            result: The execution result
        """

    def __getstate__(self) -> dict[str, Any]:
        return self.state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__init__()  # type: ignore[misc]
        self.state = state


class ExecutionObserver(abc.ABC):
    """An observer that can be used to observe the execution of a test case."""

    @property
    @abstractmethod
    def remote_observer(self) -> RemoteExecutionObserver:
        """The remote observer.

        Returns:
            The remote observer
        """

    @abstractmethod
    def before_remote_test_case_execution(self, test_case: tc.TestCase) -> None:
        """Called before test case execution from the main thread.

        Note: This method can be called with several test cases before the
        after_remote_test_case_execution method is called.

        Args:
            test_case: The test cases that will be executed.
        """

    @abstractmethod
    def after_remote_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Called after test case execution from the main thread.

        Note: This method is always called, though the data you expect in the execution
        might not be there, if the execution of the test case timed out.
        You are not allowed to access thread local state here (due to how
        threading.local works, it isn't even possible ;)), but you can do some
        postprocessing with the data from the execution result here.

        Args:
            test_case: The test cases that was executed
            result: The execution result
        """


class RemoteAssertionExecutionObserver(RemoteExecutionObserver):
    """A remote observer which executes the assertions of statements.

    Executes each statement's assertions right after the statement, with
    checked-coverage instrumentation enabled (when the executor was configured
    for it via ``set_instrument(True)``), and records their trace positions
    via the instrumentation tracer so they can later be sliced.

    Enables slicing on the recorded data.

    Note: this observer must only be registered together with
    ``executor.set_instrument(True)``; otherwise the assertion code executes
    uninstrumented and ``ExecutionTracer.track_assertion_position`` will fail
    to find a boolean-jump instruction to record.
    """

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: not used
        """

    def after_statement_execution(
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        """Execute the statement's assertions, instrumented, and track them.

        Args:
            statement: The statement that was executed.
            executor: The executor that executed the statement.
            namespace: The shared namespace the statement executed in.
            exception: The exception raised by the statement, if any.
        """
        tracer = executor.subject_properties.instrumentation_tracer
        with tracer.temporarily_enable():
            if statement.has_only_exception_assertion():
                if exception is not None:
                    tracer.track_exception_assertion(statement)
                return
            if exception is not None:
                # The bound variable (if any) is undefined; assertions on it
                # cannot meaningfully hold, so skip them.
                return
            for assertion in statement.assertions:
                cst_node = assertion_to_cst(assertion)
                if cst_node is None:
                    # E.g. an ExceptionAssertion mixed in with other
                    # assertions; handled structurally elsewhere.
                    continue
                code_str = cst.Module(body=[cst_node]).code
                assertion_exception = executor.execute_source(code_str, namespace)
                if assertion_exception is not None:
                    # A failed/erroring assertion has no meaningful boolean
                    # jump to record; skip tracking its position.
                    continue
                tracer.track_assertion_position(assertion)

    def after_test_case_execution(
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        """Not used.

        Args:
            executor: Not used
            test_case: Not used
            result: Not used
        """


class RemoteReturnTypeObserver(RemoteExecutionObserver):
    """An observer which observes the runtime types seen during execution."""

    class RemoteReturnTypeLocalState(threading.local):
        """Encapsulate observed return types."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.return_type_trace: dict[int, type] = {}
            self.return_type_generic_args: dict[int, tuple[type, ...]] = {}
            self.position: int = 0

    def __init__(self):
        """Initializes the remote observer."""
        super().__init__()
        self._return_type_local_state = RemoteReturnTypeObserver.RemoteReturnTypeLocalState()

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return {
            "return_type_trace": self._return_type_local_state.return_type_trace,
            "return_type_generic_args": self._return_type_local_state.return_type_generic_args,
        }

    @state.setter
    def state(self, state: dict[str, Any]):  # noqa: RUF100
        self._return_type_local_state.return_type_trace = state["return_type_trace"]
        self._return_type_local_state.return_type_generic_args = state["return_type_generic_args"]

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        position = self._return_type_local_state.position
        self._return_type_local_state.position = position + 1

        if exception is not None:
            return

        bound_variable = statement.bound_variable
        if bound_variable is None or bound_variable not in namespace:
            return

        value = namespace[bound_variable]
        self._return_type_local_state.return_type_trace[position] = type(value)

        # TODO(fk) Hardcoded support for generics.
        # Try to guess generic arguments from elements.
        # `value` may be an arbitrary SUT object (or, once type-tracing's proxy
        # is installed, an ObjectProxy) whose `__len__`/`__iter__` misbehave;
        # guard the probing so a misbehaving object cannot abort the trace.
        with contextlib.suppress(Exception):
            if type(value) in {set, list} and len(value) > 0:
                self._return_type_local_state.return_type_generic_args[position] = (
                    type(next(iter(value))),
                )
            elif isinstance(value, dict) and len(value) > 0:
                first_item = next(iter(value.items()))
                self._return_type_local_state.return_type_generic_args[position] = (
                    type(first_item[0]),
                    type(first_item[1]),
                )
            elif type(value) is tuple:
                self._return_type_local_state.return_type_generic_args[position] = tuple(
                    type(v) for v in value
                )

    def after_test_case_execution(  # noqa: D102
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ):
        result.raw_return_types = dict(self._return_type_local_state.return_type_trace)
        result.raw_return_type_generic_args = dict(
            self._return_type_local_state.return_type_generic_args
        )


class ReturnTypeObserver(ExecutionObserver):
    """Observes the runtime types seen during execution.

    Updates the return types of the called function with the observed types.
    """

    def __init__(self, test_cluster: TestCluster):
        """Initializes the observer.

        Args:
            test_cluster: The test cluster that shall be updated
        """
        self._test_cluster = test_cluster
        self._remote_observer = RemoteReturnTypeObserver()

    @property
    def remote_observer(self) -> RemoteExecutionObserver:
        """The remote observer.

        Returns:
            The remote observer
        """
        return self._remote_observer

    def before_remote_test_case_execution(self, test_case: TestCase) -> None:
        """Not used.

        Args:
            test_case: Not used
        """

    def after_remote_test_case_execution(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        # We store the raw types, so we still need to convert them to proper types.
        # This must be done outside the executing thread.
        for idx, raw_type in result.raw_return_types.items():
            if raw_type is type(NotImplemented):
                continue
            proper_type = self._test_cluster.type_system.convert_type_hint(raw_type)
            proper_type = self.__infer_known_generics(result, idx, proper_type)
            result.proper_return_type_trace[idx] = proper_type
            statement = test_case.get_statement(idx)
            call_acc = getattr(statement, "accessible", None)
            if isinstance(call_acc, gao.GenericCallableAccessibleObject):
                self._test_cluster.update_return_type(call_acc, proper_type)

    def __infer_known_generics(
        self, result: ExecutionResult, idx: int, proper: ProperType
    ) -> ProperType:
        if idx not in result.raw_return_type_generic_args:
            return proper

        if isinstance(proper, TupleType):
            return TupleType(
                tuple(
                    self._test_cluster.type_system.convert_type_hint(t)
                    for t in result.raw_return_type_generic_args[idx]
                )
            )
        if isinstance(proper, Instance) and proper.type.raw_type in {list, set, dict}:
            return Instance(
                proper.type,
                tuple(
                    self._test_cluster.type_system.convert_type_hint(t)
                    for t in result.raw_return_type_generic_args[idx]
                ),
            )
        return proper


T = TypeVar("T")


@dataclasses.dataclass
class ExecutionResult:
    """Result of an execution."""

    timeout: bool = False
    exceptions: dict[int, BaseException] = dataclasses.field(default_factory=dict, init=False)
    assertion_trace: at.AssertionTrace = dataclasses.field(
        default_factory=at.AssertionTrace, init=False
    )
    assertion_verification_trace: at.AssertionVerificationTrace = dataclasses.field(
        default_factory=at.AssertionVerificationTrace, init=False
    )
    execution_trace: ExecutionTrace = dataclasses.field(default_factory=ExecutionTrace, init=False)

    # Observation of return types.
    raw_return_types: dict[int, type] = dataclasses.field(default_factory=dict, init=False)
    raw_return_type_generic_args: dict[int, tuple[type, ...]] = dataclasses.field(
        default_factory=dict, init=False
    )
    # Observed return types converted to proper types.
    proper_return_type_trace: dict[int, ProperType] = dataclasses.field(
        default_factory=dict, init=False
    )

    proxy_knowledge: dict[tuple[int, str], tt.UsageTraceNode] = dataclasses.field(
        default_factory=dict, init=False
    )

    num_executed_statements: int = dataclasses.field(default=0, init=False)

    def has_test_exceptions(self) -> bool:
        """Returns true if any exceptions were thrown during the execution.

        Returns:
            Whether the test has exceptions
        """
        return bool(self.exceptions)

    def report_new_thrown_exception(self, stmt_idx: int, ex: BaseException) -> None:
        """Report an exception that was thrown during execution.

        Args:
            stmt_idx: the index of the statement, that caused the exception
            ex: the exception
        """
        self.exceptions[stmt_idx] = ex

    def get_first_position_of_thrown_exception(self) -> int | None:
        """Provide the index of the first thrown exception or None.

        Returns:
            The index of the first thrown exception, if any
        """
        if self.has_test_exceptions():
            return min(self.exceptions.keys())
        return None

    def delete_statement_data(self, deleted_statements: set[int]) -> None:
        """Delete statements at given indices.

        It may happen that the test case is modified after execution, for example,
        by removing unused primitives. We have to update the execution result to reflect
        this, otherwise the indexes maybe wrong.

        Args:
            deleted_statements: The indexes of the deleted statements
        """
        self.raw_return_types = ExecutionResult.shift_dict(
            self.raw_return_types, deleted_statements
        )
        self.raw_return_type_generic_args = ExecutionResult.shift_dict(
            self.raw_return_type_generic_args, deleted_statements
        )
        self.proper_return_type_trace = ExecutionResult.shift_dict(
            self.proper_return_type_trace, deleted_statements
        )
        self.exceptions = ExecutionResult.shift_dict(self.exceptions, deleted_statements)

    @staticmethod
    def shift_dict(to_shift: dict[int, T], deleted_indexes: set[int]) -> dict[int, T]:
        """Shifts the entries in the given dictionary.

        Compute the entries' new positions after the given statements were deleted.

        Args:
            to_shift: The dict to shift
            deleted_indexes: A set of deleted statement indexes.

        Returns:
            The shifted dict
        """
        # Count how many statements were deleted up to a given point
        shifts = {}
        delta = 0
        for idx in range(max(to_shift.keys(), default=0) + 1):
            if idx in deleted_indexes:
                delta += 1
            shifts[idx] = delta

        # Shift all indexes accordingly
        shifted = {}
        for stmt_idx, value in to_shift.items():
            if stmt_idx not in deleted_indexes:
                shifted[stmt_idx - shifts[stmt_idx]] = value
        return shifted

    def __str__(self) -> str:
        return f"ExecutionResult(exceptions: {self.exceptions}, trace: {self.execution_trace})"

    def __repr__(self) -> str:
        return str(self)


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


@contextlib.contextmanager
def _suppress_logging():
    """Suppress all log messages during SUT execution.

    Yields:
        Nothing; restores logging on exit.
    """
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


class OutputSuppressionContext:
    """A context manager that suppresses stdout and stderr.

    Operates at two levels:

    - Python level: redirects ``sys.stdout`` / ``sys.stderr`` to ``/dev/null``.
    - OS level: saves file descriptors 0/1/2 via ``os.dup`` so that if the SUT
      closes them (e.g. ``with open(1, 'w')`` where the int happens to be a
      stdio fd), they are restored on exit.
    """

    # Repeatedly opening/closing devnull caused problems.
    # This is closed when Pynguin terminates, since we don't need this output
    # anyway this is acceptable.
    _null_file = open(os.devnull, mode="w")  # noqa: PLW1514, PTH123, SIM115

    def __init__(self) -> None:
        """Create a new context manager that suppress stdout and stderr."""
        self._restored = False
        self._restored_lock = threading.Lock()
        self._saved_fds: dict[int, int] = {}

    def restore(self) -> None:
        """Restore stdout and stderr at both Python and OS level."""
        with self._restored_lock:
            if self._restored:
                return
            self._restored = True
            # Restore OS-level fds first so that sys.__stdout__ / sys.__stderr__
            # point to live fds again before we reassign the Python objects.
            for fd, saved_fd in self._saved_fds.items():
                with contextlib.suppress(OSError):
                    os.dup2(saved_fd, fd)
                with contextlib.suppress(OSError):
                    os.close(saved_fd)
            self._saved_fds.clear()
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

    def __enter__(self) -> None:
        # Save OS-level fds before the SUT has a chance to close them.
        for fd in (0, 1, 2):
            with contextlib.suppress(OSError):
                self._saved_fds[fd] = os.dup(fd)
        sys.stdout = self._null_file
        sys.stderr = self._null_file

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.restore()


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


def _make_deterministic():
    """Make the execution deterministic.

    Reseed the module-level random and every SUT-related random.Random
    instance that was tracked by the _patch_random() hook.  Pynguin's own
    randomness.RNG is excluded so that Pynguin's own decisions remain
    unaffected.
    """
    seed = config.configuration.seeding.seed
    random.seed(seed)

    tracked = getattr(random.Random.seed, "__pynguin_instances__", None)
    if tracked is not None:
        for _inst in list(tracked):
            if _inst is not randomness.RNG:
                _inst.seed(seed)


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


class PatchRandomOnUnpickle:
    """A hook that patches random when unpickled in a subprocess.

    This ensures that random.Random.seed is patched before the SUT is unpickled
    and potentially creates new random.Random instances (e.g., mimesis).
    """

    def __init__(self):
        """Create a new hook."""
        self._config = config.configuration

    def __getstate__(self):
        return {"config": self._config}

    def __setstate__(self, state):
        config.configuration = state["config"]
        from pynguin.generator import _patch_random  # noqa: PLC0415

        _patch_random()


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
        # Calculate hash before to ensure the same hash for minimized and non-minimized one
        test_case_hash = str(hash(test_case))

        # Store hash and track CrashRevealingSize output variable if new hash
        if test_case_hash not in self._crash_revealing_hashes:
            self._crash_revealing_hashes.add(test_case_hash)
            stat.track_output_variable(
                RuntimeVariable.CrashRevealingSize, len(self._crash_revealing_hashes)
            )

        self._safe_crash_test(test_case, hash_str=test_case_hash)
        try:
            minimized_test_case = self._minimize(test_case, exit_code)
            self._safe_crash_test(minimized_test_case, hash_str=test_case_hash, minimized=True)
        except MinimizationFailureError:
            _LOGGER.warning("Minimized the test case failed. Not storing minimized test case.")

    def _minimize(self, test_case: tc.TestCase, exit_code: int | None) -> tc.TestCase:
        test_case_to_minimize = test_case.clone()
        minimizer = pp.CrashPreservingMinimizationVisitor(self)
        # The per-test-case minimisation visitors are invoked directly.
        minimizer.visit_default_test_case(test_case_to_minimize)

        # Verify that the minimized test case still crashes
        new_exit_code = self.execute_with_exit_code(test_case_to_minimize)
        if exit_code == new_exit_code:
            _LOGGER.info(
                "Minimized crashed test case from %d to %d statements",
                test_case.size(),
                test_case_to_minimize.size(),
            )
            return test_case_to_minimize
        raise MinimizationFailureError(
            "Minimizing the test case failed, as it does not cause the same crash anymore."
        )

    @staticmethod
    def _safe_crash_test(
        test_case: tc.TestCase, hash_str: str | None = None, *, minimized: bool = False
    ):
        postfix = "_minimized" if minimized else ""
        if hash_str is None:
            hash_str = str(hash(test_case))
        output_path = (
            config.configuration.test_case_output.crash_path
            or config.configuration.test_case_output.output_path
        )
        target_file = Path(output_path).resolve() / f"crash_test_{hash_str}{postfix}.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(test_case.to_code())

    @staticmethod
    def _create_variable_binding(
        test_case: TestCase,
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
    def _fix_result_for_pickle(result: ExecutionResult) -> None:  # noqa: C901
        """Fix the result for pickling.

        This method removes unpicklable objects from the result because it would cause
        the subprocess to crash when sending the result back to the main process.

        Args:
            result: The result to fix
        """

        def filter_bad_exceptions(bad_exceptions: Collection[Exception]) -> None:
            result.exceptions = {
                position: exception
                for position, exception in result.exceptions.items()
                if exception not in bad_exceptions
            }

        def clear_bad_exceptions() -> None:
            result.exceptions.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.exceptions,
            "Unpicklable exceptions",
            filter_bad_exceptions,
            "Failed to fix exceptions for pickle",
            clear_bad_exceptions,
        )

        def filter_bad_assertions(bad_assertions: Collection[ass.Assertion]) -> None:
            for assertions in result.assertion_trace.trace.values():
                assertions.difference_update(bad_assertions)

        def clear_bad_assertions() -> None:
            result.assertion_trace.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            list(itertools.chain(*result.assertion_trace.trace.values())),
            "Unpicklable assertions",
            filter_bad_assertions,
            "Failed to fix assertions for pickle",
            clear_bad_assertions,
        )

        def filter_bad_executed_assertions(
            bad_executed_assertions: Collection[ExecutedAssertion],
        ) -> None:
            result.execution_trace.executed_assertions = [
                assertion
                for assertion in result.execution_trace.executed_assertions
                if assertion not in bad_executed_assertions
            ]

        def clear_bad_executed_assertions() -> None:
            result.execution_trace.executed_assertions.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.execution_trace.executed_assertions,
            "Unpicklable executed assertions",
            filter_bad_executed_assertions,
            "Failed to fix executed assertions for pickle",
            clear_bad_executed_assertions,
        )

        def filter_bad_proxy_knowledges(
            bad_proxy_knowledges: Collection[tt.UsageTraceNode],
        ) -> None:
            result.proxy_knowledge = {
                position: proxy
                for position, proxy in result.proxy_knowledge.items()
                if proxy not in bad_proxy_knowledges
            }

        def clear_bad_proxy_knowledges() -> None:
            result.proxy_knowledge.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.proxy_knowledge,
            "Unpicklable proxy knowledges",
            filter_bad_proxy_knowledges,
            "Failed to fix proxy knowledges for pickle",
            clear_bad_proxy_knowledges,
        )

        def filter_bad_proper_return_type_traces(
            bad_proper_return_type_traces: Collection[ProperType],
        ) -> None:
            result.proper_return_type_trace = {
                position: proper_return_type
                for position, proper_return_type in result.proper_return_type_trace.items()
                if proper_return_type not in bad_proper_return_type_traces
            }

        def clear_bad_proper_return_type_traces() -> None:
            result.proper_return_type_trace.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.proper_return_type_trace,
            "Unpicklable proper return type traces",
            filter_bad_proper_return_type_traces,
            "Failed to fix proper return type traces for pickle",
            clear_bad_proper_return_type_traces,
        )

        def filter_bad_raw_return_type_generic_args(
            bad_raw_return_type_generic_args: Collection[type],
        ) -> None:
            result.raw_return_type_generic_args = {
                position: generic_args
                for position, generic_args in result.raw_return_type_generic_args.items()
                if all(type_ not in bad_raw_return_type_generic_args for type_ in generic_args)
            }

        def clear_bad_raw_return_type_generic_args() -> None:
            result.raw_return_type_generic_args.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.raw_return_type_generic_args,
            "Unpicklable raw return type generic args",
            filter_bad_raw_return_type_generic_args,
            "Failed to fix raw return type generic args for pickle",
            clear_bad_raw_return_type_generic_args,
        )

        def filter_bad_raw_return_types(bad_raw_return_types: Collection[type]) -> None:
            result.raw_return_types = {
                position: type_
                for position, type_ in result.raw_return_types.items()
                if type_ not in bad_raw_return_types
            }

        def clear_bad_raw_return_types() -> None:
            result.raw_return_types.clear()

        SubprocessTestCaseExecutor._fix_unpicklable(
            result.raw_return_types,
            "Unpicklable raw return types",
            filter_bad_raw_return_types,
            "Failed to fix raw return types for pickle",
            clear_bad_raw_return_types,
        )


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


# Sentinel marking an argument whose runtime value could not be resolved.
_UNRESOLVED = object()


def _find_call(
    node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
) -> cst.Call | None:
    """Return the top-level call of a statement node, if it wraps one.

    Covers ``var_0 = module_.f(...)``, ``var_0 = var_1.m(...)`` and demoted
    ``module_.f(...)`` expression statements.

    Args:
        node: The statement's CST node.

    Returns:
        The wrapped ``cst.Call``, or ``None`` if the node does not wrap one.
    """
    if not isinstance(node, cst.SimpleStatementLine) or not node.body:
        return None
    small = node.body[0]
    if not isinstance(small, cst.Assign | cst.AnnAssign | cst.Expr):
        return None
    value = small.value
    if isinstance(value, cst.Call):
        return value
    return None


def _map_args_to_params(
    call: cst.Call, signature: inspect.Signature
) -> list[tuple[int, str, inspect.Parameter]]:
    """Map each call argument to the parameter it binds.

    Keyword args resolve by name; positional args consume the signature's
    positional parameters (``POSITIONAL_ONLY`` / ``POSITIONAL_OR_KEYWORD``,
    skipping a leading ``self``) in declaration order. ``*args`` / ``**kwargs``
    expansions and unresolvable keyword args are skipped.

    Args:
        call: The call whose arguments to map.
        signature: The callable's inferred signature.

    Returns:
        A list of ``(arg_index, param_name, parameter)`` tuples.
    """
    parameters = signature.parameters
    positional = [
        param
        for param in parameters.values()
        if param.kind
        in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        and param.name != "self"
    ]
    result: list[tuple[int, str, inspect.Parameter]] = []
    pos_index = 0
    for index, arg in enumerate(call.args):
        if arg.star:
            # *args / **kwargs expansion; do not proxy.
            continue
        if arg.keyword is not None:
            name = arg.keyword.value
            param = parameters.get(name)
            if param is None:
                continue
            result.append((index, name, param))
        else:
            if pos_index >= len(positional):
                continue
            param = positional[pos_index]
            pos_index += 1
            result.append((index, param.name, param))
    return result


def _resolve_arg_value(arg: cst.Arg, namespace: dict[str, Any], renderer: cst.Module) -> Any:
    """Resolve the runtime value of a call argument in the namespace.

    A ``cst.Name`` argument is looked up directly; any other (inline literal)
    argument is evaluated against the namespace. Generated literals are
    side-effect-free and the instrumentation tracer is disabled here.

    Args:
        arg: The call argument.
        namespace: The shared execution namespace.
        renderer: A ``cst.Module`` used to render nodes to source.

    Returns:
        The resolved value, or ``_UNRESOLVED`` if it could not be obtained.
    """
    value = arg.value
    if isinstance(value, cst.Name):
        try:
            return namespace[value.value]
        except KeyError:
            return _UNRESOLVED
    try:
        return eval(renderer.code_for_node(value), namespace)  # noqa: S307
    except BaseException:  # noqa: BLE001
        return _UNRESOLVED


class RemoteTypeTracingObserver(RemoteExecutionObserver):
    """A remote execution observer used for type tracing."""

    class RemoteTypeTracingLocalState(threading.local):
        """Thread local data for type tracing."""

        def __init__(self):  # noqa: D107
            super().__init__()
            # Active proxies per statement position and argument name.
            self.proxies: dict[tuple[int, str], tt.ObjectProxy] = {}
            # Position counter, incremented once per statement. A fresh thread per
            # test case guarantees this starts at 0 and, because execution stops at
            # the first exception, equals the statement index.
            self.position: int = 0
            # Temp proxy names injected for the current statement, cleaned up in
            # after_statement_execution so proxies do not leak into later statements.
            self.current_temp_names: list[str] = []

    def __init__(self):
        """Initializes the remote observer."""
        super().__init__()
        self._local_state = RemoteTypeTracingObserver.RemoteTypeTracingLocalState()

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return dict(  # noqa: C408
            proxies=self._local_state.proxies,
        )

    @state.setter
    def state(self, state: dict[str, Any]) -> None:
        self._local_state.proxies = state["proxies"]

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def before_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
        namespace: dict[str, Any],
    ) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        position = self._local_state.position
        self._local_state.position = position + 1
        self._local_state.current_temp_names = []
        accessible = statement.accessible
        if not isinstance(accessible, gao.GenericCallableAccessibleObject):
            return node
        call = _find_call(node)
        if call is None:
            return node
        signature = accessible.inferred_signature.signature
        mapping = _map_args_to_params(call, signature)
        if not mapping:
            return node
        new_args = list(call.args)
        renderer = cst.Module(body=[])
        changed = False
        for index, name, param in mapping:
            arg = call.args[index]
            value = _resolve_arg_value(arg, namespace, renderer)
            if value is _UNRESOLVED:
                continue
            proxy = tt.ObjectProxy(
                value,
                usage_trace=tt.UsageTraceNode(name=name),
                is_kwargs=param.kind == inspect.Parameter.VAR_KEYWORD,
            )
            temp = f"_pyn_proxy_{position}_{index}"
            namespace[temp] = proxy
            self._local_state.current_temp_names.append(temp)
            self._local_state.proxies[position, name] = proxy
            new_args[index] = arg.with_changes(value=cst.Name(temp))
            changed = True
        if not changed:
            return node
        return cast(
            "cst.SimpleStatementLine | cst.BaseCompoundStatement",
            node.deep_replace(call, call.with_changes(args=new_args)),
        )

    def after_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        for temp in self._local_state.current_temp_names:
            namespace.pop(temp, None)
        self._local_state.current_temp_names = []
        if exception is None and statement.bound_variable is not None:
            bound_variable = statement.bound_variable
            if bound_variable in namespace:
                # Unwrap a possibly-proxied return value so proxies do not leak into
                # later statements. (Containers of proxies still leak.)
                namespace[bound_variable] = tt.unwrap(namespace[bound_variable])

    def after_test_case_execution(  # noqa: D102
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        for (stmt_pos, arg_name), proxy in self._local_state.proxies.items():
            result.proxy_knowledge[stmt_pos, arg_name] = copy.deepcopy(
                tt.UsageTraceNode.from_proxy(proxy)
            )


class TypeTracingObserver(ExecutionObserver):
    """An execution observer used for type tracing.

    It wraps parameters in proxies in order to make better guesses on their type.
    """

    def __init__(self, cluster: TestCluster):
        """Initializes the observer.

        Args:
            cluster: The test cluster that shall be updated by the observer
        """
        self._cluster = cluster
        self._remote_observer = RemoteTypeTracingObserver()

    @property
    def remote_observer(self) -> RemoteTypeTracingObserver:  # noqa: D102
        return self._remote_observer

    def before_remote_test_case_execution(self, test_case: TestCase) -> None:
        """Not used.

        Args:
            test_case: Not used
        """

    def after_remote_test_case_execution(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        for (stmt_pos, arg_name), knowledge in result.proxy_knowledge.items():
            statement = test_case.get_statement(stmt_pos)
            call_acc = getattr(statement, "accessible", None)
            if isinstance(call_acc, gao.GenericCallableAccessibleObject):
                self._cluster.update_parameter_knowledge(
                    call_acc,
                    arg_name,
                    knowledge,
                )
