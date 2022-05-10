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
from types import BuiltinFunctionType, BuiltinMethodType, CodeType, ModuleType
from typing import TYPE_CHECKING, Any, Callable, TypeVar, Union

import pytest
from bytecode import BasicBlock, CellVar, Compare, FreeVar, Instr
from jellyfish import levenshtein_distance
from opcode import opname
from ordered_set import OrderedSet

import pynguin.assertion.assertion_to_ast as ass_to_ast
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.utils.namingscope as ns
import pynguin.utils.opcodes as op
from pynguin.analyses.controlflow import CFG, ControlDependenceGraph, ProgramGraphNode
from pynguin.utils.type_utils import (
    given_exception_matches,
    is_bytes,
    is_numeric,
    is_string,
)

immutable_types = [int, float, complex, str, tuple, frozenset, bytes]

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    import pynguin.assertion.assertion_trace as at
    import pynguin.testcase.statement as stmt
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.variablereference as vr


class ArtificialInstr(Instr):
    """Marker subclass to distinguish between original instructions
    and instructions that were inserted by the instrumentation."""


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
            prefix="module", new_name_callback=self._add_new_module_alias
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

    def executable_statement_node(
        self,
        statement: stmt.Statement,
    ) -> tuple[ast.stmt, ast.Module]:
        """Transforms the given statement in an executable ast node.

        Args:
            statement: The statement that should be converted.

        Returns:
            An executable ast node.
        """
        stmt_visitor = stmt_to_ast.StatementToAstVisitor(
            self._module_aliases, self._variable_names
        )
        statement.accept(stmt_visitor)
        ast_stmt = stmt_visitor.ast_node
        return ast_stmt, ExecutionContext._wrap_node_in_module(ast_stmt)

    def executable_assertion_node(
        self, assertion: ass.Assertion, statement_node: ast.stmt
    ) -> ast.Module:
        """Transforms the given assertion in an executable ast node.

        Args:
            assertion: The assertion that should be converted.
            statement_node: The ast node of the statement for the assertion.

        Returns:
            An executable ast node.
        """
        common_modules: set[str] = set()
        ass_visitor = ass_to_ast.PyTestAssertionToAstVisitor(
            self._variable_names, self._module_aliases, common_modules, statement_node
        )
        assertion.accept(ass_visitor)
        return ExecutionContext._wrap_node_in_module(ass_visitor.nodes[1])

    @staticmethod
    def _wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, such that it can be executed.

        Args:
            node: The node to wrap

        Returns:
            The module wrapping the nodes
        """
        ast.fix_missing_locations(node)
        return ast.Module(body=[node], type_ignores=[])

    def _add_new_module_alias(self, module_name: str, alias: str) -> None:
        self._global_namespace[alias] = self._module_provider.get_module(module_name)


class ExecutionObserver:
    """An Observer that can be used to observe statement execution"""

    @abstractmethod
    def before_test_case_execution(self, test_case: tc.TestCase):
        """Called before test case execution.

        Args:
            test_case: The test cases that will be executed.
        """

    @abstractmethod
    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        """Called after test case execution.

        Args:
            test_case: The test cases that will be executed
            result: The execution result
        """

    @abstractmethod
    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ):
        """Called before a statement is executed.

        Args:
            statement: the statement about to be executed.
            exec_ctx: the current execution context.
        """

    @abstractmethod
    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        """
        Called after a statement was executed.

        Args:
            statement: the statement that was executed.
            exec_ctx: the current execution context.
            exception: the exception that was thrown, if any.
        """


class ReturnTypeObserver(ExecutionObserver):
    """Observes the runtime types seen during execution."""

    def __init__(self):
        self._return_type_trace: dict[int, type] = {}

    def before_test_case_execution(self, test_case: tc.TestCase):
        self._return_type_trace.clear()

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        result.store_return_types(dict(self._return_type_trace))

    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ):
        pass  # not relevant

    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        if (
            exception is None
            and (ret_val := statement.ret_val) is not None
            and not ret_val.is_none_type()
        ):
            self._return_type_trace[statement.get_position()] = type(
                exec_ctx.get_reference_value(ret_val)
            )


class ExecutionResult:
    """Result of an execution."""

    def __init__(self, timeout: bool = False) -> None:
        self._exceptions: dict[int, Exception] = {}
        self._assertion_traces: dict[type, at.AssertionTrace] = {}
        self._execution_trace: ExecutionTrace | None = None
        self._timeout = timeout
        self._return_type_trace: dict[int, type] = {}

    @property
    def timeout(self) -> bool:
        """Did a timeout occur during the execution?

        Returns:
            True, if a timeout occurred.
        """
        return self._timeout

    @property
    def return_type_trace(self) -> dict[int, type]:
        """Provide the stored type trace.

        Returns:
            The observed return types per statement.
            Not every statement index may have an entry.
        """
        return self._return_type_trace

    @property
    def exceptions(self) -> dict[int, Exception]:
        """Provide a map of statements indices that threw an exception.

        Returns:
             A map of statement indices to their raised exception
        """
        return self._exceptions

    @property
    def assertion_traces(self) -> dict[type, at.AssertionTrace]:
        """Provides the gathered state traces.

        Returns:
            the gathered output traces.

        """
        return self._assertion_traces

    @property
    def execution_trace(self) -> ExecutionTrace:
        """The trace for this execution.

        Returns:
            The execution race
        """
        assert self._execution_trace, "No trace provided"
        return self._execution_trace

    @execution_trace.setter
    def execution_trace(self, trace: ExecutionTrace) -> None:
        """Set new trace.

        Args:
            trace: The new execution trace
        """
        self._execution_trace = trace

    def add_assertion_trace(self, trace_type: type, trace: at.AssertionTrace) -> None:
        """Add the given trace to the recorded assertion traces.

        Args:
            trace_type: the type of trace.
            trace: the trace to store.

        """
        self._assertion_traces[trace_type] = trace

    def has_test_exceptions(self) -> bool:
        """Returns true if any exceptions were thrown during the execution.

        Returns:
            Whether the test has exceptions
        """
        return bool(self._exceptions)

    def report_new_thrown_exception(self, stmt_idx: int, ex: Exception) -> None:
        """Report an exception that was thrown during execution.

        Args:
            stmt_idx: the index of the statement, that caused the exception
            ex: the exception
        """
        self._exceptions[stmt_idx] = ex

    def get_first_position_of_thrown_exception(self) -> int | None:
        """Provide the index of the first thrown exception or None.

        Returns:
            The index of the first thrown exception, if any
        """
        if self.has_test_exceptions():
            return min(self._exceptions.keys())
        return None

    def store_return_types(self, return_types: dict[int, type]) -> None:
        """Report that the statement with the given stmt_idx has type tp_.

        Args:
            return_types: The observed types for each statement index.
        """
        self._return_type_trace = return_types

    def delete_statement_data(self, deleted_statements: set[int]) -> None:
        """It may happen that the test case is modified after execution, for example,
        by removing unused primitives. We have to update the execution result to reflect
        this, otherwise the indexes maybe wrong.

        Args:
            deleted_statements: The indexes of the deleted statements
        """
        self._return_type_trace = ExecutionResult.shift_dict(
            self._return_type_trace, deleted_statements
        )
        self._exceptions = ExecutionResult.shift_dict(
            self._exceptions, deleted_statements
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
            f"ExecutionResult(exceptions: {self._exceptions}, "
            + f"trace: {self._execution_trace})"
        )

    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class ExecutionTrace:  # pylint: disable=too-many-instance-attributes
    """Stores trace information about the execution."""

    _logger = logging.getLogger(__name__)

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: dict[int, int] = field(default_factory=dict)
    true_distances: dict[int, float] = field(default_factory=dict)
    false_distances: dict[int, float] = field(default_factory=dict)
    covered_line_ids: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_instructions: list[ExecutedInstruction] = field(default_factory=list)
    existing_assertions: list[TracedAssertion] = field(default_factory=list)

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
        self.executed_instructions = other.executed_instructions
        self.existing_assertions.extend(other.existing_assertions)

    @staticmethod
    def _merge_min(target: dict[int, float], source: dict[int, float]) -> None:
        """Merge source into target. Minimum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = min(target.get(key, inf), value)

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
        # TODO(SiL) register instructions with ids instead of dataclasses?
        executed_instr = ExecutedInstruction(
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
        executed_instr = ExecutedMemoryInstruction(
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
        executed_instr = ExecutedAttributeInstruction(
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
        executed_instr = ExecutedControlInstruction(
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
        executed_instr = ExecutedCallInstruction(
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
        executed_instr = ExecutedReturnInstruction(
            module, code_object_id, node_id, opcode, None, lineno, offset
        )

        self.executed_instructions.append(executed_instr)

    def print_trace_debug(self) -> None:
        """Print debugging infos about the executed assertions and instructions."""
        self._logger.debug("------ Execution Trace ------")
        for instr in self.executed_instructions:
            self._logger.debug(instr)
        self._logger.debug("\n")


@dataclass
class CodeObjectMetaData:
    """Stores meta data of a code object."""

    # The raw code object.
    code_object: CodeType

    # Id of the parent code object, if any
    parent_code_object_id: int | None

    # CFG of this Code Object
    cfg: CFG

    # copy of the CFG of this code object before the instrumentation worked on it
    original_cfg: CFG

    # CDG of this Code Object
    cdg: ControlDependenceGraph


@dataclass
class PredicateMetaData:
    """Stores meta data of a predicate."""

    # Line number where the predicate is defined.
    line_no: int

    # Id of the code object where the predicate was defined.
    code_object_id: int

    # The node in the program graph, that defines this predicate.
    node: ProgramGraphNode


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


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class ExecutionTracer:
    """Tracks branch distances and covered statements during execution.
    The results are stored in an execution trace."""

    _logger = logging.getLogger(__name__)

    # Contains static information about how branch distances
    # for certain op codes should be computed.
    # The returned tuple for each computation is (true distance, false distance).
    # pylint: disable=arguments-out-of-order
    _DISTANCE_COMPUTATIONS: dict[Compare, Callable[[Any, Any], tuple[float, float]]] = {
        Compare.EQ: lambda val1, val2: (
            _eq(val1, val2),
            _neq(val1, val2),
        ),
        Compare.NE: lambda val1, val2: (
            _neq(val1, val2),
            _eq(val1, val2),
        ),
        Compare.LT: lambda val1, val2: (
            _lt(val1, val2),
            _le(val2, val1),
        ),
        Compare.LE: lambda val1, val2: (
            _le(val1, val2),
            _lt(val2, val1),
        ),
        Compare.GT: lambda val1, val2: (
            _lt(val2, val1),
            _le(val1, val2),
        ),
        Compare.GE: lambda val1, val2: (
            _le(val2, val1),
            _lt(val1, val2),
        ),
        Compare.IN: lambda val1, val2: (
            _in(val1, val2),
            _nin(val1, val2),
        ),
        Compare.NOT_IN: lambda val1, val2: (
            _nin(val1, val2),
            _in(val1, val2),
        ),
        Compare.IS: lambda val1, val2: (
            _is(val1, val2),
            _isn(val1, val2),
        ),
        Compare.IS_NOT: lambda val1, val2: (
            _isn(val1, val2),
            _is(val1, val2),
        ),
    }

    def __init__(self) -> None:
        self._known_data = KnownData()
        # Contains the trace information that is generated when a module is imported
        self._import_trace = ExecutionTrace()
        self._init_trace()
        self._enabled = True
        self._current_thread_identifier: int | None = None
        self._setup: bool = False
        self._known_object_addresses: set[int] = set()
        self._assertion_stack_counter = 0
        self._test_id = ""
        self._module_name = ""
        self._traced_assertions: list[TracedAssertion] = []

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

    @property
    def module_name(self) -> str:
        """Returns the name of the module that was tested during the trace.

        Returns:
            The name of the module that was tested during the trace.
        """
        return self._module_name

    @module_name.setter
    def module_name(self, module_name: str) -> None:
        """Sets the module name for the trace.

        Args:
            module_name: the new set module name
        """
        self._module_name = module_name

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
        self._init_trace()

    def store_import_trace(self) -> None:
        """Stores the current trace as the import trace.

        Should only be done once, after a module was loaded. The import trace will be
        merged into every subsequently recorded trace.
        """
        self._import_trace = self._trace
        self._init_trace()

    def _init_trace(self) -> None:
        """Create a new trace that only contains the trace data from the import."""
        new_trace = ExecutionTrace()
        new_trace.merge(self._import_trace)
        self._trace = new_trace

    def _is_disabled(self) -> bool:
        """Should we track anything?

        We might have to disable tracing, e.g. when calling __eq__ ourselves.
        Otherwise, we create an endless recursion.

        Returns:
            Whether we should track anything
        """
        return not self._enabled

    def enable(self) -> None:
        """Enable tracing."""
        self._enabled = True

    def disable(self) -> None:
        """Disable tracing."""
        self._enabled = False

    def get_trace(self) -> ExecutionTrace:
        """Get the trace with the current information.

        Returns:
            The current execution trace
        """
        return self._trace

    def clear_trace(self) -> None:
        """Clear trace."""
        self._init_trace()

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
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            return

        assert (
            code_object_id in self._known_data.existing_code_objects
        ), "Cannot trace unknown code object"
        self._trace.executed_code_objects.add(code_object_id)

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
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            return

        if self._is_disabled():
            return

        try:
            self.disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            distance_true, distance_false = ExecutionTracer._DISTANCE_COMPUTATIONS[
                cmp_op
            ](value1, value2)

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    def executed_bool_predicate(self, value, predicate: int) -> None:
        """A predicate that is based on a boolean value was executed.

        Args:
            value: the value
            predicate: the predicate identifier
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            return

        if self._is_disabled():
            return

        try:
            self.disable()
            assert (
                predicate in self._known_data.existing_predicates
            ), "Cannot trace unknown predicate"
            distance_true = 0.0
            distance_false = 0.0
            if value:
                distance_false = 1.0
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
        """
        if threading.current_thread().ident != self._current_thread_identifier:
            return

        if self._is_disabled():
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
        """
        self._trace.covered_line_ids.add(line_id)

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
        self._trace.executed_predicates[predicate] = (
            self._trace.executed_predicates.get(predicate, 0) + 1
        )
        self._trace.true_distances[predicate] = min(
            self._trace.true_distances.get(predicate, inf), distance_true
        )
        self._trace.false_distances[predicate] = min(
            self._trace.false_distances.get(predicate, inf), distance_false
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

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
        """
        self._trace.add_instruction(
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
        """
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
        if arg_address and arg_address not in self._known_object_addresses:
            object_creation = True
            self._known_object_addresses.add(arg_address)

        self._trace.add_memory_instruction(
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
        """

        # Different built-in methods and functions often have the same address when
        # accessed sequentially.
        # The address is not recorded in such cases.
        if arg_type is BuiltinMethodType or arg_type is BuiltinFunctionType:
            arg_address = -1

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        self._trace.add_attribute_instruction(
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

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            target_id: the offset of the target of the jump
        """
        self._trace.add_jump_instruction(
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

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            arg: the argument used in the method call
        """
        self._trace.add_call_instruction(
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

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
        """
        self._trace.add_return_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def register_assertion_position(self, code_object_id: int, node_id: int) -> None:
        """Track the position of an assertion in the trace.

        Args:
            code_object_id: code object containing the assertion to register
            node_id: the id of the node containing the assertion to register
        """
        exec_instr = self.get_trace().executed_instructions
        pop_jump_if_true_position = len(exec_instr) - 1
        for instr in reversed(exec_instr):
            if instr.opcode == op.POP_JUMP_IF_TRUE:
                break
            pop_jump_if_true_position -= 1
        assert (
            pop_jump_if_true_position != -1
        ), "Node in code object did not contain a POP_JUMP_IF_TRUE instruction"
        new_assertion = TracedAssertion(
            code_object_id,
            node_id,
            pop_jump_if_true_position,
        )
        self._trace.existing_assertions.append(new_assertion)

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
class TracedAssertion:
    """Data class for assertions of a testcase traced during execution for slicing"""

    code_object_id: int
    node_id: int
    trace_position: int


@dataclass(frozen=True)
class ExecutedInstruction:
    """Represents an executed bytecode instruction with additional information."""

    file: str
    code_object_id: int
    node_id: int
    opcode: int
    argument: int | str | None
    lineno: int
    offset: int

    @property
    def name(self) -> str:
        """Returns the name of the executed instruction.

        Returns:
            The name of the executed instruction.
        """
        return opname[self.opcode]

    @staticmethod
    def is_jump() -> bool:
        """Returns whether the executed instruction is a jump condition.

        Returns:
            True, if the instruction is a jump condition, False otherwise.
        """
        return False

    def __str__(self) -> str:
        return (
            f"{'(-)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedMemoryInstruction(ExecutedInstruction):
    """Represents an executed instructions which read from or wrote to memory."""

    arg_address: int
    is_mutable_type: bool
    object_creation: bool

    def __str__(self) -> str:
        if not self.arg_address:
            arg_address = -1
        else:
            arg_address = self.arg_address
        return (
            f"{'(mem)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.argument:<25} {hex(arg_address):<25} {self.code_object_id:02d}"
            f"@ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedAttributeInstruction(ExecutedInstruction):
    """
    Represents an executed instructions which accessed an attribute.

    We prepend each accessed attribute with the address of the object the attribute
    is taken from. This allows to build correct def-use pairs during backward traversal.
    """

    src_address: int
    arg_address: int
    is_mutable_type: bool

    @property
    def combined_attr(self):
        """Format the source address and the argument
        for an ExecutedAttributeInstruction.

        Returns:
            A string representation of the attribute in memory
        """
        return f"{hex(self.src_address)}_{self.argument}"

    def __str__(self) -> str:
        return (
            f"{'(attr)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.combined_attr:<51} {self.code_object_id:02d} "
            f"@ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedControlInstruction(ExecutedInstruction):
    """Represents an executed control flow instruction."""

    @staticmethod
    def is_jump() -> bool:
        """Returns whether the executed instruction is a jump condition.

        Returns:
            True, if the instruction is a jump condition, False otherwise.
        """
        return True

    def __str__(self) -> str:
        return (
            f"{'(crtl)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.argument:<51} {self.code_object_id:02d} "
            f"@ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedCallInstruction(ExecutedInstruction):
    """Represents an executed call instruction."""

    def __str__(self) -> str:
        return (
            f"{'(func)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedReturnInstruction(ExecutedInstruction):
    """Represents an executed return instruction."""

    def __str__(self) -> str:
        return (
            f"{'(ret)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.offset:d}"
        )


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

    _logger = logging.getLogger(__name__)

    def __init__(
        self, tracer: ExecutionTracer, module_provider: ModuleProvider | None = None
    ) -> None:
        """Create new test case executor.

        Args:
            tracer: the execution tracer
            module_provider: The used module provider
        """
        self._module_provider = (
            module_provider if module_provider is not None else ModuleProvider()
        )
        self._tracer = tracer
        self._observers: list[ExecutionObserver] = []

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
        # pylint:disable=unspecified-encoding
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                self._before_test_case_execution(test_case)
                return_queue: Queue = Queue()
                thread = threading.Thread(
                    target=self._execute_test_case,
                    args=(test_case, return_queue, instrument_test),
                )
                thread.start()
                thread.join(timeout=len(test_case.statements))
                if thread.is_alive():
                    result = ExecutionResult(timeout=True)
                    self._logger.warning("Experienced timeout from test-case execution")
                else:
                    try:
                        result = return_queue.get(block=False)
                    except Empty as ex:
                        self._logger.error("Finished thread did not return a result.")
                        raise RuntimeError("Bug in Pynguin!") from ex
                self._after_test_case_execution(test_case, result)
        return result

    def _before_test_case_execution(self, test_case: tc.TestCase) -> None:
        self._tracer.clear_trace()
        for observer in self._observers:
            observer.before_test_case_execution(test_case)

    def _execute_test_case(
        self, test_case: tc.TestCase, result_queue: Queue, instrument_test: bool
    ) -> None:
        result = ExecutionResult()
        exec_ctx = ExecutionContext(self._module_provider)
        self.tracer.current_thread_identifier = threading.current_thread().ident
        for idx, statement in enumerate(test_case.statements):
            self._before_statement_execution(statement, exec_ctx)
            exception = self._execute_statement(statement, exec_ctx, instrument_test)
            self._after_statement_execution(statement, exec_ctx, exception)
            if exception is not None:
                result.report_new_thrown_exception(idx, exception)
                break
        result_queue.put(result)

    def _after_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Collect the execution trace after each executed test case.

        Args:
            test_case: The executed test case
            result: The execution result
        """
        result.execution_trace = self._tracer.get_trace()
        for observer in self._observers:
            observer.after_test_case_execution(test_case, result)

    def _before_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
    ) -> None:
        # Check if the current thread is still the one that should be executing
        # Otherwise raise an exception to kill it.
        if self.tracer.current_thread_identifier != threading.current_thread().ident:
            # Kill this thread
            raise RuntimeError()

        # We need to disable the tracer, because an observer might interact with an
        # object of the SUT via the ExecutionContext and trigger code execution, which
        # is not caused by the test case and should therefore not be in the trace.
        self._tracer.disable()
        try:
            for observer in self._observers:
                observer.before_statement_execution(statement, exec_ctx)
        finally:
            self._tracer.enable()

    def _execute_statement(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        instrument_test: bool,
    ) -> Exception | None:
        ast_stmt, ast_node = exec_ctx.executable_statement_node(statement)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("Executing %s", ast.unparse(ast_node))
        code = compile(ast_node, "<ast>", "exec")

        if instrument_test:
            code = self._instrument_code_for_checked(code)

        try:
            # pylint: disable=exec-used
            exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
        except Exception as err:  # pylint: disable=broad-except
            failed_stmt = ast.unparse(ast_node)
            TestCaseExecutor._logger.debug(
                "Failed to execute statement:\n%s%s", failed_stmt, err.args
            )

            if any(
                isinstance(assertion, ass.ExceptionAssertion)
                for assertion in statement.assertions
            ):
                # TODO(SiL) track the existence of an exception assertion
                #  problem: code objects do not hold POP_JUMP_IF_TRUE
                #  solution: track failed call position instead?
                pass

            return err

        if instrument_test and statement.assertions:
            self._execute_assertions(ast_stmt, exec_ctx, statement)

        return None

    def _after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Exception | None,
    ):
        # See comments in _before_statement_execution
        if self.tracer.current_thread_identifier != threading.current_thread().ident:
            # Kill this thread
            raise RuntimeError()

        self._tracer.disable()
        try:
            for observer in self._observers:
                observer.after_statement_execution(statement, exec_ctx, exception)
        finally:
            self._tracer.enable()

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

    def _execute_assertions(
        self, ast_stmt: ast.stmt, exec_ctx: ExecutionContext, statement: stmt.Statement
    ):
        exec_ctx.global_namespace["pytest"] = pytest  # import pytest for assertions

        for assertion in statement.assertions:
            assertion_node = exec_ctx.executable_assertion_node(assertion, ast_stmt)

            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug("Executing %s", ast.unparse(assertion_node))

            code = compile(assertion_node, "<ast>", "exec")
            code = self._instrument_code_for_checked(code)

            try:
                # pylint: disable=exec-used
                exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = ast.unparse(assertion_node)
                TestCaseExecutor._logger.debug(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
            code_object_id, node_id = self._get_assertion_node_and_code_object_ids()
            self._tracer.register_assertion_position(code_object_id, node_id)

    def _instrument_code_for_checked(self, code: CodeType) -> CodeType:
        # TODO(SiL) rework module structure to avoid circular dependencies
        #  if this is imported at the top of the file
        # pylint: disable=import-outside-toplevel
        from pynguin.instrumentation.instrumentation import (
            CheckedCoverageInstrumentation,
            InstrumentationTransformer,
        )

        checked_adapter = CheckedCoverageInstrumentation(self._tracer)
        transformer = InstrumentationTransformer(self._tracer, [checked_adapter])
        code = transformer.instrument_module(code)
        return code
