#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Contains all code related to test-case execution."""

from __future__ import annotations

import inspect
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sized
from dataclasses import dataclass, field
from functools import wraps
from itertools import count
from math import inf
from opcode import opname
from types import BuiltinFunctionType, BuiltinMethodType, CodeType, MethodType, TracebackType
from typing import TYPE_CHECKING, Concatenate, ParamSpec

from bytecode.instr import CellVar, FreeVar

import pynguin.assertion.assertion as ass
import pynguin.slicer.executedinstruction as ei
import pynguin.testcase.statement as stmt
import pynguin.utils.typetracing as tt
from pynguin.instrumentation import PynguinCompare, version
from pynguin.utils.exceptions import TracingAbortedException
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.type_utils import (
    given_exception_matches,
    is_bytes,
    is_numeric,
    is_string,
    string_distance,
    string_le_distance,
    string_lt_distance,
)

if TYPE_CHECKING:
    from typing_extensions import Self

    from pynguin.instrumentation.controlflow import CFG, BasicBlockNode, ControlDependenceGraph

immutable_types = (int, float, complex, str, tuple, frozenset, bytes)

VariableName = str | CellVar | FreeVar


@dataclass
class ExecutedAssertion:
    """Data class for assertions of a testcase traced during execution for slicing."""

    # the position inside the exection trace of the executed assertion
    trace_position: int
    # the assertion object of a statement that was executed
    assertion: ass.Assertion


