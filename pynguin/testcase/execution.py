#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Contains all code related to test-case execution."""
from __future__ import annotations

import ast
import contextlib
import logging
import os
import sys
import threading
from abc import abstractmethod
from dataclasses import dataclass, field
from importlib import reload
from math import inf
from queue import Empty, Queue
from types import CodeType, ModuleType
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type

import astor
from bytecode import Compare
from jellyfish import levenshtein_distance
from ordered_set import OrderedSet

import pynguin.analyses.controlflow.programgraph as pg
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.utils.namingscope as ns
from pynguin.analyses.controlflow.cfg import CFG
from pynguin.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pynguin.utils.type_utils import (
    given_exception_matches,
    is_bytes,
    is_numeric,
    is_string,
)

if TYPE_CHECKING:
    import pynguin.assertion.statetrace as ot
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
        self._local_namespace: Dict[str, Any] = {}
        self._variable_names = ns.NamingScope()
        self._modules_aliases = ns.NamingScope(prefix="module")
        self._global_namespace: Dict[str, ModuleType] = {}

    @property
    def local_namespace(self) -> Dict[str, Any]:
        """The local namespace.

        Returns:
            The local namespace
        """
        return self._local_namespace

    def get_reference_value(self, reference: vr.Reference) -> Any:
        """Resolve the given reference in this execution context.

        Args:
            reference: The reference to resolve.

        Raises:
            ValueError: If the root of the reference can not be resolved.

        Returns:
            The value that is resolved.
        """
        root, *attrs = reference.get_names(self._variable_names, self._modules_aliases)
        if root in self._local_namespace:
            # Check local namespace first
            res = self._local_namespace[root]
        elif root in self._global_namespace:
            # Check global namespace after
            res = self._global_namespace[root]
        else:
            # Root name is not defined?
            raise ValueError("Root not found in this context")
        for attr in attrs:
            res = getattr(res, attr)
        return res

    @property
    def global_namespace(self) -> Dict[str, ModuleType]:
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
        modules_before = len(self._modules_aliases)
        visitor = stmt_to_ast.StatementToAstVisitor(
            self._modules_aliases, self._variable_names
        )
        statement.accept(visitor)
        if modules_before != len(self._modules_aliases):
            # new module added
            # TODO(fk) cleaner solution?
            self._global_namespace = self._create_global_namespace(
                self._modules_aliases
            )
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

    def _create_global_namespace(
        self,
        modules_aliases: ns.NamingScope,
    ) -> Dict[str, ModuleType]:
        """Provides the required modules under the given aliases.

        Args:
            modules_aliases: The module aliases

        Returns:
            A dictionary of module aliases and the corresponding module
        """
        global_namespace: Dict[str, ModuleType] = {}
        for required_module, module_name in modules_aliases:
            global_namespace[module_name] = self._module_provider.get_module(
                required_module
            )
        return global_namespace


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
        exception: Optional[Exception] = None,
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
        self._exceptions: Dict[int, Exception] = {}
        self._output_traces: Dict[Type, ot.StateTrace] = {}
        self._execution_trace: Optional[ExecutionTrace] = None
        self._timeout = timeout

    @property
    def timeout(self) -> bool:
        """Did a timeout occur during the execution?

        Returns:
            True, if a timeout occurred.
        """
        return self._timeout

    @property
    def exceptions(self) -> Dict[int, Exception]:
        """Provide a map of statements indices that threw an exception.

        Returns:
             A map of statement indices to their raised exception
        """
        return self._exceptions

    @property
    def output_traces(self) -> Dict[Type, ot.StateTrace]:
        """Provides the gathered state traces.

        Returns:
            the gathered output traces.

        """
        return self._output_traces

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

    def add_output_trace(self, trace_type: Type, trace: ot.StateTrace) -> None:
        """Add the given trace to the recorded output traces.

        Args:
            trace_type: the type of trace.
            trace: the trace to store.

        """
        self._output_traces[trace_type] = trace

    def has_test_exceptions(self) -> bool:
        """Returns true if any exceptions were thrown during the execution.

        Returns:
            Whether or not the test has exceptions
        """
        return bool(self._exceptions)

    def report_new_thrown_exception(self, stmt_idx: int, ex: Exception) -> None:
        """Report an exception that was thrown during execution.

        Args:
            stmt_idx: the index of the statement, that caused the exception
            ex: the exception
        """
        self._exceptions[stmt_idx] = ex

    def get_first_position_of_thrown_exception(self) -> Optional[int]:
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
class FileStatementData:
    """Tracks information about statements inside one file."""

    # name of the file of the module that is being tracked
    file_name: str

    # the visited statements and the number of times they were visited
    visited_statements: Dict[int, int] = field(default_factory=dict)

    # overall available statements of a file
    statements: OrderedSet[int] = field(default_factory=OrderedSet)

    # set of ids of the code_objects created for this file
    code_objects: OrderedSet[int] = field(default_factory=OrderedSet)

    def visit_statement(self, line_number: int, code_object_id: int) -> None:
        """Increment the visits of an already visited statement or add a number to the visited
        statements with its first visit already being counted.

        Args:
            line_number: The line number of the visited statement.
            code_object_id: The id of the code object currently containing the line
        """
        self.code_objects.add(code_object_id)
        if line_number in self.visited_statements:
            self.visited_statements[line_number] += 1
        else:
            self.visited_statements[line_number] = 1

    def track_statement(self, line_number: int) -> None:
        """Add a statement in a line number to the tracked lines

        Args:
            line_number: The tracked line number of an executed statement.
        """
        self.statements.add(line_number)


