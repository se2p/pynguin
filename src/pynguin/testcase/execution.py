#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Contains all code related to test-case execution."""

from __future__ import annotations

import abc
import ast
import contextlib
import copy
import dataclasses
import inspect
import logging
import os
import sys
import threading

from abc import abstractmethod
from importlib import reload
from queue import Empty
from queue import Queue
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar
from typing import cast

# Needs to be loaded, i.e., in sys.modules for the execution of assertions to work.
import pytest  # noqa: F401

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_to_ast as ass_to_ast
import pynguin.assertion.assertion_trace as at
import pynguin.configuration as config
import pynguin.testcase.statement as stmt
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.namingscope as ns
import pynguin.utils.opcodes as op
import pynguin.utils.typetracing as tt

from pynguin.analyses.typesystem import ANY
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TupleType
from pynguin.instrumentation.instrumentation import ArtificialInstr
from pynguin.instrumentation.instrumentation import CheckedCoverageInstrumentation
from pynguin.instrumentation.instrumentation import InstrumentationTransformer
from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.instrumentation.tracer import InstrumentationExecutionTracer
from pynguin.testcase.mocking import mocks_to_use
from pynguin.utils.mirror import Mirror


immutable_types = (int, float, complex, str, tuple, frozenset, bytes)

if TYPE_CHECKING:
    from types import MappingProxyType
    from types import ModuleType

    from bytecode import BasicBlock

    import pynguin.testcase.testcase as tc

    from pynguin.analyses import module


_LOGGER = logging.getLogger(__name__)