@dataclass
class ExecutionTrace:
    """Stores trace information about the execution."""

    _logger = logging.getLogger(__name__)

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: dict[int, int] = field(default_factory=dict)
    true_distances: dict[int, float] = field(default_factory=dict)
    false_distances: dict[int, float] = field(default_factory=dict)
    covered_line_ids: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_instructions: list[ei.ExecutedInstruction] = field(default_factory=list)
    object_addresses: OrderedSet[int] = field(default_factory=OrderedSet)
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
        self.object_addresses.update(other.object_addresses)
        self.executed_assertions.extend(
            ExecutedAssertion(
                executed_assertion.trace_position + shift,
                executed_assertion.assertion,
            )
            for executed_assertion in other.executed_assertions
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
        self.executed_predicates[predicate] = self.executed_predicates.get(predicate, 0) + 1
        self.true_distances[predicate] = min(self.true_distances.get(predicate, inf), distance_true)
        self.false_distances[predicate] = min(
            self.false_distances.get(predicate, inf), distance_false
        )

    def add_instruction(  # noqa: PLR0917
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

    def add_memory_instruction(  # noqa: PLR0917
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg_name: str | tuple[str, str],
        arg_address: int | tuple[int, int],
        is_mutable_type: bool | tuple[bool, bool],  # noqa: FBT001
        object_creation: bool | tuple[bool, bool],  # noqa: FBT001
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

    def add_attribute_instruction(  # noqa: PLR0917
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
        is_mutable_type: bool,  # noqa: FBT001
        is_method: bool,  # noqa: FBT001
    ) -> None:
        """Creates a new ExecutedAttributeInstruction object and adds it to the trace.

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
            is_method: if the attribute is a method
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
            is_method,
        )

        self.executed_instructions.append(executed_instr)

    def add_jump_instruction(  # noqa: PLR0917
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

    def add_call_instruction(  # noqa: PLR0917
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

    def add_return_instruction(  # noqa: PLR0917
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

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, LineMetaData):
            return False
        # code object id is not checked since file
        # and line number are the unique identifiers
        return self.line_number == other.line_number and self.file_name == other.file_name


@dataclass
class CodeObjectMetaData:
    """Stores meta data of a code object."""

    # The instrumented code object.
    code_object: CodeType

    # Id of the parent code object, if any
    parent_code_object_id: int | None

    # CFG of this code object
    cfg: CFG

    # CDG of this code object
    cdg: ControlDependenceGraph

    def __getstate__(self) -> dict:
        return {
            "code_object": self.code_object,
            "parent_code_object_id": self.parent_code_object_id,
            "cfg": self.cfg,
            "cdg": self.cdg,
        }

    def __setstate__(self, state: dict) -> None:
        self.code_object = state["code_object"]
        self.parent_code_object_id = state["parent_code_object_id"]
        self.cfg = state["cfg"]
        self.cdg = state["cdg"]


@dataclass
class PredicateMetaData:
    """Stores meta data of a predicate."""

    # Line number where the predicate is defined.
    line_no: int

    # Id of the code object where the predicate was defined.
    code_object_id: int

    # The node in the program graph, that defines this predicate.
    node: BasicBlockNode


@dataclass
class SubjectProperties:
    """Contains properties about the subject under test.

    The subject properties are `code objects`, `predicates` and `lines`:

    - **Code Objects**:
      Compiled chunks of code (functions, methods, modules).
      Tracked in `CodeObjectMetaData` with references to the compiled code, parent,
      control graphs, and a unique ID. Represent the program's structural units.
    - **Predicates**:
      Decision points within code objects (e.g., ``if``, ``while``).
      Tracked in `PredicateMetaData` with line number, owning code object, and graph node.
      Used for branch coverage and measuring branch distances.
    - **Lines**:
      Individual lines of code within code objects.
      Tracked in `LineMetaData` with file name and line number.
      Used for measuring line coverage.

    **Example**::

        def example(x):
            if x > 0:  # Predicate
                return "pos"
            return "non-pos"

        # The function ``example`` is a Code Object and ``x > 0`` is a Predicate.
    """

    # TODO(lk): SubjectProperties and ExecutionTracer should be separated

    # The instrumentation tracer that is used to trace the execution
    instrumentation_tracer: InstrumentationExecutionTracer = field(
        default_factory=lambda: InstrumentationExecutionTracer(ExecutionTracer())
    )

    # The counter used to generate unique code object ids
    code_object_counter: count[int] = field(default_factory=count)

    # Maps all known ids of Code Objects to meta information
    existing_code_objects: dict[int, CodeObjectMetaData] = field(default_factory=dict)

    # Maps all known ids of predicates to meta information
    existing_predicates: dict[int, PredicateMetaData] = field(default_factory=dict)

    # Stores which line id represents which line in which file
    existing_lines: dict[int, LineMetaData] = field(default_factory=dict)

    @property
    def branch_less_code_objects(self) -> Iterable[int]:
        """Get the existing code objects that do not contain a branch.

        Every code object is initially seen as branch-less until a predicate is registered for it.

        Returns:
            The existing code objects that do not contain a branch.
        """
        return (
            code_object_id
            for code_object_id in self.existing_code_objects
            if all(
                code_object_id != metadata.code_object_id
                for metadata in self.existing_predicates.values()
            )
        )

    def reset(self) -> None:
        """Resets the subject properties."""
        self.code_object_counter = count()
        self.existing_code_objects.clear()
        self.existing_predicates.clear()
        self.existing_lines.clear()
        self.instrumentation_tracer.reset()

    def create_code_object_id(self) -> int:
        """Create a new code object ID.

        Returns:
            A new code object ID.
        """
        return next(self.code_object_counter)

    def register_code_object(self, code_object_id: int, meta: CodeObjectMetaData) -> None:
        """Declare that a code object exists.

        Args:
            code_object_id: the id of the code object, which should be used to identify the object
            during instrumentation.
            meta: the code objects existing
        """
        assert code_object_id not in self.existing_code_objects, (
            "Code object already registered in existing code objects"
        )

        self.existing_code_objects[code_object_id] = meta

    def register_predicate(self, meta: PredicateMetaData) -> int:
        """Declare that a predicate exists.

        Args:
            meta: Metadata about the predicates

        Returns:
            the id of the predicate, which can be used to identify the predicate
            during instrumentation.
        """
        assert (meta.node, meta.code_object_id) not in {
            (p.node, p.code_object_id) for p in self.existing_predicates.values()
        }, "Predicate with the same node already registered"
        predicate_id = len(self.existing_predicates)
        self.existing_predicates[predicate_id] = meta
        return predicate_id

    def register_line(self, meta: LineMetaData) -> int:
        """Tracks the existence of a line.

        Args:
            meta: Metadata about the line

        Returns:
            the id of the registered line
        """
        if meta not in self.existing_lines.values():
            line_id = len(self.existing_lines)
            self.existing_lines[line_id] = meta
        else:
            index = list(self.existing_lines.values()).index(meta)
            line_id = list(self.existing_lines.keys())[index]
        return line_id

    def validate_execution_trace(self, execution_trace: ExecutionTrace) -> None:
        """Validate the execution trace.

        Args:
            execution_trace: The execution trace to validate

        Raises:
            AssertionError: if the execution trace is invalid
        """
        for code_object_id in execution_trace.executed_code_objects:
            assert code_object_id in self.existing_code_objects, (
                f"Code object id {code_object_id} not registered in subject properties"
            )
        for predicate_id in execution_trace.executed_predicates:
            assert predicate_id in self.existing_predicates, (
                f"Predicate id {predicate_id} not registered in subject properties"
            )
        for line_id in execution_trace.covered_line_ids:
            assert line_id in self.existing_lines, (
                f"Line id {line_id} not registered in subject properties"
            )

    def lineids_to_linenos(self, line_ids: OrderedSet[int]) -> OrderedSet[int]:
        """Convenience method to translate line ids to line numbers.

        Args:
            line_ids: The ids that should be translated.

        Returns:
            The line numbers.
        """
        return OrderedSet([self.existing_lines[line_id].line_number for line_id in line_ids])


class AbstractExecutionTracer(ABC):  # noqa: PLR0904
    """An abstract execution tracer.

    The results are stored in an execution trace.
    """

    @abstractmethod
    def __enter__(self) -> Self:
        """Activate the tracer for the current thread.

        Returns:
            The tracer itself, so it can be used as a context manager.
        """

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Deactivate the tracer for the current thread.

        Args:
            exc_type: The type of the exception, if any.
            exc_value: The value of the exception, if any.
            traceback: The traceback of the exception, if any.
        """

    @abstractmethod
    def check(self) -> None:
        """Check if the thread that called this method should still be running.

        Raises:
            RuntimeError: if the thread is not running anymore.
        """

    @property
    @abstractmethod
    def import_trace(self) -> ExecutionTrace:
        """The trace that was generated when the SUT was imported.

        Returns:
            The execution trace after executing the import statements
        """

    @abstractmethod
    def reset(self) -> None:
        """Resets everything.

        Should be called before instrumentation. Clears all data, so we can handle a
        reload of the SUT.
        """

    @abstractmethod
    def store_import_trace(self) -> None:
        """Stores the current trace as the import trace.

        Should only be done once, after a module was loaded. The import trace will be
        merged into every subsequently recorded trace.
        """

    @abstractmethod
    def init_trace(self) -> None:
        """Create a new trace that only contains the trace data from the import."""

    @abstractmethod
    def is_disabled(self) -> bool:
        """Should we track anything?

        We might have to disable tracing, e.g. when calling __eq__ ourselves.
        Otherwise, we create an endless recursion.

        Returns:
            Whether we should track anything
        """

    @abstractmethod
    def enable(self) -> None:
        """Enable tracing."""

    @abstractmethod
    def disable(self) -> None:
        """Disable tracing."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the tracer.

        This should be called when the tracer is no longer needed, e.g., when the test
        case execution is finished.
        """

    @abstractmethod
    def get_trace(self) -> ExecutionTrace:
        """Get the trace with the current information.

        Returns:
            The current execution trace
        """

    @abstractmethod
    def executed_code_object(self, code_object_id: int) -> None:
        """Mark a code object as executed.

        This means, that the routine which refers to this code object was at least
        called once.

        Args:
            code_object_id: the code object id to mark

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def executed_compare_predicate(
        self, value1, value2, predicate: int, cmp_op: PynguinCompare
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

    @abstractmethod
    def executed_bool_predicate(self, value, predicate: int) -> None:
        """A predicate that is based on a boolean value was executed.

        Args:
            value: the value
            predicate: the predicate identifier

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def executed_exception_match(
        self,
        err: BaseException | type[BaseException],
        exc: type[BaseException],
        predicate: int,
    ) -> None:
        """A predicate that is based on exception matching was executed.

        Args:
            err: The raised exception
            exc: The matching condition
            predicate: the predicate identifier

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_line_visit(self, line_id: int) -> None:
        """Tracks the visit of a line.

        Args:
            line_id: the if of the line that was visited

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_generic(  # noqa: PLR0917
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

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_memory_access(  # noqa: PLR0917
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        var_name: VariableName | tuple[VariableName, VariableName],
        var_value: object,
    ) -> None:
        """Track a memory access instruction in the trace.

        Args:
            module: File name of the module containing the instruction
            code_object_id: code object containing the instruction
            node_id: the node of the code object containing the instruction
            opcode: the opcode of the instruction
            lineno: the line number of the instruction
            offset: the offset of the instruction
            var_name: the used variable name
            var_value: the value stored in the used variable

        Raises:
            ValueError: when no argument is given
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_attribute_access(  # noqa: PLR0917
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        attr_name: str | None,
        obj: object,
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
            obj: the object containing the accessed attribute

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_jump(  # noqa: PLR0917
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

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_call(  # noqa: PLR0917
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

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_return(  # noqa: PLR0917
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

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def track_exception_assertion(self, statement: stmt.Statement) -> None:
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

    @abstractmethod
    def track_assertion_position(self, assertion: ass.Assertion) -> None:
        """Track the position of an assertion in the trace.

        Args:
            assertion: the assertion of the statement

        Raises:
            RuntimeError: raised when called from another thread
        """

    @abstractmethod
    def __getstate__(self) -> dict:
        """Gets the state.

        Returns:
            The state
        """

    @abstractmethod
    def __setstate__(self, state: dict) -> None:
        """Sets the state.

        Args:
            state: The state
        """


def _eq(val1, val2) -> float:
    """Distance computation for '=='.

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 == val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return float(abs(val1 - val2))
    if is_string(val1) and is_string(val2):
        return string_distance(val1, val2)
    if is_bytes(val1) and is_bytes(val2):
        return string_distance(val1.decode("iso-8859-1"), val2.decode("iso-8859-1"))
    return inf


def _neq(val1, val2) -> float:
    """Distance computation for '!='.

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
    """Distance computation for '<'.

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 < val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return (float(val1) - float(val2)) + 1.0
    if is_string(val1) and is_string(val2):
        return string_lt_distance(val1, val2)
    if is_bytes(val1) and is_bytes(val2):
        return string_lt_distance(val1.decode("iso-8859-1"), val2.decode("iso-8859-1"))
    return inf


def _le(val1, val2) -> float:
    """Distance computation for '<='.

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 <= val2:
        return 0.0
    if is_numeric(val1) and is_numeric(val2):
        return float(val1) - float(val2)
    if is_string(val1) and is_string(val2):
        return string_le_distance(val1, val2)
    if is_bytes(val1) and is_bytes(val2):
        return string_le_distance(val1.decode("iso-8859-1"), val2.decode("iso-8859-1"))
    return inf


def _in(val1, val2) -> float:
    """Distance computation for 'in'.

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

    # Use the shortest distance to any element.
    return min([_eq(val1, v) for v in val2] + [inf])


def _nin(val1, val2) -> float:
    """Distance computation for 'not in'.

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
    """Distance computation for 'is'.

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
    """Distance computation for 'is not'.

    Args:
        val1: the first value
        val2: the second value

    Returns:
        the distance
    """
    if val1 is not val2:
        return 0.0
    return 1.0


_P = ParamSpec("_P")


def _early_return(
    func: Callable[Concatenate[ExecutionTracer, _P], None],
) -> Callable[Concatenate[ExecutionTracer, _P], None]:
    @wraps(func)
    def wrapper(self: ExecutionTracer, *args: _P.args, **kwargs: _P.kwargs) -> None:
        if self.is_disabled():
            return

        self.check()

        func(self, *args, **kwargs)

    return wrapper


class ExecutionTracer(AbstractExecutionTracer):  # noqa: PLR0904
    """Tracks branch distances and covered statements during execution.

    The results are stored in an execution trace.
    """

    _logger = logging.getLogger(__name__)

    class TracerLocalState(threading.local):
        """Encapsulate state that is thread specific."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.enabled = True
            self.trace = ExecutionTrace()

    def __init__(self) -> None:  # noqa: D107
        # Contains the trace information that is generated when a module is imported
        self._import_trace = ExecutionTrace()

        # Thread local state
        self._thread_local_state = ExecutionTracer.TracerLocalState()

        self.init_trace()
        self._current_thread_identifier: int | None = None
        self._current_code_object_id = 0

    def __enter__(self) -> Self:
        self._current_thread_identifier = threading.current_thread().ident
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

    def check(self) -> None:  # noqa: D102
        if threading.current_thread().ident != self._current_thread_identifier:
            raise TracingAbortedException(
                "The current thread shall not be executed anymore, thus I kill it."
            )

    @property
    def import_trace(self) -> ExecutionTrace:  # noqa: D102
        copied = ExecutionTrace()
        copied.merge(self._import_trace)
        return copied

    @property
    def state(self) -> dict:
        """Get the current state.

        Returns:
            The current state
        """
        return {
            "import_trace": self._import_trace,
            "current_thread_identifier": self._current_thread_identifier,
            "thread_local_state": {
                "enabled": self._thread_local_state.enabled,
                "trace": self._thread_local_state.trace,
            },
        }

    @state.setter
    def state(self, state: dict) -> None:
        """Set the current state.

        Args:
            state: The state to set
        """
        self._import_trace = state["import_trace"]
        self._current_thread_identifier = state["current_thread_identifier"]
        self._thread_local_state = ExecutionTracer.TracerLocalState()
        self._thread_local_state.enabled = state["thread_local_state"]["enabled"]
        self._thread_local_state.trace = state["thread_local_state"]["trace"]

    def reset(self) -> None:  # noqa: D102
        self._import_trace = ExecutionTrace()
        self.init_trace()

    def store_import_trace(self) -> None:  # noqa: D102
        self._import_trace = self._thread_local_state.trace
        self.init_trace()

    def init_trace(self) -> None:  # noqa: D102
        new_trace = ExecutionTrace()
        new_trace.merge(self._import_trace)
        self._thread_local_state.trace = new_trace

    def is_disabled(self) -> bool:  # noqa: D102
        return not self._thread_local_state.enabled

    def enable(self) -> None:  # noqa: D102
        self._thread_local_state.enabled = True

    def disable(self) -> None:  # noqa: D102
        self._thread_local_state.enabled = False

    def stop(self) -> None:  # noqa: D102
        self._current_thread_identifier = None

    def get_trace(self) -> ExecutionTrace:  # noqa: D102
        return self._thread_local_state.trace

    @_early_return
    def executed_code_object(self, code_object_id: int) -> None:  # noqa: D102
        self._thread_local_state.trace.executed_code_objects.add(code_object_id)

    @_early_return
    def executed_compare_predicate(  # noqa: D102, C901
        self, value1, value2, predicate: int, cmp_op: PynguinCompare
    ) -> None:
        try:
            self.disable()
            value1 = tt.unwrap(value1)
            value2 = tt.unwrap(value2)

            match cmp_op:
                case PynguinCompare.EQ:
                    distance_true, distance_false = _eq(value1, value2), _neq(value1, value2)
                case PynguinCompare.NE:
                    distance_true, distance_false = _neq(value1, value2), _eq(value1, value2)
                case PynguinCompare.LT:
                    distance_true, distance_false = (
                        _lt(value1, value2),
                        _le(value2, value1),
                    )
                case PynguinCompare.LE:
                    distance_true, distance_false = (
                        _le(value1, value2),
                        _lt(value2, value1),
                    )
                case PynguinCompare.GT:
                    distance_true, distance_false = (
                        _lt(value2, value1),
                        _le(value1, value2),
                    )
                case PynguinCompare.GE:
                    distance_true, distance_false = (
                        _le(value2, value1),
                        _lt(value1, value2),
                    )
                case PynguinCompare.IN:
                    distance_true, distance_false = (
                        _in(value1, value2),
                        _nin(value1, value2),
                    )
                case PynguinCompare.NOT_IN:
                    distance_true, distance_false = (
                        _nin(value1, value2),
                        _in(value1, value2),
                    )
                case PynguinCompare.IS:
                    distance_true, distance_false = (
                        _is(value1, value2),
                        _isn(value1, value2),
                    )
                case PynguinCompare.IS_NOT:
                    distance_true, distance_false = (
                        _isn(value1, value2),
                        _is(value1, value2),
                    )
                case _:
                    raise AssertionError("Unknown compare op")
            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    @_early_return
    def executed_bool_predicate(self, value, predicate: int) -> None:  # noqa: D102
        try:
            self.disable()
            distance_true = 0.0
            distance_false = 0.0
            # Might be necessary when using Proxies.
            value = tt.unwrap(value)
            if value:
                if isinstance(value, Sized):
                    # Sized instances evaluate to False if they are empty,
                    # and to True otherwise, thus we can use their size as a distance
                    # measurement.
                    distance_false = len(value)
                elif is_numeric(value):
                    # For numeric value, we can use their absolute value
                    distance_false = float(abs(value))
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

    @_early_return
    def executed_exception_match(  # noqa: D102
        self,
        err: BaseException | type[BaseException],
        exc: type[BaseException],
        predicate: int,
    ) -> None:
        try:
            self.disable()
            distance_true = 0.0
            distance_false = 0.0
            # Might be necessary when using Proxies.
            err = tt.unwrap(err)
            exc = tt.unwrap(exc)

            if isinstance(err, BaseException):
                err = type(err)

            if given_exception_matches(err, exc):
                distance_false = 1.0
            else:
                distance_true = 1.0

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    @_early_return
    def track_line_visit(self, line_id: int) -> None:  # noqa: D102
        self._thread_local_state.trace.covered_line_ids.add(line_id)

    def _update_metrics(self, distance_false: float, distance_true: float, predicate: int):
        assert distance_true >= 0.0, "True distance cannot be negative"
        assert distance_false >= 0.0, "False distance cannot be negative"
        assert (distance_true == 0.0) ^ (distance_false == 0.0), (
            "Exactly one distance must be 0.0, i.e., one branch must be taken."
        )
        self._thread_local_state.trace.update_predicate_distances(
            distance_true=distance_true,
            distance_false=distance_false,
            predicate=predicate,
        )

    @_early_return
    def track_generic(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        self._thread_local_state.trace.add_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def _extract_arguments(
        self, var_name: VariableName, var_value: object
    ) -> tuple[str, int, bool, bool]:
        var_address = id(var_value)
        var_type = type(var_value)

        if isinstance(var_name, CellVar | FreeVar):
            var_name = var_name.name

        # Determine if this is a mutable type
        mutable_type = var_type not in immutable_types

        # Determine if this is a definition of a completely new object
        # (required later during slicing)
        object_creation = (
            bool(var_address) and var_address not in self._thread_local_state.trace.object_addresses
        )

        if object_creation:
            self._thread_local_state.trace.object_addresses.add(var_address)

        return var_name, var_address, mutable_type, object_creation

    @_early_return
    def track_memory_access(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        var_name: VariableName | tuple[VariableName, VariableName],
        var_value: object,
    ) -> None:
        # IMPORT_NAMEs may not have arguments
        assert var_name or opname[opcode] in version.IMPORT_NAME_NAMES, (
            "A memory access instruction must have an argument or be an import"
        )

        arg_name: str | tuple[str, str]
        arg_address: int | tuple[int, int]
        mutable_type: bool | tuple[bool, bool]
        object_creation: bool | tuple[bool, bool]
        if (
            isinstance(var_name, tuple)
            and isinstance(var_value, tuple)
            and len(var_name) == 2
            and len(var_value) == 2
        ):
            arg_name0, arg_address0, mutable_type0, object_creation0 = self._extract_arguments(
                var_name[0], var_value[0]
            )
            arg_name1, arg_address1, mutable_type1, object_creation1 = self._extract_arguments(
                var_name[1], var_value[1]
            )
            arg_name = (arg_name0, arg_name1)
            arg_address = (arg_address0, arg_address1)
            mutable_type = (mutable_type0, mutable_type1)
            object_creation = (object_creation0, object_creation1)
        elif isinstance(var_name, (str, CellVar, FreeVar)):
            arg_name, arg_address, mutable_type, object_creation = self._extract_arguments(
                var_name, var_value
            )
        else:
            raise AssertionError(f"Unexpected argument types: {var_name}, {var_value}")

        self._thread_local_state.trace.add_memory_instruction(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            arg_name,
            arg_address,
            mutable_type,
            object_creation,
        )

    @_early_return
    def track_attribute_access(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        attr_name: str | None,
        obj: object,
    ) -> None:
        arg_type: type
        if attr_name is None:
            attr_name = "None"
            src_address = id(obj)
            arg_address = -1
            arg_type = type(None)
        else:
            src_address = self.attribute_lookup(obj, attr_name)
            attr_value = getattr(obj, attr_name)
            arg_address = id(attr_value)
            arg_type = type(attr_value)

        # Different built-in methods and functions often have the same address when
        # accessed sequentially.
        # The address is not recorded in such cases.
        if arg_type is BuiltinMethodType or arg_type is BuiltinFunctionType:
            arg_address = -1

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        is_method = arg_type is MethodType or arg_type is BuiltinMethodType

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
            is_method,
        )

    @_early_return
    def track_jump(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        target_id: int,
    ) -> None:
        self._thread_local_state.trace.add_jump_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, target_id
        )

    @_early_return
    def track_call(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: int,
    ) -> None:
        self._thread_local_state.trace.add_call_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, arg
        )

    @_early_return
    def track_return(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        self._thread_local_state.trace.add_return_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    @_early_return
    def track_exception_assertion(  # noqa: D102
        self, statement: stmt.Statement
    ) -> None:
        assert statement.has_only_exception_assertion()
        trace = self._thread_local_state.trace
        error_call_position = len(trace.executed_instructions) - 1
        trace.executed_assertions.append(
            ExecutedAssertion(
                error_call_position,
                next(iter(statement.assertions)),
            )
        )

    @_early_return
    def track_assertion_position(self, assertion: ass.Assertion) -> None:  # noqa: D102
        exec_instr = self.get_trace().executed_instructions

        boolean_jump = len(exec_instr) - 1
        for instruction in reversed(exec_instr):
            if (
                is_true_branch := version.get_branch_type(instruction.opcode)
            ) is not None and is_true_branch:
                break
            boolean_jump -= 1
        assert boolean_jump != -1, "Node in code object did not contain a boolean jump instruction"

        self._thread_local_state.trace.executed_assertions.append(
            ExecutedAssertion(
                boolean_jump,
                assertion,
            )
        )

    @staticmethod
    def attribute_lookup(object_type, attribute: str) -> int:
        """Check the dictionary of classes making up the MRO (method resolution order).

        It is inspired by the `_PyType_Lookup` C function in CPython.

        Args:
            object_type: The type object to check
            attribute: the attribute to check for in the class. It must be a data descriptor
                       to be prioritized here.

        Returns:
            The id of the object type or the class if it has the attribute, -1 otherwise
        """
        for clss in type(object_type).__mro__:
            if attribute in clss.__dict__ and inspect.isdatadescriptor(
                clss.__dict__.get(attribute)
            ):
                # Class in the MRO hierarchy has attribute
                # Class has attribute and attribute is a data descriptor
                return id(clss)

        # This would lead to an infinite recursion and thus a crash of the program
        if attribute in {"__getattr__", "__getitem__"}:
            return -1
        # Check if the dictionary of the object on which lookup is performed
        if (
            hasattr(object_type, "__dict__")
            and object_type.__dict__
            and attribute in object_type.__dict__
        ):
            return id(object_type)
        if (
            hasattr(object_type, "__slots__")
            and object_type.__slots__
            and attribute in object_type.__slots__
        ):
            return id(object_type)

        # Check if attribute in MRO hierarchy (no need for data descriptor)
        for clss in type(object_type).__mro__:
            if attribute in clss.__dict__:
                return id(clss)

        return -1

    def __repr__(self) -> str:
        return "ExecutionTracer"

    def __getstate__(self) -> dict:
        return self.state

    def __setstate__(self, state: dict) -> None:
        self.state = state


class InstrumentationExecutionTracer(AbstractExecutionTracer):  # noqa: PLR0904
    """An `InstrumentationExecutionTracer` is a sort of proxy for an `ExecutionTracer`.

    This was done because when a module is instrumented, instructions are inserted into
    its bytecode and refer directly to a tracer. This means that without the use of a
    proxy, it would be impossible to modify the tracer, as there are direct references
    between the bytecode instructions and the tracer. By adding a proxy between
    the bytecode and the tracer, this ensures that the bytecode only has direct
    references to the proxy but no references to the tracer, so the tracer can be
    modified without any problems.
    """

    def __init__(self, tracer: ExecutionTracer):  # noqa: D107
        self._tracer = tracer

    @property
    def tracer(self) -> ExecutionTracer:  # noqa: D102
        return self._tracer

    @tracer.setter
    def tracer(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

    def __enter__(self) -> Self:
        self._tracer.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._tracer.__exit__(exc_type, exc_value, traceback)

    def check(self) -> None:  # noqa: D102
        self._tracer.check()

    @property
    def import_trace(self) -> ExecutionTrace:  # noqa: D102
        return self._tracer.import_trace

    def reset(self) -> None:  # noqa: D102
        self._tracer.reset()

    def store_import_trace(self) -> None:  # noqa: D102
        self._tracer.store_import_trace()

    def init_trace(self) -> None:  # noqa: D102
        self._tracer.init_trace()

    def is_disabled(self) -> bool:  # noqa: D102
        return self._tracer.is_disabled()

    def enable(self) -> None:  # noqa: D102
        self._tracer.enable()

    def disable(self) -> None:  # noqa: D102
        self._tracer.disable()

    def stop(self) -> None:  # noqa: D102
        self._tracer.stop()

    def get_trace(self) -> ExecutionTrace:  # noqa: D102
        return self._tracer.get_trace()

    def executed_code_object(self, code_object_id: int) -> None:  # noqa: D102
        self._tracer.executed_code_object(code_object_id)

    def executed_compare_predicate(  # noqa: D102
        self, value1, value2, predicate: int, cmp_op: PynguinCompare
    ) -> None:
        self._tracer.executed_compare_predicate(value1, value2, predicate, cmp_op)

    def executed_bool_predicate(self, value, predicate: int) -> None:  # noqa: D102
        self._tracer.executed_bool_predicate(value, predicate)

    def executed_exception_match(  # noqa: D102
        self,
        err: BaseException | type[BaseException],
        exc: type[BaseException],
        predicate: int,
    ) -> None:
        self._tracer.executed_exception_match(err, exc, predicate)

    def track_line_visit(self, line_id: int) -> None:  # noqa: D102
        self._tracer.track_line_visit(line_id)

    def track_generic(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        self._tracer.track_generic(module, code_object_id, node_id, opcode, lineno, offset)

    def track_memory_access(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        var_name: VariableName | tuple[VariableName, VariableName],
        var_value: object,
    ) -> None:
        self._tracer.track_memory_access(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            var_name,
            var_value,
        )

    def track_attribute_access(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        attr_name: str | None,
        obj: object,
    ) -> None:
        self._tracer.track_attribute_access(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            attr_name,
            obj,
        )

    def track_jump(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        target_id: int,
    ) -> None:
        self._tracer.track_jump(module, code_object_id, node_id, opcode, lineno, offset, target_id)

    def track_call(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: int,
    ) -> None:
        self._tracer.track_call(module, code_object_id, node_id, opcode, lineno, offset, arg)

    def track_return(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        self._tracer.track_return(module, code_object_id, node_id, opcode, lineno, offset)

    def track_exception_assertion(  # noqa: D102
        self, statement: stmt.Statement
    ) -> None:
        self._tracer.track_exception_assertion(statement)

    def track_assertion_position(self, assertion: ass.Assertion) -> None:  # noqa: D102
        self._tracer.track_assertion_position(assertion)

    def __repr__(self) -> str:
        return "InstrumentationExecutionTracer"

    def __getstate__(self) -> dict:
        return {"tracer": self._tracer}

    def __setstate__(self, state: dict) -> None:
        self._tracer = state["tracer"]
