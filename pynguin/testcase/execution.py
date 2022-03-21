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
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Set, Union

from bytecode import CellVar, Compare, FreeVar, Instr
from jellyfish import levenshtein_distance
from opcode import opname
from ordered_set import OrderedSet

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
    import pynguin.assertion.assertion_trace as at
    import pynguin.testcase.statement as stmt
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.variablereference as vr


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

    def executable_node_for(
        self,
        statement: stmt.Statement,
    ) -> ast.Module:
        """Transforms the given statement in an executable ast node.

        Args:
            statement: The statement that should be converted.

        Returns:
            An executable ast node.
        """
        visitor = stmt_to_ast.StatementToAstVisitor(
            self._module_aliases, self._variable_names
        )
        statement.accept(visitor)
        assert (
            len(visitor.ast_nodes) == 1
        ), "Expected statement to produce exactly one ast node"
        return ExecutionContext._wrap_node_in_module(visitor.ast_nodes[0])

    @staticmethod
    def _wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, such that it can be executed.

        Args:
            node: The node to wrap

        Returns:
            The module wrapping the node
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


class ExecutionResult:
    """Result of an execution."""

    def __init__(self, timeout: bool = False) -> None:
        self._exceptions: dict[int, Exception] = {}
        self._assertion_traces: dict[type, at.AssertionTrace] = {}
        self._execution_trace: ExecutionTrace | None = None
        self._timeout = timeout

    @property
    def timeout(self) -> bool:
        """Did a timeout occur during the execution?

        Returns:
            True, if a timeout occurred.
        """
        return self._timeout

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

    def __str__(self) -> str:
        return (
            f"ExecutionResult(exceptions: {self._exceptions}, "
            + f"trace: {self._execution_trace})"
        )

    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class ExecutionTrace:
    """Stores trace information about the execution."""

    _logger = logging.getLogger(__name__)

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: dict[int, int] = field(default_factory=dict)
    true_distances: dict[int, float] = field(default_factory=dict)
    false_distances: dict[int, float] = field(default_factory=dict)
    covered_line_ids: OrderedSet[int] = field(default_factory=OrderedSet)
    # TODO(SiL) add all attributes below to _merge
    executed_instructions: OrderedSet[ExecutedInstruction] = field(
        default_factory=OrderedSet
    )
    test_id: str = ""
    module_name: str = ""
    module: bool = False
    traced_assertions: List[TracedAssertion] = field(default_factory=list)
    unique_assertions: Set[UniqueAssertion] = field(default_factory=set)
    current_assertion: Optional[TracedAssertion] = None

    def merge(self, other: ExecutionTrace) -> None:
        """Merge the values from the other trace.

        Args:
            other: Merges the other traces into this trace
        """
        self.executed_code_objects.update(other.executed_code_objects)
        for key, value in other.executed_predicates.items():
            self.executed_predicates[key] = self.executed_predicates.get(key, 0) + value
        self._merge_min(self.true_distances, other.true_distances)
        self._merge_min(self.false_distances, other.false_distances)
        self.covered_line_ids.update(other.covered_line_ids)

    @staticmethod
    def _merge_min(target: dict[int, float], source: dict[int, float]) -> None:
        """Merge source into target. Minimum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = min(target.get(key, inf), value)

    def add_instruction(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """
        Creates a new ExecutedInstruction object and adds it to the trace.
        """
        # TODO(SiL) register instructions with ids instead of dataclasses?
        executed_instr = ExecutedInstruction(
            module, code_object_id, node_id, opcode, None, lineno, offset
        )
        self.executed_instructions.add(executed_instr)

    def add_memory_instruction(
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
        """Creates a new ExecutedMemoryInstruction object and adds it to the trace."""
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
        self.executed_instructions.add(executed_instr)

    def add_attribute_instruction(
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
        adds it to the trace."""
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
        self.executed_instructions.add(executed_instr)

    def add_jump_instruction(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        target_id: int,
    ) -> None:
        """Creates a new ExecutedControlInstruction object and adds it to the trace."""
        executed_instr = ExecutedControlInstruction(
            module, code_object_id, node_id, opcode, lineno, offset, target_id
        )
        self.executed_instructions.add(executed_instr)

    def add_call_instruction(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: int,
    ) -> None:
        """Creates a new ExecutedCallInstruction object and adds it to the trace."""
        executed_instr = ExecutedCallInstruction(
            module, code_object_id, node_id, opcode, lineno, offset, arg
        )

        self.executed_instructions.add(executed_instr)

    def add_return_instruction(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Creates a new ExecutedReturnInstruction object and adds it to the trace."""
        executed_instr = ExecutedReturnInstruction(
            module, code_object_id, node_id, opcode, None, lineno, offset
        )

        self.executed_instructions.add(executed_instr)

    def start_assertion(
        self, traced_pop_jump: ExecutedInstruction
    ) -> TracedAssertion:
        """Initialise a new TracedAssertion object and store it as current assertion.
        This is used to know where an assertion started and keep track of all following
        instructions until end_assertion() is called.

        Returns:
            the newly created TracedAssertion object stored in current_assertion.
        """
        self.current_assertion = TracedAssertion(
            traced_pop_jump.code_object_id, traced_pop_jump.node_id, traced_pop_jump.lineno,
            len(self.executed_instructions) - 1, traced_pop_jump
        )
        return self.current_assertion

    def end_assertion(self):
        """Create a new UniqueAssertion object from _current_assertion's instruction,
        which started the assertion to the current position.
        This clears the _current_assertion attribute until start_assertion() is called
        again.
        """
        assert self.current_assertion
        assert self.current_assertion.traced_assertion_pop_jump
        assert self.current_assertion.traced_assertion_pop_jump.opcode == op.POP_JUMP_IF_TRUE

        # TODO(SiL) is this the correct calculation
        self.current_assertion.trace_position_end = len(self.executed_instructions) - 1

        self.traced_assertions.append(self.current_assertion)
        self.unique_assertions.add(
            UniqueAssertion(self.current_assertion.traced_assertion_pop_jump)
        )

        self.current_assertion = None

    def print_trace_debug(self) -> None:
        """Print debugging infos about the executed assertions and instructions."""
        self._logger.debug("\n %d assertion calls(s)", len(self.traced_assertions))
        self._logger.debug("\n")
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
        self._known_object_addresses: Set[int] = set()
        self._current_assertion: Optional[TracedAssertion] = None
        self._assertion_stack_counter = 0
        self._test_id = ""
        self._module_name = ""
        self._traced_assertions: List[TracedAssertion] = []
        self._unique_assertions: Set[UniqueAssertion] = set()

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
    def test_id(self) -> str:
        """
        Returns the id of an executed test as string.
        Returns:
            The id of the test case or suite that created the trace.
        """
        return self._test_id

    @test_id.setter
    def test_id(self, test_id: str) -> None:
        """
        Sets the id of an executed test case or suite inside a trace.
        Args:
            test_id: the new test id as string
        """
        self.test_id = test_id

    @property
    def module_name(self) -> str:
        """
        Returns the name of the module that was tested during the trace.
        Returns:
            The name of the module that was tested during the trace.
        """
        return self._module_name

    @module_name.setter
    def module_name(self, module_name: str) -> None:
        """
        Sets the module name for the trace.
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

    def executed_bool_predicate(self, value, predicate: int):
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

    def track_generic(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Track a generic instruction inside the trace."""
        self._trace.add_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def track_memory_access(
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
        """Track a memory access instruction in the trace."""
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
        # (required later during slicing).
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

    def track_attribute_access(
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
        """Track an attribute access instruction in the trace."""

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

    def track_jump(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        target_id: int,
    ) -> None:
        """Track a jump instruction in the trace."""
        self._trace.add_jump_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, target_id
        )

    def track_call(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: int,
    ) -> None:
        """Track a method call instruction in the trace."""
        self._trace.add_call_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, arg
        )

    def track_return(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Track a return instruction in the trace."""
        self._trace.add_return_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def track_assert_start(
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        """Track the beginning of an assertion in the trace."""
        # previous assertion should be finished being tracked
        assert not self._current_assertion

        pop_jump_instr = ExecutedInstruction(module, code_object_id, node_id, opcode, None, lineno, offset)
        self._current_assertion = self._trace.start_assertion(pop_jump_instr)

    def track_assert_end(self) -> None:
        """Track the end of an assertion in the trace."""
        assert self._current_assertion
        self._trace.end_assertion()
        self._current_assertion = None

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
    lineno: int
    trace_position_start: int
    traced_assertion_pop_jump: ExecutedInstruction
    trace_position_end: int = -1


class UniqueAssertion:
    """Data class for an assertion uniquely identifiable by its instruction"""

    def __init__(self, assertion_pop_jump_instruction: ExecutedInstruction):
        self.assertion_pop_jump_instruction = assertion_pop_jump_instruction

    def __eq__(self, other):
        if not isinstance(other, UniqueAssertion):
            return False

        return (
            self.assertion_pop_jump_instruction.code_object_id
            == other.assertion_pop_jump_instruction.code_object_id
            and self.assertion_pop_jump_instruction.node_id
            == other.assertion_pop_jump_instruction.node_id
            and self.assertion_pop_jump_instruction.lineno
            == other.assertion_pop_jump_instruction.lineno
            and self.assertion_pop_jump_instruction.offset
            == other.assertion_pop_jump_instruction.offset
        )

    def __hash__(self):
        hash_string = (
            str(self.assertion_pop_jump_instruction.code_object_id)
            + "_"
            + str(self.assertion_pop_jump_instruction.node_id)
            + "_"
            + str(self.assertion_pop_jump_instruction.lineno)
            + "_"
            + str(self.assertion_pop_jump_instruction.offset)
            + "_"
        )

        return hash(hash_string)

    def __str__(self):
        return str(self.assertion_pop_jump_instruction.lineno)


@dataclass(frozen=True)
class ExecutedInstruction:
    """Represents an executed bytecode instruction with additional information."""

    file: str
    code_object_id: int
    node_id: int
    opcode: int
    argument: Optional[int | str]
    lineno: int
    offset: int

    @property
    def name(self) -> str:
        """
        Returns the name of the executed instruction.
        Returns:
            The name of the executed instruction.
        """
        return opname[self.opcode]

    @staticmethod
    def is_jump() -> bool:
        """
        Returns whether the executed instruction is a jump condition.
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
        """
        Returns whether the executed instruction is a jump condition.
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

    def execute(self, test_case: tc.TestCase) -> ExecutionResult:
        """Executes all statements of the given test case.

        Args:
            test_case: the test case that should be executed.

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
                    target=self._execute_test_case, args=(test_case, return_queue)
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
        self,
        test_case: tc.TestCase,
        result_queue: Queue,
    ) -> None:
        result = ExecutionResult()
        exec_ctx = ExecutionContext(self._module_provider)
        self.tracer.current_thread_identifier = threading.current_thread().ident
        for idx, statement in enumerate(test_case.statements):
            self._before_statement_execution(statement, exec_ctx)
            exception = self._execute_statement(statement, exec_ctx)
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
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
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
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ) -> Exception | None:
        ast_node = exec_ctx.executable_node_for(statement)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("Executing %s", ast.unparse(ast_node))
        code = compile(ast_node, "<ast>", "exec")
        try:
            # pylint: disable=exec-used
            exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
        except Exception as err:  # pylint: disable=broad-except
            failed_stmt = ast.unparse(ast_node)
            TestCaseExecutor._logger.debug(
                "Failed to execute statement:\n%s%s", failed_stmt, err.args
            )
            return err
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
