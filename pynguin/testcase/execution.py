#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Contains all code related to test-case execution."""
from __future__ import annotations

import ast
import contextlib
import dataclasses
import inspect
import logging
import os
import sys
import threading
from abc import abstractmethod
from dataclasses import dataclass, field
from importlib import reload
from math import inf
from queue import Empty, Queue
from types import BuiltinFunctionType, BuiltinMethodType, ModuleType
from typing import TYPE_CHECKING, Any, Sized, TypeVar, Union

# Needs to be loaded, i.e., in sys.modules for the execution of assertions to work.
import pytest  # pylint:disable=unused-import,import-outside-toplevel # noqa: F401
from bytecode import BasicBlock, CellVar, Compare, FreeVar
from jellyfish import levenshtein_distance
from ordered_set import OrderedSet

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_to_ast as ass_to_ast
import pynguin.slicer.executedinstruction as ei
import pynguin.assertion.assertion_trace as at
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.utils.namingscope as ns
import pynguin.utils.opcodes as op
from pynguin.instrumentation.instrumentation import (
    ArtificialInstr,
    CheckedCoverageInstrumentation,
    CodeObjectMetaData,
    InstrumentationTransformer,
    PredicateMetaData,
)
from pynguin.slicer.dynamicslicer import SlicingCriterion
from pynguin.slicer.executionflowbuilder import UniqueInstruction
from pynguin.utils.type_utils import (
    given_exception_matches,
    is_bytes,
    is_numeric,
    is_string,
)

immutable_types = (int, float, complex, str, tuple, frozenset, bytes)

if TYPE_CHECKING:
    import pynguin.testcase.statement as stmt
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.variablereference as vr


_logger = logging.getLogger(__name__)


