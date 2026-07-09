#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a libcst-backed test case implementation."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Literal

import libcst as cst

from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class _NameCollector(cst.CSTTransformer):
    """Collect all Name node values encountered during a CST traversal."""

    def __init__(self, *, filter_targets: bool = False) -> None:
        """Initializes the name collector.

        Args:
            filter_targets: Whether to filter assignment targets.
        """
        self.names: set[str] = set()
        self._filter_targets = filter_targets
        self._is_in_target: int = 0

    def visit_AssignTarget(self, node: cst.AssignTarget) -> bool:  # noqa: N802
        if self._filter_targets:
            self._is_in_target += 1
        return True

    def leave_AssignTarget(  # noqa: N802
        self, original_node: cst.AssignTarget, updated_node: cst.AssignTarget
    ) -> cst.AssignTarget:
        if self._filter_targets:
            self._is_in_target -= 1
        return updated_node

    def visit_Name(self, node: cst.Name) -> bool:  # noqa: N802
        """Collect the name if it is not a target.

        Args:
            node: The visited Name node.

        Returns:
            True to continue traversal.
        """
        if self._is_in_target == 0:
            self.names.add(node.value)
        return True


class _VariableRenamer(cst.CSTTransformer):
    """Rename ``var_N`` style variable references according to a mapping."""

    def __init__(self, rename: dict[str, str]) -> None:
        """Initializes the renamer.

        Args:
            rename: Mapping from old variable names to new ones.
        """
        self._rename = rename

    def leave_Name(  # noqa: N802
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.Name:
        """Rename a Name node if it is in the mapping.

        Args:
            original_node: The original Name node.
            updated_node: The updated Name node.

        Returns:
            The (possibly renamed) Name node.
        """
        new = self._rename.get(updated_node.value)
        if new is not None:
            return updated_node.with_changes(value=new)
        return updated_node


@dataclasses.dataclass
class MLStatementInfo:
    """Metadata describing an ML-specific statement.

    The libcst representation has no statement subclasses, so ML-specific
    statements (ndarray literals, dtype picks, ``np.array``/tensor-constructor
    calls) are plain :class:`Statement` instances carrying this metadata
    instead. It is the successor of the old ``NdArrayStatement`` /
    ``AllowedValuesStatement`` classes and the ``FunctionStatement.should_mutate
    is False`` marker.
    """

    kind: Literal["ndarray", "allowed_values", "ml_scalar", "ml_call"]
    dtype: str | None = None
    """Numpy dtype name, e.g. ``"int32"``, for ``ndarray``/``ml_scalar`` kinds."""
    low: float | None = None
    """Lower bound of the value range used to generate the payload."""
    high: float | None = None
    """Upper bound of the value range used to generate the payload."""
    is_tuple: bool = False
    """Whether a 1-D ``ndarray`` payload is rendered/mutated as a tuple."""
    allowed_values: list[int | float | bool | str] | None = None
    """The pool of values an ``allowed_values`` statement was picked from."""


@dataclasses.dataclass
class Statement:
    """Wraps a single libcst statement node."""

    node: cst.SimpleStatementLine | cst.BaseCompoundStatement
    bound_variable: str | None = None
    bound_type: type | None = None
    assertions: list[ass.Assertion] = dataclasses.field(default_factory=list)
    accessible: GenericAccessibleObject | None = None
    ml_info: MLStatementInfo | None = None
    _used_vars: frozenset[str] | None = dataclasses.field(
        default=None, init=False, repr=False, compare=False
    )

    def has_only_exception_assertion(self) -> bool:
        """Does this statement only have an exception assertion?

        Returns:
            True, if there is only an exception assertion.
        """
        from pynguin.assertion.assertion import ExceptionAssertion  # noqa: PLC0415

        return len(self.assertions) == 1 and isinstance(
            next(iter(self.assertions)), ExceptionAssertion
        )

    def used_variables(self) -> frozenset[str]:
        """Return (and cache) the set of variable names read by this statement.

        The result is computed lazily on first call and cached, since CST nodes
        are immutable and Statement.node is never mutated after construction.

        Returns:
            The frozenset of variable names read by this statement.
        """
        if self._used_vars is None:
            collector = _NameCollector(filter_targets=True)
            self.node.visit(collector)
            self._used_vars = frozenset(collector.names)
        return self._used_vars


def _get_used_variables(stmt: Statement) -> frozenset[str]:
    """Return all variable names used (read) in *stmt*.

    Args:
        stmt: The statement to inspect.

    Returns:
        The set of variable names read by the statement.
    """
    return stmt.used_variables()


def _uses_variable(stmt: Statement, var_name: str) -> bool:
    """Return True if *var_name* is used (read) anywhere in *stmt*'s CST.

    Args:
        stmt: The statement to inspect.
        var_name: The variable name to look for.

    Returns:
        True if the variable is read by the statement.
    """
    return var_name in stmt.used_variables()


# TestCase is the central test-case representation; its public surface (statement
# editing, variable/name management, cloning, code rendering) is inherently broad and
# splitting it would not improve cohesion, hence the PLR0904 suppression below.
class TestCase:  # noqa: PLR0904
    """An ordered list of CST-backed statements forming a single test case."""

    def __init__(self) -> None:
        """Initializes an empty test case."""
        self._statements: list[Statement] = []
        self._var_counter: int = 0
        self._type_registry: dict[type, list[str]] = {}
        self._code_cache: str | None = None

    # ------------------------------------------------------------------
    # Statement management
    # ------------------------------------------------------------------

    def add_statement(self, stmt: Statement) -> None:
        """Append a statement and update the type registry.

        Args:
            stmt: The statement to append.
        """
        self._code_cache = None
        self._statements.append(stmt)
        self._register(stmt)

    def insert_statement(self, index: int, stmt: Statement) -> None:
        """Insert a statement at *index* and rebuild the type registry.

        Args:
            index: The index to insert the statement at.
            stmt: The statement to insert.
        """
        self._code_cache = None
        self._statements.insert(index, stmt)
        self._rebuild_registry()

    def remove_statement(self, index: int) -> Statement:
        """Remove and return the statement at *index*; rebuild the type registry.

        Args:
            index: The index of the statement to remove.

        Returns:
            The removed statement.
        """
        self._code_cache = None
        stmt = self._statements.pop(index)
        self._rebuild_registry()
        return stmt

    def replace_statement(self, index: int, stmt: Statement) -> None:
        """Replace the statement at *index* in-place; rebuild the type registry.

        Args:
            index: The index of the statement to replace.
            stmt: The replacement statement.
        """
        self._code_cache = None
        self._statements[index] = stmt
        self._rebuild_registry()

    def remove_statements_batch(self, indices: set[int]) -> None:
        """Remove all statements at *indices* in one pass; rebuild registry once.

        Args:
            indices: The set of indices to remove.
        """
        self._code_cache = None
        self._statements = [s for i, s in enumerate(self._statements) if i not in indices]
        self._rebuild_registry()

    def chop(self, position: int) -> None:
        """Remove all statements after *position* (keeping ``0..position``).

        Args:
            position: The index of the last statement to keep.
        """
        if position < 0:
            self.remove_statements_batch(set(range(self.size())))
            return
        self.remove_statements_batch(set(range(position + 1, self.size())))

    def forward_dependencies(self, index: int) -> set[int]:
        """Return *index* plus every later statement transitively depending on it.

        Dependencies are computed name-based: a later statement depends on the
        statement at *index* if it (transitively) reads a variable bound by a
        statement already in the dependency set.

        Args:
            index: The index of the root statement.

        Returns:
            The set of statement indices in the forward-dependency closure
            (including *index* itself).
        """
        closure = {index}
        # Names bound by statements currently in the closure.
        tainted_names: set[str] = set()
        root_var = self._statements[index].bound_variable
        if root_var is not None:
            tainted_names.add(root_var)

        changed = True
        while changed:
            changed = False
            for i in range(index + 1, self.size()):
                if i in closure:
                    continue
                stmt = self._statements[i]
                if stmt.used_variables() & tainted_names:
                    closure.add(i)
                    if stmt.bound_variable is not None and stmt.bound_variable not in tainted_names:
                        tainted_names.add(stmt.bound_variable)
                    changed = True
        return closure

    def remove_statement_with_forward_dependencies(self, index: int) -> set[int]:
        """Remove the statement at *index* and all of its forward dependencies.

        Args:
            index: The index of the statement to remove.

        Returns:
            The set of removed statement indices.
        """
        to_remove = self.forward_dependencies(index)
        self.remove_statements_batch(to_remove)
        return to_remove

    def append_test_case(self, other: TestCase) -> None:
        """Append a copy of *other*'s statements, renaming variables to fresh names.

        Variables bound by *other* are renamed to freshly allocated ``var_N`` names
        in this test case to avoid collisions with existing names.

        Args:
            other: The test case whose statements should be appended.
        """
        self.append_test_case_from(other, 0)

    def append_test_case_from(self, other: TestCase, start: int) -> None:
        """Append *other*'s statements from *start* onwards, renaming variables.

        Like :meth:`append_test_case` but begins at *start* instead of 0.
        Variables from ``other[start:]`` are still renamed consistently so that
        references between those statements are preserved and do not collide with
        names already present in this test case.

        Tail statements may also *read* variables that ``other`` bound before
        *start*.  Such free references are remapped to a type-compatible
        variable already present in this test case; when none exists, the
        statement (and every tail statement transitively depending on it) is
        dropped instead of being appended with a dangling name.

        This is the correct building block for single-point crossover: the second
        parent's tail is appended with fresh variable names, avoiding silent
        overwrites of names introduced by the first parent and NameErrors from
        references into the second parent's head.

        Args:
            other: The test case to read statements from.
            start: First index of *other* to include (inclusive).
        """
        # Variables bound by other's head (before `start`), with their types.
        head_types: dict[str, type | None] = {
            stmt.bound_variable: stmt.bound_type
            for stmt in other.statements()[:start]
            if stmt.bound_variable is not None
        }
        rename: dict[str, str] = {}
        dropped: set[str] = set()
        for stmt in other.statements()[start:]:
            # Resolve references into other's head; drop the statement if a
            # reference cannot be satisfied from this test case.
            if not self._resolve_head_references(stmt, head_types, rename, dropped):
                if stmt.bound_variable is not None:
                    dropped.add(stmt.bound_variable)
                continue

            new_node = stmt.node
            new_bound = stmt.bound_variable
            if stmt.bound_variable is not None:
                fresh = self.next_var_name()
                rename[stmt.bound_variable] = fresh
                new_bound = fresh
            if rename:
                renamed = new_node.visit(_VariableRenamer(rename))
                # ``_VariableRenamer`` only rewrites ``Name`` leaves; it never removes
                # or flattens the top-level statement node, so the result is always a
                # single statement node of the original kind.
                assert isinstance(renamed, cst.SimpleStatementLine | cst.BaseCompoundStatement)
                new_node = renamed
            self.add_statement(
                Statement(
                    node=new_node,
                    bound_variable=new_bound,
                    bound_type=stmt.bound_type,
                    assertions=list(stmt.assertions),
                    accessible=stmt.accessible,
                    ml_info=stmt.ml_info,
                )
            )

    def _resolve_head_references(
        self,
        stmt: Statement,
        head_types: dict[str, type | None],
        rename: dict[str, str],
        dropped: set[str],
    ) -> bool:
        """Resolve *stmt*'s references into the other parent's head.

        References to variables in *head_types* are remapped (via *rename*) to a
        type-compatible variable of this test case when one exists.

        Args:
            stmt: The tail statement whose references are resolved.
            head_types: Variables bound by the other parent before the split
                point, mapped to their bound types.
            rename: The rename mapping, extended in place with new remappings.
            dropped: Names bound by tail statements that were dropped.

        Returns:
            True if all references are satisfiable, False if the statement must
            be dropped.
        """
        for name in stmt.used_variables():
            if name in dropped:
                return False
            if name in rename:
                continue
            if name in head_types:
                head_type = head_types[name]
                candidates = self.variables_of_type(head_type) if head_type is not None else []
                if not candidates:
                    return False
                rename[name] = randomness.choice(candidates)
        return True

    def get_statement(self, index: int) -> Statement:
        """Return the statement at *index*.

        Args:
            index: The index of the statement.

        Returns:
            The statement at the index.
        """
        return self._statements[index]

    def statements(self) -> list[Statement]:
        """Return a shallow copy of the statement list.

        Returns:
            A shallow copy of the statement list.
        """
        return list(self._statements)

    # ------------------------------------------------------------------
    # Variable naming
    # ------------------------------------------------------------------

    def next_var_name(self) -> str:
        """Allocate and return the next ``var_N`` name.

        Returns:
            The next variable name.
        """
        name = f"var_{self._var_counter}"
        self._var_counter += 1
        return name

    def variables_of_type(self, t: type) -> list[str]:
        """Return all variable names currently bound to type *t*.

        Args:
            t: The type to look up.

        Returns:
            The list of variable names bound to the type.
        """
        return list(self._type_registry.get(t, []))

    # ------------------------------------------------------------------
    # CST / code generation
    # ------------------------------------------------------------------

    def to_module(self) -> cst.Module:
        """Return all statements as a flat ``cst.Module``.

        Returns:
            The module containing all statements.
        """
        body: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [
            s.node for s in self._statements
        ]
        if not body:
            body = [cst.SimpleStatementLine(body=[cst.Pass()])]
        return cst.Module(body=body)

    def to_code(self) -> str:
        """Return the Python source string for this test case.

        Returns:
            The source string for this test case.
        """
        if self._code_cache is None:
            self._code_cache = self.to_module().code
        return self._code_cache

    def to_test_function(self, index: int = 0) -> cst.Module:
        """Wrap all statements in ``def test_N():`` and return as a Module.

        Args:
            index: The index used to name the test function.

        Returns:
            The module containing the test function.
        """
        body: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [
            s.node for s in self._statements
        ]
        if not body:
            body = [cst.SimpleStatementLine(body=[cst.Pass()])]
        return cst.Module(
            body=[
                cst.FunctionDef(
                    name=cst.Name(f"test_{index}"),
                    params=cst.Parameters(),
                    body=cst.IndentedBlock(body=body),
                )
            ]
        )

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def size(self) -> int:
        """Return the number of statements.

        Returns:
            The number of statements.
        """
        return len(self._statements)

    def size_with_assertions(self) -> int:
        """Return the number of statements plus the total number of assertions.

        Returns:
            The number of statements plus assertions.
        """
        return sum(1 + len(s.assertions) for s in self._statements)

    def get_assertions(self) -> list[ass.Assertion]:
        """Return all assertions across all statements.

        Returns:
            The list of all assertions in this test case.
        """
        assertions: list[ass.Assertion] = []
        for stmt in self._statements:
            assertions.extend(stmt.assertions)
        return assertions

    def clone(self) -> TestCase:
        """Return a deep copy; mutations to the clone do not affect the original.

        Returns:
            A deep copy of this test case.
        """
        tc = TestCase()
        cloned = []
        for stmt in self._statements:
            s = Statement(
                node=stmt.node,
                bound_variable=stmt.bound_variable,
                bound_type=stmt.bound_type,
                assertions=list(stmt.assertions),
                accessible=stmt.accessible,
                ml_info=stmt.ml_info,
            )
            s._used_vars = stmt._used_vars  # noqa: SLF001 # propagate cached set; nodes are immutable
            cloned.append(s)
        tc._statements = cloned
        tc._var_counter = self._var_counter
        tc._rebuild_registry()
        tc._code_cache = self._code_cache
        return tc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TestCase):
            return NotImplemented
        return self.to_code() == other.to_code()

    def __hash__(self) -> int:
        return hash(self.to_code())

    def remove_unused_variables(self) -> None:
        """Remove assignments to variables that are not used later in the test case.

        Uses a backward pass to track alive variables. For each assignment, if the
        bound variable is not alive at that point, the assignment is replaced with
        a simple expression statement.
        """
        self._code_cache = None
        alive_vars: set[str] = set()

        for i in range(len(self._statements) - 1, -1, -1):
            stmt = self._statements[i]
            bv = stmt.bound_variable

            if bv is not None:
                if bv in alive_vars:
                    # Variable is used later. It is NOT alive before this assignment.
                    alive_vars.remove(bv)
                    alive_vars.update(_get_used_variables(stmt))
                else:
                    # Variable is NOT used later. Transform Assign to Expr.
                    new_node = self._transform_assign_to_expr(stmt.node)
                    if new_node is not stmt.node:
                        self._statements[i] = Statement(
                            node=new_node,
                            bound_variable=None,
                            bound_type=None,
                        )
                    # Even if unused, the RHS might use other variables
                    alive_vars.update(_get_used_variables(stmt))
            else:
                # Not an assignment, just update alive vars
                alive_vars.update(_get_used_variables(stmt))

        self._rebuild_registry()

    def _transform_assign_to_expr(
        self, node: cst.SimpleStatementLine | cst.BaseCompoundStatement
    ) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        """Replace cst.Assign with cst.Expr if it's a simple assignment.

        Args:
            node: The node to transform.

        Returns:
            The transformed node, or the original node if no change applied.
        """
        if not isinstance(node, cst.SimpleStatementLine):
            return node

        new_body: list[cst.BaseSmallStatement] = []
        changed = False

        for small_stmt in node.body:
            if isinstance(small_stmt, cst.Assign) and len(small_stmt.targets) == 1:
                new_body.append(cst.Expr(value=small_stmt.value))
                changed = True
            else:
                new_body.append(small_stmt)

        if changed:
            return node.with_changes(body=new_body)
        return node

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register(self, stmt: Statement) -> None:
        if stmt.bound_variable is not None and stmt.bound_type is not None:
            self._type_registry.setdefault(stmt.bound_type, []).append(stmt.bound_variable)

    def _rebuild_registry(self) -> None:
        self._type_registry = {}
        for stmt in self._statements:
            self._register(stmt)