@dataclass
class ExecutionTrace:
    """Stores trace information about the execution."""

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: Dict[int, int] = field(default_factory=dict)
    true_distances: Dict[int, float] = field(default_factory=dict)
    false_distances: Dict[int, float] = field(default_factory=dict)
    file_trackers: Dict[str, FileStatementData] = field(default_factory=dict)

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
        self._merge_file_trackers(self.file_trackers, other.file_trackers)

    @staticmethod
    def _merge_file_trackers(target: Dict[str, FileStatementData], source: Dict[str, FileStatementData]) -> None:
        """
        Merge source file statement data into target file statement data.
        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key in source:
            if key in target:
                target[key].statements.update(source[key].statements)
                target[key].code_objects.update(source[key].code_objects)
                for line in source[key].visited_statements:
                    if line in target[key].visited_statements:
                        source[key].visited_statements[line] += target[key].visited_statements[line]
                    else:
                        source[key].visited_statements[line] = target[key].visited_statements[line]
            else:
                target[key] = source[key]

    @staticmethod
    def _merge_min(target: Dict[int, float], source: Dict[int, float]) -> None:
        """Merge source into target. Minimum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = min(target.get(key, inf), value)

    @staticmethod
    def _merge_max(target: Dict[int, float], source: Dict[int, float]) -> None:
        """Merge source into target. Maximum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = max(target.get(key, -inf), value)


@dataclass
class CodeObjectMetaData:
    """Stores meta data of a code object."""

    # The raw code object.
    code_object: CodeType

    # Id of the parent code object, if any
    parent_code_object_id: Optional[int]

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
    node: pg.ProgramGraphNode


@dataclass
class KnownData:
    """Contains known code objects and predicates.
    FIXME(fk) better class name...
    """

    # Maps all known ids of Code Objects to meta information
    existing_code_objects: Dict[int, CodeObjectMetaData] = field(default_factory=dict)

    # Stores which of the existing code objects do not contain a branch, i.e.,
    # they do not contain a predicate. Every code object is initially seen as
    # branch-less until a predicate is registered for it.
    branch_less_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)

    # Maps all known ids of predicates to meta information
    existing_predicates: Dict[int, PredicateMetaData] = field(default_factory=dict)


class ExecutionTracer:
    """Tracks branch distances during execution.
    The results are stored in an execution trace."""

    _logger = logging.getLogger(__name__)

    # Contains static information about how branch distances
    # for certain op codes should be computed.
    # The returned tuple for each computation is (true distance, false distance).
    # pylint: disable=arguments-out-of-order
    _DISTANCE_COMPUTATIONS: Dict[Compare, Callable[[Any, Any], Tuple[float, float]]] = {
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
        self._current_thread_identifier: Optional[int] = None

    @property
    def current_thread_identifier(self) -> Optional[int]:
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

    def get_file_trackers(self) -> Dict[str, FileStatementData]:
        return self._trace.file_trackers

    def track_statement_visit(self, file_name: str, line_number: int, code_object_id: int) -> None:
        """Tracks the visit of a statement.

        Args:
            file_name: The file in which the statement is
            line_number: The line of the statement that was tracked
            code_object_id: the id of the code object which while executed covered the line
        """
        if file_name not in self._trace.file_trackers:
            self._trace.file_trackers[file_name] = FileStatementData(file_name)
        self._trace.file_trackers[file_name].visit_statement(line_number, code_object_id)

    def track_statement(self, file_name: str, line_number: int) -> None:
        """Tracks the existence of a statement.

        Args:
            file_name: The file in which the statement is
            line_number: The line of the statement to track
        """
        if file_name not in self._trace.file_trackers:
            self._trace.file_trackers[file_name] = FileStatementData(file_name)
        self._trace.file_trackers[file_name].track_statement(line_number)

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

    def __repr__(self) -> str:
        return "ExecutionTracer"


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
        self._mutated_module_aliases: Dict[str, ModuleType] = {}

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
        self, tracer: ExecutionTracer, module_provider: Optional[ModuleProvider] = None
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
        self._observers: List[ExecutionObserver] = []

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
    ) -> Optional[Exception]:
        ast_node = exec_ctx.executable_node_for(statement)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("Executing %s", astor.to_source(ast_node))
        code = compile(ast_node, "<ast>", "exec")
        try:
            # pylint: disable=exec-used
            exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
        except Exception as err:  # pylint: disable=broad-except
            failed_stmt = astor.to_source(ast_node)
            TestCaseExecutor._logger.debug(
                "Failed to execute statement:\n%s%s", failed_stmt, err.args
            )
            return err
        return None

    def _after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Optional[Exception],
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
