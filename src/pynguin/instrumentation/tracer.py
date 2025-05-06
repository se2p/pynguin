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

from abc import ABC
from abc import abstractmethod
from collections.abc import Sized
from dataclasses import dataclass
from dataclasses import field
from math import inf
from types import BuiltinFunctionType
from types import BuiltinMethodType

from bytecode import CellVar
from bytecode import FreeVar

import pynguin.assertion.assertion as ass
import pynguin.instrumentation.instrumentation as instr
import pynguin.slicer.executedinstruction as ei
import pynguin.testcase.statement as stmt
import pynguin.utils.opcodes as op
import pynguin.utils.typetracing as tt

from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.type_utils import given_exception_matches
from pynguin.utils.type_utils import is_bytes
from pynguin.utils.type_utils import is_numeric
from pynguin.utils.type_utils import is_string
from pynguin.utils.type_utils import string_distance
from pynguin.utils.type_utils import string_le_distance
from pynguin.utils.type_utils import string_lt_distance


immutable_types = (int, float, complex, str, tuple, frozenset, bytes)


@dataclass
class ExecutedAssertion:
    """Data class for assertions of a testcase traced during execution for slicing."""

    # the code object containing the executed assertion
    code_object_id: int
    # the node containing the executed assertion
    node_id: int
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
        self.executed_assertions.extend(
            ExecutedAssertion(
                executed_assertion.code_object_id,
                executed_assertion.node_id,
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
        arg_name: str,
        arg_address: int,
        is_mutable_type: bool,  # noqa: FBT001
        object_creation: bool,  # noqa: FBT001
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
class SubjectProperties:
    """Contains properties about the subject under test."""

    # Maps all known ids of Code Objects to meta information
    existing_code_objects: dict[int, instr.CodeObjectMetaData] = field(default_factory=dict)

    # Stores which of the existing code objects do not contain a branch, i.e.,
    # they do not contain a predicate. Every code object is initially seen as
    # branch-less until a predicate is registered for it.
    branch_less_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)

    # Maps all known ids of predicates to meta information
    existing_predicates: dict[int, instr.PredicateMetaData] = field(default_factory=dict)

    # stores which line id represents which line in which file
    existing_lines: dict[int, LineMetaData] = field(default_factory=dict)

    # stores known memory attribute object addresses
    object_addresses: OrderedSet[int] = field(default_factory=OrderedSet)


class AbstractExecutionTracer(ABC):  # noqa: PLR0904
    """An abstract execution tracer.

    The results are stored in an execution trace.
    """

    @property
    @abstractmethod
    def current_thread_identifier(self) -> int | None:
        """Get the current thread identifier.

        Returns:
            The current thread identifier
        """

    @current_thread_identifier.setter
    @abstractmethod
    def current_thread_identifier(self, current: int) -> None:
        """Set the current thread identifier.

        Tracing calls from any other thread are ignored.

        Args:
            current: the current thread
        """

    @property
    @abstractmethod
    def import_trace(self) -> ExecutionTrace:
        """The trace that was generated when the SUT was imported.

        Returns:
            The execution trace after executing the import statements
        """

    @abstractmethod
    def get_subject_properties(self) -> SubjectProperties:
        """Provide known data.

        Returns:
            The known data about the execution
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
    def get_trace(self) -> ExecutionTrace:
        """Get the trace with the current information.

        Returns:
            The current execution trace
        """

    @abstractmethod
    def register_code_object(self, meta: instr.CodeObjectMetaData) -> int:
        """Declare that a code object exists.

        Args:
            meta: the code objects existing

        Returns:
            the id of the code object, which can be used to identify the object
            during instrumentation.
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
    def register_predicate(self, meta: instr.PredicateMetaData) -> int:
        """Declare that a predicate exists.

        Args:
            meta: Metadata about the predicates

        Returns:
            the id of the predicate, which can be used to identify the predicate
            during instrumentation.
        """

    @abstractmethod
    def executed_compare_predicate(
        self, value1, value2, predicate: int, cmp_op: instr.PynguinCompare
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
    def executed_exception_match(self, err, exc, predicate: int):
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
    def register_line(self, code_object_id: int, file_name: str, line_number: int) -> int:
        """Tracks the existence of a line.

        Args:
            code_object_id: The id of the code object that contains the line
            file_name: The file in which the statement is
            line_number: The line of the statement to track

        Returns:
            the id of the registered line
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

    @abstractmethod
    def track_memory_access(  # noqa: PLR0917
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: str | CellVar | FreeVar,
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

    @abstractmethod
    def track_attribute_access(  # noqa: PLR0917
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

    @abstractmethod
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

    @abstractmethod
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

    @classmethod
    def attribute_lookup(cls, object_type, attribute: str) -> int:
        """Check the dictionary of classes making up the MRO (_PyType_Lookup).

        The attribute must be a data descriptor to be prioritized here

        Args:
            object_type: The type object to check
            attribute: the attribute to check for in the class

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

    @abstractmethod
    def lineids_to_linenos(self, line_ids: OrderedSet[int]) -> OrderedSet[int]:
        """Convenience method to translate line ids to line numbers.

        Args:
            line_ids: The ids that should be translated.

        Returns:
            The line numbers.
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
        self.subject_properties = SubjectProperties()
        # Contains the trace information that is generated when a module is imported
        self._import_trace = ExecutionTrace()

        # Thread local state
        self._thread_local_state = ExecutionTracer.TracerLocalState()

        self.init_trace()
        self._current_thread_identifier: int | None = None

    @property
    def current_thread_identifier(self) -> int | None:  # noqa: D102
        return self._current_thread_identifier

    @current_thread_identifier.setter
    def current_thread_identifier(self, current: int) -> None:
        self._current_thread_identifier = current

    @property
    def import_trace(self) -> ExecutionTrace:  # noqa: D102
        copied = ExecutionTrace()
        copied.merge(self._import_trace)
        return copied

    def get_subject_properties(self) -> SubjectProperties:  # noqa: D102
        return self.subject_properties

    @property
    def state(self) -> dict:
        """Get the current state.

        Returns:
            The current state
        """
        return {
            "subject_properties": self.subject_properties,
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
        self.subject_properties = state["subject_properties"]
        self._import_trace = state["import_trace"]
        self._current_thread_identifier = state["current_thread_identifier"]
        self._thread_local_state = ExecutionTracer.TracerLocalState()
        self._thread_local_state.enabled = state["thread_local_state"]["enabled"]
        self._thread_local_state.trace = state["thread_local_state"]["trace"]

    def reset(self) -> None:  # noqa: D102
        self.subject_properties = SubjectProperties()
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

    def get_trace(self) -> ExecutionTrace:  # noqa: D102
        return self._thread_local_state.trace

    def register_code_object(self, meta: instr.CodeObjectMetaData) -> int:  # noqa: D102
        code_object_id = len(self.subject_properties.existing_code_objects)
        self.subject_properties.existing_code_objects[code_object_id] = meta
        self.subject_properties.branch_less_code_objects.add(code_object_id)
        return code_object_id

    def executed_code_object(self, code_object_id: int) -> None:  # noqa: D102
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        assert code_object_id in self.subject_properties.existing_code_objects, (
            "Cannot trace unknown code object"
        )
        self._thread_local_state.trace.executed_code_objects.add(code_object_id)

    def register_predicate(self, meta: instr.PredicateMetaData) -> int:  # noqa: D102
        predicate_id = len(self.subject_properties.existing_predicates)
        self.subject_properties.existing_predicates[predicate_id] = meta
        self.subject_properties.branch_less_code_objects.discard(meta.code_object_id)
        return predicate_id

    def executed_compare_predicate(  # noqa: D102, C901
        self, value1, value2, predicate: int, cmp_op: instr.PynguinCompare
    ) -> None:
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        try:
            self.disable()
            assert predicate in self.subject_properties.existing_predicates, (
                "Cannot trace unknown predicate"
            )
            value1 = tt.unwrap(value1)
            value2 = tt.unwrap(value2)

            match cmp_op:
                case instr.PynguinCompare.EQ:
                    distance_true, distance_false = _eq(value1, value2), _neq(value1, value2)
                case instr.PynguinCompare.NE:
                    distance_true, distance_false = _neq(value1, value2), _eq(value1, value2)
                case instr.PynguinCompare.LT:
                    distance_true, distance_false = (
                        _lt(value1, value2),
                        _le(value2, value1),
                    )
                case instr.PynguinCompare.LE:
                    distance_true, distance_false = (
                        _le(value1, value2),
                        _lt(value2, value1),
                    )
                case instr.PynguinCompare.GT:
                    distance_true, distance_false = (
                        _lt(value2, value1),
                        _le(value1, value2),
                    )
                case instr.PynguinCompare.GE:
                    distance_true, distance_false = (
                        _le(value2, value1),
                        _lt(value1, value2),
                    )
                case instr.PynguinCompare.IN:
                    distance_true, distance_false = (
                        _in(value1, value2),
                        _nin(value1, value2),
                    )
                case instr.PynguinCompare.NOT_IN:
                    distance_true, distance_false = (
                        _nin(value1, value2),
                        _in(value1, value2),
                    )
                case instr.PynguinCompare.IS:
                    distance_true, distance_false = (
                        _is(value1, value2),
                        _isn(value1, value2),
                    )
                case instr.PynguinCompare.IS_NOT:
                    distance_true, distance_false = (
                        _isn(value1, value2),
                        _is(value1, value2),
                    )
                case _:
                    raise AssertionError("Unknown compare op")
            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    def executed_bool_predicate(self, value, predicate: int) -> None:  # noqa: D102
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        try:
            self.disable()
            assert predicate in self.subject_properties.existing_predicates, (
                "Cannot trace unknown predicate"
            )
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

    def executed_exception_match(self, err, exc, predicate: int):  # noqa: D102
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        try:
            self.disable()
            assert predicate in self.subject_properties.existing_predicates, (
                "Cannot trace unknown predicate"
            )
            distance_true = 0.0
            distance_false = 0.0
            # Might be necessary when using Proxies.
            err = tt.unwrap(err)
            exc = tt.unwrap(exc)
            if given_exception_matches(err, exc):
                distance_false = 1.0
            else:
                distance_true = 1.0

            self._update_metrics(distance_false, distance_true, predicate)
        finally:
            self.enable()

    def track_line_visit(self, line_id: int) -> None:  # noqa: D102
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        self._thread_local_state.trace.covered_line_ids.add(line_id)

    def register_line(  # noqa: D102
        self, code_object_id: int, file_name: str, line_number: int
    ) -> int:
        line_meta = LineMetaData(code_object_id, file_name, line_number)
        if line_meta not in self.subject_properties.existing_lines.values():
            line_id = len(self.subject_properties.existing_lines)
            self.subject_properties.existing_lines[line_id] = line_meta
        else:
            index = list(self.subject_properties.existing_lines.values()).index(line_meta)
            line_id = list(self.subject_properties.existing_lines.keys())[index]
        return line_id

    def _update_metrics(self, distance_false: float, distance_true: float, predicate: int):
        assert predicate in self.subject_properties.existing_predicates, (
            "Cannot update unknown predicate"
        )
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

    def track_generic(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def track_memory_access(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
        arg: str | CellVar | FreeVar,
        arg_address: int,
        arg_type: type,
    ) -> None:
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        if not arg and opcode != op.IMPORT_NAME:  # IMPORT_NAMEs may not have arguments
            raise ValueError("A memory access instruction must have an argument")
        if isinstance(arg, CellVar | FreeVar):
            arg = arg.name

        # Determine if this is a mutable type
        mutable_type = True
        if arg_type in immutable_types:
            mutable_type = False

        # Determine if this is a definition of a completely new object
        # (required later during slicing)
        object_creation = False
        if arg_address and arg_address not in self.subject_properties.object_addresses:
            object_creation = True
            self.subject_properties.object_addresses.add(arg_address)

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

    def track_attribute_access(  # noqa: PLR0917, D102
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
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

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
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_jump_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, target_id
        )

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
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_call_instruction(
            module, code_object_id, node_id, opcode, lineno, offset, arg
        )

    def track_return(  # noqa: PLR0917, D102
        self,
        module: str,
        code_object_id: int,
        node_id: int,
        opcode: int,
        lineno: int,
        offset: int,
    ) -> None:
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        self._thread_local_state.trace.add_return_instruction(
            module, code_object_id, node_id, opcode, lineno, offset
        )

    def register_exception_assertion(  # noqa: D102
        self, statement: stmt.Statement
    ) -> None:
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

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
                    next(iter(statement.assertions)),
                )
            )

    def register_assertion_position(  # noqa: D102
        self, code_object_id: int, node_id: int, assertion: ass.Assertion
    ) -> None:
        if threading.current_thread().ident != self._current_thread_identifier:
            raise RuntimeError("The current thread shall not be executed any more, thus I kill it.")

        if self.is_disabled():
            return

        exec_instr = self.get_trace().executed_instructions
        pop_jump_if_true_position = len(exec_instr) - 1
        for instruction in reversed(exec_instr):
            if instruction.opcode == op.POP_JUMP_IF_TRUE:
                break
            pop_jump_if_true_position -= 1
        assert pop_jump_if_true_position != -1, (
            "Node in code object did not contain a POP_JUMP_IF_TRUE instruction"
        )

        self._thread_local_state.trace.executed_assertions.append(
            ExecutedAssertion(
                code_object_id,
                node_id,
                pop_jump_if_true_position,
                assertion,
            )
        )

    def __repr__(self) -> str:
        return "ExecutionTracer"

    def lineids_to_linenos(  # noqa: D102
        self, line_ids: OrderedSet[int]
    ) -> OrderedSet[int]:
        return OrderedSet([
            self.subject_properties.existing_lines[line_id].line_number for line_id in line_ids
        ])

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

    @property
    def current_thread_identifier(self) -> int | None:  # noqa: D102
        return self._tracer.current_thread_identifier

    @current_thread_identifier.setter
    def current_thread_identifier(self, current: int) -> None:
        self._tracer.current_thread_identifier = current

    @property
    def import_trace(self) -> ExecutionTrace:  # noqa: D102
        return self._tracer.import_trace

    def get_subject_properties(self) -> SubjectProperties:  # noqa: D102
        return self._tracer.get_subject_properties()

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

    def get_trace(self) -> ExecutionTrace:  # noqa: D102
        return self._tracer.get_trace()

    def register_code_object(self, meta: instr.CodeObjectMetaData) -> int:  # noqa: D102
        return self._tracer.register_code_object(meta)

    def executed_code_object(self, code_object_id: int) -> None:  # noqa: D102
        self._tracer.executed_code_object(code_object_id)

    def register_predicate(self, meta: instr.PredicateMetaData) -> int:  # noqa: D102
        return self._tracer.register_predicate(meta)

    def executed_compare_predicate(  # noqa: D102
        self, value1, value2, predicate: int, cmp_op: instr.PynguinCompare
    ) -> None:
        self._tracer.executed_compare_predicate(value1, value2, predicate, cmp_op)

    def executed_bool_predicate(self, value, predicate: int) -> None:  # noqa: D102
        self._tracer.executed_bool_predicate(value, predicate)

    def executed_exception_match(self, err, exc, predicate: int):  # noqa: D102
        self._tracer.executed_exception_match(err, exc, predicate)

    def track_line_visit(self, line_id: int) -> None:  # noqa: D102
        self._tracer.track_line_visit(line_id)

    def register_line(  # noqa: D102
        self, code_object_id: int, file_name: str, line_number: int
    ) -> int:
        return self._tracer.register_line(code_object_id, file_name, line_number)

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
        arg: str | CellVar | FreeVar,
        arg_address: int,
        arg_type: type,
    ) -> None:
        self._tracer.track_memory_access(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            arg,
            arg_address,
            arg_type,
        )

    def track_attribute_access(  # noqa: PLR0917, D102
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
        self._tracer.track_attribute_access(
            module,
            code_object_id,
            node_id,
            opcode,
            lineno,
            offset,
            attr_name,
            src_address,
            arg_address,
            arg_type,
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

    def register_exception_assertion(  # noqa: D102
        self, statement: stmt.Statement
    ) -> None:
        self._tracer.register_exception_assertion(statement)

    def register_assertion_position(  # noqa: D102
        self, code_object_id: int, node_id: int, assertion: ass.Assertion
    ) -> None:
        self._tracer.register_assertion_position(code_object_id, node_id, assertion)

    def lineids_to_linenos(  # noqa: D102
        self, line_ids: OrderedSet[int]
    ) -> OrderedSet[int]:
        return self._tracer.lineids_to_linenos(line_ids)

    def __repr__(self) -> str:
        return "InstrumentationExecutionTracer"

    def __getstate__(self) -> dict:
        return {"tracer": self._tracer}

    def __setstate__(self, state: dict) -> None:
        self._tracer = state["tracer"]