class ExecutionContext:
    """Contains information required in the context of an execution.
    e.g. the used variables, modules and
    the AST representation of the statements that should be executed."""

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

    @property
    def module_aliases(self) -> ns.NamingScope:
        """The module aliases

        Returns:
            A naming scope that maps the used modules to their alias.
        """
        return self._module_aliases

    @property
    def variable_names(self) -> ns.NamingScope:
        """The module aliases

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
        stmt_visitor = stmt_to_ast.StatementToAstVisitor(
            self._module_aliases, self._variable_names
        )
        statement.accept(stmt_visitor)
        ast_stmt = stmt_visitor.ast_node
        return ast_stmt

    def node_for_assertion(
        self, assertion: ass.Assertion, statement_node: ast.stmt
    ) -> ast.stmt:
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
        """Add a new module alias

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
        """Called after test case execution from inside the thread that executed
        the test case. You should override this method to extract information from the
        thread local storage to the execution result.

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
        """
        Called after a statement was executed.

        Args:
            statement: the statement that was executed.
            executor: the executor, in case you want to execute something.
            exec_ctx: the current execution context.
            exception: the exception that was thrown, if any.
        """


class AssertionSlicingObserver(ExecutionObserver):
    """An observer which executes the assertions of statements to enable slicing on
    the recorded data."""

    def __init__(self, tracer: ExecutionTracer):
        self._tracer = tracer

    def before_test_case_execution(self, test_case: tc.TestCase):
        pass

    def after_test_case_execution_inside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        pass

    def after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        pass

    def before_statement_execution(
        self, statement: stmt.Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        return node

    def after_statement_execution(
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
                executor.execute_ast(assertion_node, exec_ctx, True)

                code_object_id, node_id = self._get_assertion_node_and_code_object_ids()
                self._tracer.register_assertion_position(
                    code_object_id, node_id, assertion
                )
        finally:
            if enabled:
                # Restore old state
                self._tracer.disable()

    def _get_assertion_node_and_code_object_ids(self) -> tuple[int, int]:
        existing_code_objects = self._tracer.get_known_data().existing_code_objects
        code_object_id = len(existing_code_objects) - 1
        code_object = existing_code_objects[code_object_id]
        assert_node = None
        for node in code_object.cfg.nodes:
            if node.is_artificial:
                continue
            bb_node: BasicBlock = node.basic_block
            if (
                not isinstance(bb_node[-1], ArtificialInstr)
                and bb_node[-1].opcode == op.POP_JUMP_IF_TRUE
            ):
                assert_node = node
        assert assert_node
        return code_object_id, assert_node.index


class ReturnTypeObserver(ExecutionObserver):
    """Observes the runtime types seen during execution."""

    class ReturnTypeLocalState(
        threading.local
    ):  # pylint:disable=too-few-public-methods
        """Encapsulate observed return types."""

        def __init__(self):
            super().__init__()
            self.return_type_trace: dict[int, type] = {}

    def __init__(self):
        self._return_type_local_state = ReturnTypeObserver.ReturnTypeLocalState()

    def before_test_case_execution(self, test_case: tc.TestCase):
        pass

    def after_test_case_execution_inside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        result.return_type_trace = dict(self._return_type_local_state.return_type_trace)

    def after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        pass

    def before_statement_execution(
        self, statement: stmt.Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        return node  # not relevant

    def after_statement_execution(
        self,
        statement: stmt.Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        if (
            exception is None
            and (ret_val := statement.ret_val) is not None
            and not ret_val.is_none_type()
        ):
            self._return_type_local_state.return_type_trace[
                statement.get_position()
            ] = type(exec_ctx.get_reference_value(ret_val))


@dataclass
class ExecutionTrace:  # pylint: disable=too-many-instance-attributes
    """Stores trace information about the execution."""

    _logger = logging.getLogger(__name__)

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: dict[int, int] = field(default_factory=dict)
    true_distances: dict[int, float] = field(default_factory=dict)
    false_distances: dict[int, float] = field(default_factory=dict)
    covered_line_ids: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_instructions: list[ei.ExecutedInstruction] = field(default_factory=list)
    executed_assertions: list[ExecutedAssertion] = field(default_factory=list)
    checked_lines: OrderedSet[int] = field(default_factory=OrderedSet)

    def merge(self, other: ExecutionTrace) -> None:
        """Merge the values from the other execution trace.

        Args:
            other: Merges the other traces into this trace
        """
        self.executed_code_objects.update(other.executed_code_objects)
        for key, value in other.executed_predicates.items():
            self.executed_predicates[key] = self.executed_predicates.get(key, 0) + value
        self._merge_min(self.true_distances, other.true_distances)
        self._merge_min(self.false_distances, other.false_distances)
        self.covered_line_ids.update(other.covered_line_ids)
        self.checked_lines.update(other.checked_lines)
        shift: int = len(self.executed_instructions)
        self.executed_instructions.extend(other.executed_instructions)
        for traced_assertion in other.executed_assertions:
            self.executed_assertions.append(
                ExecutedAssertion(
                    traced_assertion.code_object_id,
                    traced_assertion.node_id,
                    traced_assertion.trace_position + shift,
                    traced_assertion.assertion,
                )
            )

    @staticmethod
    def _merge_min(target: dict[int, float], source: dict[int, float]) -> None:
        """Merge source into target. Minimum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = min(target.get(key, inf), value)

    def update_predicate_distances(
        self, distance_true: float, distance_false: float, predicate: int
    ) -> None:
        """Update the distances and predicate execution count.

        Args:
            distance_true: the measured true distance
            distance_false: the measured false distance
            predicate: the predicate id
        """
        self.executed_predicates[predicate] = (
            self.executed_predicates.get(predicate, 0) + 1
        )
        self.true_distances[predicate] = min(
            self.true_distances.get(predicate, inf), distance_true
        )
        self.false_distances[predicate] = min(
            self.false_distances.get(predicate, inf), distance_false
        )

    def add_instruction(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Creates a new ExecutedInstruction object and adds it to the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
        """
        executed_instr = ei.ExecutedInstruction(
            module, code_object_id, node_id, opcode, None, lineno, offset
        )
        self.executed_instructions.append(executed_instr)

    def add_memory_instruction(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg_name: str,
        arg_address: int,
        is_mutable_type: bool,
        object_creation: bool,
    ) -> None:
        """Creates a new ExecutedMemoryInstruction object and adds it to the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            arg_name: the name of the argument
            arg_address: the memory address of the argument
            is_mutable_type: if the argument is mutable
            object_creation: if the instruction creates the object used
        """
        executed_instr = ei.ExecutedMemoryInstruction(
            module,
            code_object_id,
            node_id,
            opcode,
            arg_name,
            lineno,
            offset,
            arg_address,
            is_mutable_type,
            object_creation,
        )
        self.executed_instructions.append(executed_instr)

    def add_attribute_instruction(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        attr_name: str,
        src_address: int,
        arg_address: int,
        is_mutable_type: bool,
    ) -> None:
        """Creates a new ExecutedAttributeInstruction object and
        adds it to the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            attr_name: the name of the accessed attribute
            src_address: the memory address of the attribute
            arg_address: the memory address of the argument
            is_mutable_type: if the attribute is mutable
        """
        executed_instr = ei.ExecutedAttributeInstruction(
            module,
            code_object_id,
            node_id,
            opcode,
            attr_name,
            lineno,
            offset,
            src_address,
            arg_address,
            is_mutable_type,
        )
        self.executed_instructions.append(executed_instr)

    def add_jump_instruction(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        target_id: int,
    ) -> None:
        """Creates a new ExecutedControlInstruction object and adds it to the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            target_id: the target offset to jump to
        """
        executed_instr = ei.ExecutedControlInstruction(
            module, code_object_id, node_id, opcode, target_id, lineno, offset
        )
        self.executed_instructions.append(executed_instr)

    def add_call_instruction(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: int,
    ) -> None:
        """Creates a new ExecutedCallInstruction object and adds it to the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            arg: the argument to the instruction
        """
        executed_instr = ei.ExecutedCallInstruction(
            module, code_object_id, node_id, opcode, arg, lineno, offset
        )

        self.executed_instructions.append(executed_instr)

    def add_return_instruction(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Creates a new ExecutedReturnInstruction object and adds it to the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
        """
        executed_instr = ei.ExecutedReturnInstruction(
            module, code_object_id, node_id, opcode, None, lineno, offset
        )

        self.executed_instructions.append(executed_instr)


@dataclasses.dataclass
class ExecutionResult:
    """Result of an execution."""

    timeout: bool = False
    exceptions: dict[int, BaseException] = dataclasses.field(
        default_factory=dict, init=False
    )
    assertion_trace: at.AssertionTrace = dataclasses.field(
        default_factory=at.AssertionTrace, init=False
    )
    assertion_verification_trace: at.AssertionVerificationTrace = dataclasses.field(
        default_factory=at.AssertionVerificationTrace, init=False
    )
    execution_trace: ExecutionTrace = dataclasses.field(
        default_factory=ExecutionTrace, init=False
    )
    return_type_trace: dict[int, type] = dataclasses.field(
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
        """It may happen that the test case is modified after execution, for example,
        by removing unused primitives. We have to update the execution result to reflect
        this, otherwise the indexes maybe wrong.

        Args:
            deleted_statements: The indexes of the deleted statements
        """
        self.return_type_trace = ExecutionResult.shift_dict(
            self.return_type_trace, deleted_statements
        )
        self.exceptions = ExecutionResult.shift_dict(
            self.exceptions, deleted_statements
        )

    T = TypeVar("T")

    @staticmethod
    def shift_dict(to_shift: dict[int, T], deleted_indexes: set[int]) -> dict[int, T]:
        """Shifts the entries in the given dictionary by computing their new positions
        after the given statements were deleted.

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
        return (
            f"ExecutionResult(exceptions: {self.exceptions}, "
            + f"trace: {self.execution_trace})"
        )

    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class LineMetaData:
    """Stores meta data of a line."""

    # id of the code object where the line is first defined
    code_object_id: int

    # name of the file containing a line
    file_name: str

    # Line number where the predicate is defined.
    line_number: int

    def __hash__(self):
        # code object id is not checked since file
        # and line number are the unique identifiers
        return 31 + self.line_number + hash(self.file_name)

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, LineMetaData):
            return False
        # code object id is not checked since file
        # and line number are the unique identifiers
        return (
            self.line_number == other.line_number and self.file_name == other.file_name
        )


@dataclass
class KnownData:
    """Contains known code objects and predicates.
    FIXME(fk) better class name...
    """

    # Maps all known ids of Code Objects to meta information
    existing_code_objects: dict[int, CodeObjectMetaData] = field(default_factory=dict)

    # Stores which of the existing code objects do not contain a branch, i.e.,
    # they do not contain a predicate. Every code object is initially seen as
    # branch-less until a predicate is registered for it.
    branch_less_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)

    # Maps all known ids of predicates to meta information
    existing_predicates: dict[int, PredicateMetaData] = field(default_factory=dict)

    # stores which line id represents which line in which file
    existing_lines: dict[int, LineMetaData] = field(default_factory=dict)

    # stores known memory attribute object addresses
    object_addresses: OrderedSet[int] = field(default_factory=OrderedSet)


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class ExecutionTracer:
    """Tracks branch distances and covered statements during execution.
    The results are stored in an execution trace."""

    _logger = logging.getLogger(__name__)

    class TracerLocalState(threading.local):  # pylint:disable=too-few-public-methods
        """Encapsulate state that is thread specific."""

        def __init__(self):
            super().__init__()
            self.enabled = True
            self.trace = ExecutionTrace()

    def __init__(self) -> None:
        self._known_data = KnownData()
        # Contains the trace information that is generated when a module is imported
        self._import_trace = ExecutionTrace()

        # Thread local state
        self._thread_local_state = ExecutionTracer.TracerLocalState()

        self.init_trace()
        self._current_thread_identifier: int | None = None

    @property
    def current_thread_identifier(self) -> int | None:
        """Get the current thread identifier.

        Returns:
            The current thread identifier
        """
        return self._current_thread_identifier

    @current_thread_identifier.setter
    def current_thread_identifier(self, current: int) -> None:
        """Set the current thread identifier. Tracing calls from any other thread
        are ignored.

        Args:
            current: the current thread
        """
        self._current_thread_identifier = current

    @property
    def import_trace(self) -> ExecutionTrace:
        """The trace that was generated when the SUT was imported.

        Returns:
            The execution trace after executing the import statements
        """
        copied = ExecutionTrace()
        copied.merge(self._import_trace)
        return copied

    def get_known_data(self) -> KnownData:
        """Provide known data.

        Returns:
            The known data about the execution
        """
        return self._known_data

    def reset(self) -> None:
        """Resets everything.

        Should be called before instrumentation. Clears all data, so we can handle a
        reload of the SUT.
        """
        self._known_data = KnownData()
        self._import_trace = ExecutionTrace()
        self.init_trace()

    def store_import_trace(self) -> None:
        """Stores the current trace as the import trace.

        Should only be done once, after a module was loaded. The import trace will be
        merged into every subsequently recorded trace.
        """
        self._import_trace = self._thread_local_state.trace
        self.init_trace()

    def init_trace(self) -> None:
        """Create a new trace that only contains the trace data from the import."""
        new_trace = ExecutionTrace()
        new_trace.merge(self._import_trace)
        self._thread_local_state.trace = new_trace

    def is_disabled(self) -> bool:
        """Should we track anything?

        We might have to disable tracing, e.g. when calling __eq__ ourselves.
        Otherwise, we create an endless recursion.

        Returns:
            Whether we should track anything
        """
        return not self._thread_local_state.enabled

    def enable(self) -> None:
        """Enable tracing."""
        self._thread_local_state.enabled = True

    def disable(self) -> None:
        """Disable tracing."""
        self._thread_local_state.enabled = False

    def get_trace(self) -> ExecutionTrace:
        """Get the trace with the current information.

        Returns:
            The current execution trace
        """
        return self._thread_local_state.trace

    def register_code_object(self, meta: CodeObjectMetaData) -> int:
        """Declare that a code object exists.

        Args:
            meta: the code objects existing

        Returns:
            the id of the code object, which can be used to identify the object
            during instrumentation.
        """
        code_object_id = len(self._known_data.existing_code_objects)
        self._known_data.existing_code_objects[code_object_id] = meta
        self._known_data.branch_less_code_objects.add(code_object_id)
        return code_object_id

    def executed_code_object(self, code_object_id: int) -> None:
        """Mark a code object as executed.

        This means, that the routine which refers to this code object was at least
        called once.

        Args:
            code_object_id: the code object id to mark

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        assert (
            code_object_id in self._known_data.existing_code_objects
        ), "Cannot trace unknown code object"
        self._thread_local_state.trace.executed_code_objects.add(code_object_id)

    def register_predicate(self, meta: PredicateMetaData) -> int:
        """Declare that a predicate exists.

        Args:
            meta: Meta data about the predicates

        Returns:
            the id of the predicate, which can be used to identify the predicate
            during instrumentation.
        """
        predicate_id = len(self._known_data.existing_predicates)
        self._known_data.existing_predicates[predicate_id] = meta
        self._known_data.branch_less_code_objects.discard(meta.code_object_id)
        return predicate_id

    def executed_compare_predicate(
        self, value1, value2, predicate: int, cmp_op: Compare
    ) -> None:
        """A predicate that is based on a comparison was executed.

        Args:
            value1: the first value
            value2: the second value
            predicate: the predicate identifier
            cmp_op: the compare operation

        Raises:
            RuntimeError: raised when called from another thread.
            AssertionError: when encountering an unknown compare op.
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        try:
            self.disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            match cmp_op:
                case Compare.EQ:
                    distance_true, distance_false = _eq(value1, value2), _neq(
                        value1, value2
                    )
                case Compare.NE:
                    distance_true, distance_false = _neq(value1, value2), _eq(
                        value1, value2
                    )
                case Compare.LT:
                    distance_true, distance_false = (
                        _lt(value1, value2),
                        _le(value2, value1),
                    )
                case Compare.LE:
                    distance_true, distance_false = (
                        _le(value1, value2),
                        _lt(value2, value1),
                    )
                case Compare.GT:
                    distance_true, distance_false = (
                        _lt(value2, value1),
                        _le(value1, value2),
                    )
                case Compare.GE:
                    distance_true, distance_false = (
                        _le(value2, value1),
                        _lt(value1, value2),
                    )
                case Compare.IN:
                    distance_true, distance_false = (
                        _in(value1, value2),
                        _nin(value1, value2),
                    )
                case Compare.NOT_IN:
                    distance_true, distance_false = (
                        _nin(value1, value2),
                        _in(value1, value2),
                    )
                case Compare.IS:
                    distance_true, distance_false = (
                        _is(value1, value2),
                        _isn(value1, value2),
                    )
                case Compare.IS_NOT:
                    distance_true, distance_false = (
                        _isn(value1, value2),
                        _is(value1, value2),
                    )
                case _:
                    raise AssertionError("Unknown compare op")
            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    def executed_bool_predicate(self, value, predicate: int) -> None:
        """A predicate that is based on a boolean value was executed.

        Args:
            value: the value
            predicate: the predicate identifier

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        try:
            self.disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            distance_true = 0.0
            distance_false = 0.0
            if value:
                if isinstance(value, Sized):
                    # Sized instances evaluate to False if they are empty,
                    # and to True otherwise, thus we can use their size as a distance
                    # measurement.
                    distance_false = len(value)
                elif is_numeric(value):
                    # For numeric value, we can use their absolute value
                    distance_false = abs(value)
                else:
                    # Necessary to use inf instead of 1.0 here,
                    # so that a value for which we can't compute a false distance
                    # always has the greatest distance to the false branch than an
                    # object for which we can compute a distance.
                    distance_false = inf
            else:
                distance_true = 1.0

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    def executed_exception_match(self, err, exc, predicate: int):
        """A predicate that is based on exception matching was executed.

        Args:
            err: The raised exception
            exc: The matching condition
            predicate: the predicate identifier

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        try:
            self.disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            distance_true = 0.0
            distance_false = 0.0
            if given_exception_matches(err, exc):
                distance_false = 1.0
            else:
                distance_true = 1.0

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    def track_line_visit(self, line_id: int) -> None:
        """Tracks the visit of a line.

        Args:
            line_id: the if of the line that was visited

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        self._thread_local_state.trace.covered_line_ids.add(line_id)

    def register_line(
        self, code_object_id: int, file_name: str, line_number: int
    ) -> int:
        """Tracks the existence of a line.

        Args:
            code_object_id: The id of the code object that contains the line
            file_name: The file in which the statement is
            line_number: The line of the statement to track

        Returns:
            the id of the registered line
        """
        line_meta = LineMetaData(code_object_id, file_name, line_number)
        if line_meta not in self._known_data.existing_lines.values():
            line_id = len(self._known_data.existing_lines)
            self._known_data.existing_lines[line_id] = line_meta
        else:
            index = list(self._known_data.existing_lines.values()).index(line_meta)
            line_id = list(self._known_data.existing_lines.keys())[index]
        return line_id

    def _update_metrics(
        self, distance_false: float, distance_true: float, predicate: int
    ):
        assert (
            predicate in self._known_data.existing_predicates
        ), "Cannot update unknown predicate"
        assert distance_true >= 0.0, "True distance cannot be negative"
        assert distance_false >= 0.0, "False distance cannot be negative"
        assert (distance_true == 0.0) ^ (
            distance_false == 0.0
        ), "Exactly one distance must be 0.0, i.e., one branch must be taken."
        self._thread_local_state.trace.update_predicate_distances(
            distance_true=distance_true,
            distance_false=distance_false,
            predicate=predicate,
        )

    def track_generic(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Track a generic instruction inside the trace.

        Note: This method is referenced by name in the instrumentation
        for checked coverage. To avoid circular imports, the name is simply written
        as string, so if this method is renamed, please adjust the string in the
        instrumentation. Otherwise, the checked coverage instrumentation breaks!

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def track_memory_access(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: Union[str, CellVar, FreeVar],
        arg_address: int,
        arg_type: type,
    ) -> None:
        """Track a memory access instruction in the trace.

        Note: This method is referenced by name in the instrumentation
        for checked coverage. To avoid circular imports, the name is simply written
        as string, so if this method is renamed, please adjust the string in the
        instrumentation. Otherwise, the checked coverage instrumentation breaks!

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            arg: the used variable
            arg_address: the memory address of the variable
            arg_type: the type of the variable

        Raises:
            ValueError: when no argument is given
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        if not arg:
            if opcode != op.IMPORT_NAME:  # IMPORT_NAMEs may not have an argument
                raise ValueError("A memory access instruction must have an argument")
        if isinstance(arg, (CellVar, FreeVar)):
            arg = arg.name

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        # Determine if this is a definition of a completely new object
        # (required later during slicing)
        object_creation = False
        if arg_address and arg_address not in self.get_known_data().object_addresses:
            object_creation = True
            self._known_data.object_addresses.append(arg_address)

        self._thread_local_state.trace.add_memory_instruction(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            arg,
            arg_address,
            mutable_type,
            object_creation,
        )

    def track_attribute_access(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        attr_name: str,
        src_address: int,
        arg_address: int,
        arg_type: type,
    ) -> None:
        """Track an attribute access instruction in the trace.

        Note: This method is referenced by name in the instrumentation
        for checked coverage. To avoid circular imports, the name is simply written
        as string, so if this method is renamed, please adjust the string in the
        instrumentation. Otherwise, the checked coverage instrumentation breaks!

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            attr_name: the name of the accessed attribute
            src_address: the memory address of the attribute
            arg_address: the memory address of the argument
            arg_type: the type of argument

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        # Different built-in methods and functions often have the same address when
        # accessed sequentially.
        # The address is not recorded in such cases.
        if arg_type is BuiltinMethodType or arg_type is BuiltinFunctionType:
            arg_address = -1

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        self._thread_local_state.trace.add_attribute_instruction(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            attr_name,
            src_address,
            arg_address,
            mutable_type,
        )

    def track_jump(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        target_id: int,
    ) -> None:
        """Track a jump instruction in the trace.

        Note: This method is referenced by name in the instrumentation
        for checked coverage. To avoid circular imports, the name is simply written
        as string, so if this method is renamed, please adjust the string in the
        instrumentation. Otherwise, the checked coverage instrumentation breaks!

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            target_id: the offset of the target of the jump

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_jump_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, target_id
        )

    def track_call(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: int,
    ) -> None:
        """Track a method call instruction in the trace.

        Note: This method is referenced by name in the instrumentation
        for checked coverage. To avoid circular imports, the name is simply written
        as string, so if this method is renamed, please adjust the string in the
        instrumentation. Otherwise, the checked coverage instrumentation breaks!

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            arg: the argument used in the method call

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_call_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, arg
        )

    def track_return(  # pylint: disable=too-many-arguments
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Track a return instruction in the trace.

        Note: This method is referenced by name in the instrumentation
        for checked coverage. To avoid circular imports, the name is simply written
        as string, so if this method is renamed, please adjust the string in the
        instrumentation. Otherwise, the checked coverage instrumentation breaks!

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_return_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def register_exception_assertion(self, statement: stmt.Statement) -> None:
        """Track the position of an exception assertion in the trace.

        Normally, to track an assertion, we trace the POP_JUMP_IF_TRUE instruction
        contained by each assertion. The pytest exception assertion does not use
        an assertion containing this instruction.
        Therefore, we trace the instruction that was last executed before
        the exception.

        Args:
            statement: the statement causing the exception

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        if statement.has_only_exception_assertion():
            trace = self._thread_local_state.trace
            error_call_position = len(trace.executed_instructions) - 1
            error_causing_instr = trace.executed_instructions[error_call_position]
            code_object_id = error_causing_instr.code_object_id
            node_id = error_causing_instr.node_id
            trace.executed_assertions.append(
                ExecutedAssertion(
                    code_object_id,
                    node_id,
                    error_call_position,
                    statement.assertions[0],
                )
            )

    def register_assertion_position(
        self, code_object_id: int, node_id: int, assertion: ass.Assertion
    ) -> None:
        """Track the position of an assertion in the trace.

        Args:
            code_object_id: code object containing the assertion to register
            node_id: the id of the node containing the assertion to register
            assertion: the assertion of the statement

        Raises:
            RuntimeError: raised when called from another thread
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        if self.is_disabled():
            return

        exec_instr = self.get_trace().executed_instructions
        pop_jump_if_true_position = len(exec_instr) - 1
        for instr in reversed(exec_instr):
            if instr.opcode == op.POP_JUMP_IF_TRUE:
                break
            pop_jump_if_true_position -= 1
        assert (
            pop_jump_if_true_position != -1
        ), "Node in code object did not contain a POP_JUMP_IF_TRUE instruction"

        self._thread_local_state.trace.executed_assertions.append(
            ExecutedAssertion(
                code_object_id,
                node_id,
                pop_jump_if_true_position,
                assertion,
            )
        )

    @staticmethod
    def attribute_lookup(object_type, attribute: str) -> int:
        """Check the dictionary of classes making up the MRO (_PyType_Lookup)
        The attribute must be a data descriptor to be prioritized here

        Args:
            object_type: The type object to check
            attribute: the attribute to check for in the class

        Returns:
            The id of the object type or the class if it has the attribute, -1 otherwise
        """

        for cls in type(object_type).__mro__:
            if attribute in cls.__dict__:
                # Class in the MRO hierarchy has attribute
                if inspect.isdatadescriptor(cls.__dict__.get(attribute)):
                    # Class has attribute and attribute is a data descriptor
                    return id(cls)

        # This would lead to an infinite recursion and thus a crash of the program
        if attribute in ("__getattr__", "__getitem__"):
            return -1
        # Check if the dictionary of the object on which lookup is performed
        if hasattr(object_type, "__dict__") and object_type.__dict__:
            if attribute in object_type.__dict__:
                return id(object_type)
        if hasattr(object_type, "__slots__") and object_type.__slots__:
            if attribute in object_type.__slots__:
                return id(object_type)

        # Check if attribute in MRO hierarchy (no need for data descriptor)
        for cls in type(object_type).__mro__:
            if attribute in cls.__dict__:
                return id(cls)

        return -1

    def __repr__(self) -> str:
        return "ExecutionTracer"

    def lineids_to_linenos(self, line_ids: OrderedSet[int]) -> OrderedSet[int]:
        """Convenience method to translate line ids to line numbers.

        Args:
            line_ids: The ids that should be translated.

        Returns:
            The line numbers.
        """
        return OrderedSet(
            [
                self._known_data.existing_lines[line_id].line_number
                for line_id in line_ids
            ]
        )


@dataclass
class ExecutedAssertion:
    """Data class for assertions of a testcase traced during execution for slicing"""

    # the code object containing the executed assertion
    code_object_id: int
    # the node containing the executed assertion
    node_id: int
    # the position inside the exection trace of the executed assertion
    trace_position: int
    # the assertion object of a statement that was executed
    assertion: ass.Assertion


def _eq(val1, val2) -> float:
    """Distance computation for '=='

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 == val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return abs(val1 - val2)
    if is_string(val1) and is_string(val2):
        return levenshtein_distance(val1, val2)
    if is_bytes(val1) and is_bytes(val2):
        return levenshtein_distance(
            val1.decode("iso-8859-1"), val2.decode("iso-8859-1")
        )
    return inf


def _neq(val1, val2) -> float:
    """Distance computation for '!='

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 != val2:
        return 0.0
    return 1.0


def _lt(val1, val2) -> float:
    """Distance computation for '<'

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 < val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return (val1 - val2) + 1.0
    return inf


def _le(val1, val2) -> float:
    """Distance computation for '<='

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 <= val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return (val1 - val2) + 1.0
    return inf


def _in(val1, val2) -> float:
    """Distance computation for 'in'

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 in val2:
        return 0.0
    # TODO(fk) maybe limit this to certain collections?
    #  Check only if collection size is within some range,
    #  otherwise the check might take very long.

    # Use smallest distance to any element.
    return min([_eq(val1, v) for v in val2] + [inf])


def _nin(val1, val2) -> float:
    """Distance computation for 'not in'

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 not in val2:
        return 0.0
    return 1.0


def _is(val1, val2) -> float:
    """Distance computation for 'is'

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 is val2:
        return 0.0
    return 1.0


def _isn(val1, val2) -> float:
    """Distance computation for 'is not'

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 is not val2:
        return 0.0
    return 1.0


class ModuleProvider:
    """Class for providing modules."""

    def __init__(self):
        self._mutated_module_aliases: dict[str, ModuleType] = {}

    def get_module(self, module_name: str) -> ModuleType:
        """
        Provides a module either from sys.modules or if a mutated version for the given
        module name exists than the mutated version of the module will be returned.

        Args:
            module_name: string for the module alias, which should be loaded

        Returns:
            the module which should be loaded.
        """
        if (
            mutated_module := self._mutated_module_aliases.get(module_name, None)
        ) is not None:
            return mutated_module
        return sys.modules[module_name]

    def add_mutated_version(self, module_name: str, mutated_module: ModuleType) -> None:
        """
        Adds a mutated version of a module to the collection of mutated alias of
        normal modules.

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
        """
        Reloads the given module.

        Args:
            module_name: the module to reload.
        """
        reload(sys.modules[module_name])


class TestCaseExecutor:
    """An executor that executes the generated test cases."""

    def __init__(
        self, tracer: ExecutionTracer, module_provider: ModuleProvider | None = None
    ) -> None:
        """Create new test case executor.

        Args:
            tracer: the execution tracer
            module_provider: The used module provider
        """
        # Repeatedly opening/closing devnull caused problems.
        # This is closed when Pynguin terminates, since we don't need this output
        # anyway this is ok.
        # pylint:disable=unspecified-encoding,consider-using-with
        self._null_file = open(os.devnull, mode="w")

        self._module_provider = (
            module_provider if module_provider is not None else ModuleProvider()
        )
        self._tracer = tracer
        self._observers: list[ExecutionObserver] = []
        checked_adapter = CheckedCoverageInstrumentation(self._tracer)
        self._checked_transformer = InstrumentationTransformer(
            self._tracer, [checked_adapter]
        )

        def log_thread_exception(arg):
            _logger.error(
                "Exception in Thread: %s",
                arg.thread,
                exc_info=(arg.exc_type, arg.exc_value, arg.exc_traceback),
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
    def temporarily_add_observer(self, observer: ExecutionObserver):
        """Temporarily add the given observer.

        Args:
            observer: The observer to add.

        Yields:
            A context manager to remove the observer
        """
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

    def execute(
        self,
        test_case: tc.TestCase,
        instrument_test: bool = False,
    ) -> ExecutionResult:
        """Executes all statements of the given test case.

        Args:
            test_case: the test case that should be executed.
            instrument_test: if the test case itself needs to be
                instrumented before execution

        Raises:
            RuntimeError: If something goes wrong inside Pynguin during execution.

        Returns:
            Result of the execution
        """
        with contextlib.redirect_stdout(self._null_file):
            with contextlib.redirect_stderr(self._null_file):
                return_queue: Queue[ExecutionResult] = Queue()
                thread = threading.Thread(
                    target=self._execute_test_case,
                    args=(test_case, return_queue, instrument_test),
                    daemon=True,
                )
                thread.start()
                # Set a timeout for the thread execution of at most 5 seconds.
                thread.join(timeout=min(5, len(test_case.statements)))
                if thread.is_alive():
                    # Set thread ident to invalid value, such that the tracer
                    # kills the thread
                    self._tracer.current_thread_identifier = -1
                    result = ExecutionResult(timeout=True)
                    _logger.warning("Experienced timeout from test-case execution")
                else:
                    try:
                        result = return_queue.get(block=False)
                    except Empty as ex:
                        _logger.error("Finished thread did not return a result.")
                        raise RuntimeError("Bug in Pynguin!") from ex
        self._after_test_case_execution_outside_thread(test_case, result)
        return result

    def _before_test_case_execution(self, test_case: tc.TestCase) -> None:
        self._tracer.init_trace()
        for observer in self._observers:
            observer.before_test_case_execution(test_case)

    def _execute_test_case(
        self, test_case: tc.TestCase, result_queue: Queue, instrument_test: bool
    ) -> None:
        self._before_test_case_execution(test_case)
        result = ExecutionResult()
        exec_ctx = ExecutionContext(self._module_provider)
        self._tracer.current_thread_identifier = threading.current_thread().ident
        for idx, statement in enumerate(test_case.statements):
            ast_node = self._before_statement_execution(statement, exec_ctx)
            exception = self.execute_ast(ast_node, exec_ctx, instrument=instrument_test)
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
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        # We need to disable the tracer, because an observer might interact with an
        # object of the SUT via the ExecutionContext and trigger code execution, which
        # is not caused by the test case and should therefore not be in the trace.
        self._tracer.disable()

        ast_node = exec_ctx.node_for_statement(statement)
        try:
            for observer in self._observers:
                ast_node = observer.before_statement_execution(
                    statement, ast_node, exec_ctx
                )
        finally:
            self._tracer.enable()
        return ExecutionContext.wrap_node_in_module(ast_node)

    def execute_ast(
        self,
        ast_node: ast.Module,
        exec_ctx: ExecutionContext,
        instrument: bool = False,
    ) -> BaseException | None:
        """Execute the given ast_node in the given context.
        You can use this in an observer if you also need to execute an AST Node.

        Args:
            ast_node: The node to execute.
            exec_ctx: The execution context
            instrument: Instrument execution of the given node.

        Returns:
            The raised exception, if any.
        """
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("Executing %s", ast.unparse(ast_node))

        code = compile(ast_node, "<ast>", "exec")
        if instrument:
            code = self._checked_transformer.instrument_module(code)

        try:
            # pylint: disable=exec-used
            exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
        except BaseException as err:  # pylint: disable=broad-except
            failed_stmt = ast.unparse(ast_node)
            _logger.debug("Failed to execute statement:\n%s%s", failed_stmt, err.args)
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
            raise RuntimeError(
                "The current thread shall not be executed any more, thus I kill it."
            )

        self._tracer.disable()
        try:
            for observer in self._observers:
                observer.after_statement_execution(statement, self, exec_ctx, exception)
        finally:
            self._tracer.enable()