class ExecutionContext:
    """Contains information required in the context of an execution.

    The context contains, e.g., the used variables, modules, and the AST representation
    of the statements that should be executed.
    """

    def __init__(self, module_provider: ModuleProvider) -> None:
        """Create a new execution context.

        Args:
            module_provider: The used module provider
        """
        self._module_provider = module_provider
        self._local_namespace: dict[str, Any] = {}
        self._variable_names = ns.NamingScope()
        self._module_aliases = ns.NamingScope(
            prefix="module", new_name_callback=self.add_new_module_alias
        )
        self._global_namespace: dict[str, ModuleType] = {}

    @property
    def local_namespace(self) -> dict[str, Any]:
        """The local namespace.

        Returns:
            The local namespace
        """
        return self._local_namespace

    def replace_variable_value(self, variable: vr.VariableReference, new_value: Any) -> None:
        """Replace the value of the variable with the new value.

        Args:
            variable: The variable for which we want to replace the value
            new_value: The replacement value.
        """
        self._local_namespace[self._variable_names.get_name(variable)] = new_value

    @property
    def module_aliases(self) -> ns.NamingScope:
        """The module aliases.

        Returns:
            A naming scope that maps the used modules to their alias.
        """
        return self._module_aliases

    @property
    def variable_names(self) -> ns.NamingScope:
        """The variable names.

        Returns:
            A naming scope that maps the used variables to their names.
        """
        return self._variable_names

    def get_reference_value(self, reference: vr.Reference) -> Any:
        """Resolve the given reference in this execution context.

        Args:
            reference: The reference to resolve.

        Raises:
            ValueError: If the root of the reference can not be resolved.

        Returns:
            The value that is resolved.
        """
        root, *attrs = reference.get_names(self._variable_names, self._module_aliases)
        if root in self._local_namespace:
            # Check local namespace first
            res = self._local_namespace[root]
        elif root in self._global_namespace:
            # Check global namespace after
            res = self._global_namespace[root]
        else:
            # Root name is not defined?
            raise ValueError("Root not found in this context: " + root)
        for attr in attrs:
            res = getattr(res, attr)
        return res

    @property
    def global_namespace(self) -> dict[str, ModuleType]:
        """The global namespace.

        Returns:
            The global namespace
        """
        return self._global_namespace

    def node_for_statement(
        self,
        statement: stmt.Statement,
    ) -> ast.stmt:
        """Transforms the given statement in an executable ast node.

        Args:
            statement: The statement that should be converted.

        Returns:
            An ast node.
        """
        stmt_visitor = stmt_to_ast.StatementToAstVisitor(self._module_aliases, self._variable_names)
        statement.accept(stmt_visitor)
        return stmt_visitor.ast_node

    def node_for_assertion(self, assertion: ass.Assertion, statement_node: ast.stmt) -> ast.stmt:
        """Transforms the given assertion in an executable ast node.

        Args:
            assertion: The assertion that should be converted.
            statement_node: The ast node of the statement for the assertion.

        Returns:
            An ast node.
        """
        common_modules: set[str] = set()
        ass_visitor = ass_to_ast.PyTestAssertionToAstVisitor(
            self._variable_names, self._module_aliases, common_modules, statement_node
        )
        assertion.accept(ass_visitor)
        for common in common_modules:
            if common not in self.global_namespace:
                self.add_new_module_alias(common, common)

        if isinstance(assertion, ass.ExceptionAssertion):
            assert len(ass_visitor.nodes) == 1
            return ass_visitor.nodes[0]
        assert len(ass_visitor.assertion_nodes) == 1
        return ass_visitor.assertion_nodes[0]

    @staticmethod
    def wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, such that it can be executed.

        Args:
            node: The node to wrap

        Returns:
            The module wrapping the nodes
        """
        ast.fix_missing_locations(node)
        return ast.Module(body=[node], type_ignores=[])

    def add_new_module_alias(self, module_name: str, alias: str) -> None:
        """Add a new module alias.

        Args:
            module_name: The name of the module
            alias: The alias
        """
        self._global_namespace[alias] = self._module_provider.get_module(module_name)


class ExecutionObserver:
    """An Observer that can be used to observe the execution of a test case.

    Important Note: If an observer is stateful, then this state must be encapsulated
    in a threading.local, i.e., be bound to a thread. Note that thread local data
    is initialized per thread, so there is no need to clear any pre-existing data
    (because there is none), as every thread gets its own instance.

    Methods that are called from within the thread are not allowed to interact with the
    'outside'. The only thing that should leave an observer are results when they are
    written to the execution result in
    ExecutionObserver::after_test_case_execution_inside_thread.

    You may interact with the 'outside' in
    ExecutionObserver::after_test_case_execution_outside_thread.

    Note: Usage of threading.local may interfere with debugging tools, such as pydevd.
    In such a case, disable Cython by setting the following environment variable:
    PYDEVD_USE_CYTHON=NO

    For more details, look at some implementations, e.g., AssertionTraceObserver.
    """

    @abstractmethod
    def before_test_case_execution(self, test_case: tc.TestCase):
        """Called before test case execution.

        Args:
            test_case: The test cases that will be executed.
        """

    @abstractmethod
    def after_test_case_execution_inside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Called after test case execution.

        The call happens from inside the thread that executed the test case. You should
        override this method to extract information from the thread local storage to the
        execution result.

        Note: When a thread times out, then this method might not be called at all.

        Args:
            test_case: The test cases that was executed
            result: The execution result
        """

    @abstractmethod
    def after_test_case_execution_outside_thread(
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

    @abstractmethod
    def before_statement_execution(
        self, statement: stmt.Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        """Called before a statement is executed.

        Args:
            statement: the statement about to be executed.
            node: the ast node representing the statement.
            exec_ctx: the current execution context.

        Returns:
            An ast node. You may choose to modify this node to change what is executed.
        """

    @abstractmethod
    def after_statement_execution(
        self,
        statement: stmt.Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        """Called after a statement was executed.

        Args:
            statement: the statement that was executed.
            executor: the executor, in case you want to execute something.
            exec_ctx: the current execution context.
            exception: the exception that was thrown, if any.
        """


class AssertionExecutionObserver(ExecutionObserver):
    """An observer which executes the assertions of statements.

    Enables slicing on the recorded data.
    """

    def __init__(self, tracer: ExecutionTracer):
        """Instantiates a new observer.

        Args:
            tracer: The execution tracer used for tracing
        """
        self._tracer = tracer

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: not used
        """

    def after_test_case_execution_inside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Not used.

        Args:
            test_case: Not used
            result: Not used
        """

    def after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Not used.

        Args:
            test_case: Not used
            result: Not used
        """

    def before_statement_execution(  # noqa: D102
        self, statement: stmt.Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        return node

    def after_statement_execution(  # noqa: D102
        self,
        statement: stmt.Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        # This is a bit cumbersome, because the tracer is disabled by default.
        enabled = False
        try:
            if self._tracer.is_disabled():
                enabled = True
                self._tracer.enable()

            if statement.has_only_exception_assertion():
                if exception is not None:
                    self._tracer.register_exception_assertion(statement)
                return

            for assertion in statement.assertions:
                assertion_node = exec_ctx.wrap_node_in_module(
                    exec_ctx.node_for_assertion(assertion, ast.stmt())  # Dummy node
                )
                executor.execute_ast(assertion_node, exec_ctx)

                code_object_id, node_id = self._get_assertion_node_and_code_object_ids()
                self._tracer.register_assertion_position(code_object_id, node_id, assertion)
        finally:
            if enabled:
                # Restore old state
                self._tracer.disable()

    def _get_assertion_node_and_code_object_ids(self) -> tuple[int, int]:
        existing_code_objects = self._tracer.get_subject_properties().existing_code_objects
        code_object_id = len(existing_code_objects) - 1
        code_object = existing_code_objects[code_object_id]
        assert_node = None
        for node in code_object.cfg.nodes:
            if node.is_artificial:
                continue
            bb_node: BasicBlock = node.basic_block  # type: ignore[assignment]
            if (
                not isinstance(bb_node[-1], ArtificialInstr)
                and bb_node[-1].opcode == op.POP_JUMP_IF_TRUE  # type:ignore[union-attr]
            ):
                assert_node = node
        assert assert_node
        return code_object_id, assert_node.index


class ReturnTypeObserver(ExecutionObserver):
    """Observes the runtime types seen during execution.

    Updates the return types of the called function with the observed types.
    """

    class ReturnTypeLocalState(threading.local):
        """Encapsulate observed return types."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.return_type_trace: dict[int, type] = {}
            self.return_type_generic_args: dict[int, tuple[type, ...]] = {}

    def __init__(self, test_cluster: module.TestCluster):
        """Initializes the observer.

        Args:
            test_cluster: The test cluster that shall be updated
        """
        self._return_type_local_state = ReturnTypeObserver.ReturnTypeLocalState()

        # Non-local state
        self._test_cluster = test_cluster

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_test_case_execution_inside_thread(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        result.raw_return_types = dict(self._return_type_local_state.return_type_trace)
        result.raw_return_type_generic_args = dict(
            self._return_type_local_state.return_type_generic_args
        )

    def after_test_case_execution_outside_thread(  # noqa: D102
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
            if isinstance(statement, stmt.ParametrizedStatement):
                call_acc = statement.accessible_object()
                assert isinstance(call_acc, gao.GenericCallableAccessibleObject)
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

    def before_statement_execution(  # noqa: D102
        self, statement: stmt.Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        return node  # not relevant

    def after_statement_execution(  # noqa: D102
        self,
        statement: stmt.Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        if exception is None and (ret_val := statement.ret_val) is not None:
            value = exec_ctx.get_reference_value(ret_val)
            position = statement.get_position()
            self._return_type_local_state.return_type_trace[position] = type(value)
            # TODO(fk) Hardcoded support for generics.
            # Try to guess generic arguments from elements.

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

    T = TypeVar("T")

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
    def __get_sys_module(module_name: str) -> ModuleType:
        try:
            return sys.modules[module_name]
        except KeyError as error:
            try:
                package_name, submodule_name = module_name.rsplit(".", 1)
            except ValueError as e:
                raise error from e

            try:
                package = ModuleProvider.__get_sys_module(package_name)
            except KeyError as e:
                raise error from e

            try:
                submodule = getattr(package, submodule_name)
            except AttributeError as e:
                raise error from e

            if not inspect.ismodule(submodule):
                raise error

            return submodule

    def get_module(self, module_name: str) -> ModuleType:
        """Provides a module.

        Either from sys.modules or if a mutated version for the given module name exists
        then the mutated version of the module will be returned.

        Args:
            module_name: string for the module alias, which should be loaded

        Returns:
            the module which should be loaded.
        """
        if (mutated_module := self._mutated_module_aliases.get(module_name, None)) is not None:
            retrieved_module = mutated_module
        else:
            retrieved_module = self.__get_sys_module(module_name)
        self.mock_module(retrieved_module)
        return retrieved_module

    @staticmethod
    def mock_module(
        module_to_mock: ModuleType, mocks: MappingProxyType[str, ModuleType] = mocks_to_use
    ) -> None:
        """Mock all dangerous methods of the given module, such as logging.

        Args:
            module_to_mock: The module to mock.
            mocks: The mocks to use.
        """
        for module_to_mock_name, mock in mocks.items():
            if hasattr(module_to_mock, module_to_mock_name):
                setattr(module_to_mock, module_to_mock_name, mock)

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

    @staticmethod
    def reload_module(module_name: str) -> None:
        """Reloads the given module.

        Args:
            module_name: the module to reload.
        """
        reload(ModuleProvider.__get_sys_module(module_name))


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
    def temporarily_add_observer(self, observer: ExecutionObserver):
        """Temporarily add the given observer.

        Args:
            observer: The observer to add.
        """

    @property
    @abstractmethod
    def tracer(self) -> ExecutionTracer:
        """Provide access to the execution tracer.

        Returns:
            The execution tracer
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


class TestCaseExecutor(AbstractTestCaseExecutor):
    """An executor that executes the generated test cases."""

    def __init__(
        self,
        tracer: ExecutionTracer,
        module_provider: ModuleProvider | None = None,
        maximum_test_execution_timeout: int = 5,
        test_execution_time_per_statement: int = 1,
    ) -> None:
        """Create new test case executor.

        Args:
            tracer: the execution tracer
            module_provider: The used module provider
            maximum_test_execution_timeout: The minimum timeout time (in seconds)
                before a test case execution times out.
            test_execution_time_per_statement: The amount of time (in seconds) that is
                added to the timeout per statement, up to minimum_test_execution_timeout
        """
        # Repeatedly opening/closing devnull caused problems.
        # This is closed when Pynguin terminates, since we don't need this output
        # anyway this is acceptable.
        self._null_file = open(os.devnull, mode="w")  # noqa: PLW1514, PTH123, SIM115

        self._maximum_test_execution_timeout = maximum_test_execution_timeout
        self._test_execution_time_per_statement = test_execution_time_per_statement

        self._module_provider = module_provider if module_provider is not None else ModuleProvider()
        self._tracer = tracer
        self._observers: list[ExecutionObserver] = []
        self._instrument = (
            config.CoverageMetric.CHECKED in config.configuration.statistics_output.coverage_metrics
        )
        instrumentation_tracer = InstrumentationExecutionTracer(self._tracer)
        checked_instrumentation = CheckedCoverageInstrumentation(instrumentation_tracer)
        self._checked_transformer = InstrumentationTransformer(
            instrumentation_tracer, [checked_instrumentation]
        )

        def log_thread_exception(arg):
            _LOGGER.error(
                "Exception in Thread: %s",
                arg.thread,
                exc_info=(arg.exc_type, arg.exc_value, arg.exc_traceback),  # noqa: LOG014
            )

        # Set our own exception hook, so timeout related errors in executing threads
        # are not spilled out to stderr and clutter our formatted output but are send
        # to the logger
        threading.excepthook = log_thread_exception

    @property
    def module_provider(self) -> ModuleProvider:
        """The module provider used by this executor.

        Returns:
            The used module provider
        """
        return self._module_provider

    def add_observer(self, observer: ExecutionObserver) -> None:
        """Add an execution observer.

        Args:
            observer: the observer to be added.
        """
        self._observers.append(observer)

    def clear_observers(self) -> None:
        """Remove all existing observers."""
        self._observers.clear()

    @contextlib.contextmanager
    def temporarily_add_observer(self, observer: ExecutionObserver):  # noqa: D102
        self._observers.append(observer)
        yield
        self._observers.remove(observer)

    @property
    def tracer(self) -> ExecutionTracer:
        """Provide access to the execution tracer.

        Returns:
            The execution tracer
        """
        return self._tracer

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
        with (
            contextlib.redirect_stdout(self._null_file),
            contextlib.redirect_stderr(self._null_file),
        ):
            return_queue: Queue[ExecutionResult] = Queue()
            thread = threading.Thread(
                target=self._execute_test_case,
                args=(test_case, return_queue),
                daemon=True,
            )
            thread.start()
            thread.join(
                timeout=min(
                    self._maximum_test_execution_timeout,
                    self._test_execution_time_per_statement * len(test_case.statements),
                )
            )
            if thread.is_alive():
                # Set thread ident to invalid value, such that the tracer
                # kills the thread
                self._tracer.current_thread_identifier = -1
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
        self._after_test_case_execution_outside_thread(test_case, result)
        return result

    def _before_test_case_execution(self, test_case: tc.TestCase) -> None:
        self._tracer.init_trace()
        for observer in self._observers:
            observer.before_test_case_execution(test_case)

    def _execute_test_case(self, test_case: tc.TestCase, result_queue: Queue) -> None:
        self._before_test_case_execution(test_case)
        result = ExecutionResult()
        exec_ctx = ExecutionContext(self._module_provider)
        self._tracer.current_thread_identifier = threading.current_thread().ident
        for idx, statement in enumerate(test_case.statements):
            ast_node = self._before_statement_execution(statement, exec_ctx)
            exception = self.execute_ast(ast_node, exec_ctx)
            self._after_statement_execution(statement, exec_ctx, exception)
            if exception is not None:
                result.report_new_thrown_exception(idx, exception)
                break
        self._after_test_case_execution_inside_thread(test_case, result)
        result_queue.put(result)

    def _after_test_case_execution_inside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Collect the trace data after each executed test case.

        Args:
            test_case: The executed test case
            result: The execution result
        """
        result.execution_trace = self._tracer.get_trace()
        for observer in self._observers:
            observer.after_test_case_execution_inside_thread(test_case, result)

    def _after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Process results outside of thread.

        Args:
            test_case: The executed test case
            result: The execution result
        """
        for observer in self._observers:
            observer.after_test_case_execution_outside_thread(test_case, result)

    def _before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ) -> ast.Module:
        # Check if the current thread is still the one that should be executing
        # Otherwise raise an exception to kill it.
        if self.tracer.current_thread_identifier != threading.current_thread().ident:
            # Kill this thread
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        # We need to disable the tracer, because an observer might interact with an
        # object of the SUT via the ExecutionContext and trigger code execution, which
        # is not caused by the test case and should therefore not be in the trace.
        self._tracer.disable()

        ast_node = exec_ctx.node_for_statement(statement)
        try:
            for observer in self._observers:
                ast_node = observer.before_statement_execution(statement, ast_node, exec_ctx)
        finally:
            self._tracer.enable()
        return ExecutionContext.wrap_node_in_module(ast_node)

    def execute_ast(
        self,
        ast_node: ast.Module,
        exec_ctx: ExecutionContext,
    ) -> BaseException | None:
        """Execute the given ast_node in the given context.

        You can use this in an observer if you also need to execute an AST Node.

        Args:
            ast_node: The node to execute.
            exec_ctx: The execution context

        Returns:
            The raised exception, if any.
        """
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Executing %s", ast.unparse(ast_node))

        code = compile(ast_node, "<ast>", "exec")
        if self._instrument:
            code = self._checked_transformer.instrument_module(code)

        try:
            exec(  # noqa: S102
                code, exec_ctx.global_namespace, exec_ctx.local_namespace
            )
        except BaseException as err:  # noqa: BLE001
            failed_stmt = ast.unparse(ast_node)
            _LOGGER.debug("Failed to execute statement:\n%s%s", failed_stmt, err.args)
            return err

        return None

    def _after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ):
        # See comments in _before_statement_execution
        if self.tracer.current_thread_identifier != threading.current_thread().ident:
            # Kill this thread
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        self._tracer.disable()
        try:
            for observer in reversed(self._observers):
                observer.after_statement_execution(statement, self, exec_ctx, exception)
        finally:
            self._tracer.enable()


class TypeTracingTestCaseExecutor(AbstractTestCaseExecutor):
    """A test case executor that delegates to another executor.

    Every test case is executed twice, one time for the regular result
    and one time with proxies in order to refine parameter types.
    """

    def __init__(self, delegate: AbstractTestCaseExecutor, cluster: module.ModuleTestCluster):
        """Initializes the executor.

        Args:
            delegate: The delegate
            cluster: The test cluster
        """
        self._delegate = delegate
        self._type_tracing_observer = TypeTracingObserver(cluster)
        self._return_type_observer = ReturnTypeObserver(cluster)

    @property
    def module_provider(self) -> ModuleProvider:  # noqa: D102
        return self._delegate.module_provider

    def add_observer(self, observer: ExecutionObserver) -> None:  # noqa: D102
        self._delegate.add_observer(observer)

    def clear_observers(self) -> None:  # noqa: D102
        self._delegate.clear_observers()

    @property
    def tracer(self) -> ExecutionTracer:  # noqa: D102
        return self._delegate.tracer

    def execute(self, test_case: tc.TestCase) -> ExecutionResult:  # noqa: D102
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
                self._delegate.execute(test_case)
        return result

    def temporarily_add_observer(self, observer: ExecutionObserver):  # noqa: D102
        pass


class TypeTracingObserver(ExecutionObserver):
    """An execution observer used for type tracing.

    It wraps parameters in proxies in order to make better guesses on their type.
    """

    class TypeTracingLocalState(threading.local):
        """Thread local data for type tracing."""

        def __init__(self):  # noqa: D107
            super().__init__()
            # Active proxies per statement position and argument name.
            self.proxies: dict[tuple[int, str], tt.ObjectProxy] = {}

    def __init__(self, cluster: module.TestCluster):
        """Initializes the observer.

        Args:
            cluster: The test cluster that shall be updated by the observer
        """
        self._local_state = TypeTracingObserver.TypeTracingLocalState()
        self._cluster = cluster

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_test_case_execution_inside_thread(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        for (stmt_pos, arg_name), proxy in self._local_state.proxies.items():
            result.proxy_knowledge[stmt_pos, arg_name] = copy.deepcopy(
                tt.UsageTraceNode.from_proxy(proxy)
            )

    def after_test_case_execution_outside_thread(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        for (stmt_pos, arg_name), knowledge in result.proxy_knowledge.items():
            statement = test_case.get_statement(stmt_pos)
            assert isinstance(statement, stmt.ParametrizedStatement)
            self._cluster.update_parameter_knowledge(
                cast("gao.GenericCallableAccessibleObject", statement.accessible_object()),
                arg_name,
                knowledge,
            )

    def before_statement_execution(  # noqa: D102
        self, statement: stmt.Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        if isinstance(statement, stmt.ParametrizedStatement):
            modified_args = {}
            real_params = {}
            for name, param in statement.args.items():
                mod_param = vr.VariableReference(statement.test_case, ANY)
                modified_args[name] = mod_param
                real_params[name, mod_param] = param

            # We must rewrite calls as follows:
            # `foo(arg1, arg2, arg2) -> foo(n_arg1, n_arg2, n_arg3)`
            # where
            #   `n_arg1 = Proxy(arg1)`
            #   `n_arg2 = Proxy(arg2)`
            #   `n_arg3 = Proxy(arg2)`
            # In other words, each argument is wrapped in its own proxy, even if they
            # point to the same variable.
            modified = cast(
                "stmt.ParametrizedStatement",
                statement.clone(statement.test_case, Mirror()),
            )
            signature = cast(
                "gao.GenericCallableAccessibleObject", modified.accessible_object()
            ).inferred_signature
            modified.args = modified_args
            modified.ret_val = statement.ret_val
            visitor = stmt_to_ast.StatementToAstVisitor(
                exec_ctx.module_aliases, exec_ctx.variable_names
            )
            modified.accept(visitor)
            # Now we know the names.
            for (name, modified_param), original_param in real_params.items():
                old = exec_ctx.get_reference_value(original_param)
                # TODO(fk) use proxy only with some chance?
                #  May be necessary for functions that don't like proxies, e.g.,
                #  open(...).
                #  Record how often we get type errors to find out how often
                #  native function are a problem?
                #  can't really do that, because we use proxies as markers for
                #  interactions we don't want to record.
                proxy = tt.ObjectProxy(
                    old,
                    usage_trace=tt.UsageTraceNode(name=name),
                    is_kwargs=signature.signature.parameters[name].kind
                    == inspect.Parameter.VAR_KEYWORD,
                )
                self._local_state.proxies[statement.get_position(), name] = proxy
                exec_ctx.replace_variable_value(modified_param, proxy)

            return visitor.ast_node
        return node

    def after_statement_execution(  # noqa: D102
        self,
        statement: stmt.Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None = None,
    ) -> None:
        if exception is None:
            # It may be possible that the returned value is a proxy, but we don't
            # want to create nested proxies, so we unwrap it.
            # This does not solve all problems, e.g., a list containing proxies, so
            # that's a limitation.
            assert statement.ret_val
            value = exec_ctx.get_reference_value(statement.ret_val)
            exec_ctx.replace_variable_value(statement.ret_val, tt.unwrap(value))
