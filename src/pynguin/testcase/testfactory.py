#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a factory for libcst-backed test-case generation.

This factory builds on the analysis model
(:class:`~pynguin.analyses.module.ModuleTestCluster` and
:class:`~pynguin.utils.generic.genericaccessibleobject.GenericAccessibleObject`).
It emits :mod:`libcst` nodes directly and refers to variables by *name*
(``var_N``).
"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING

import libcst as cst

import pynguin.configuration as config
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.constants import ConstantProvider, EmptyConstantProvider
from pynguin.analyses.typesystem import Instance, ProperType, TupleType
from pynguin.testcase import literalgen
from pynguin.testcase.testcase import MLStatementInfo, Statement
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.naming import get_module_alias

if TYPE_CHECKING:
    import types

    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.analyses.typesystem import InferredSignature
    from pynguin.utils.pynguinml.mlparameter import MLParameter


_LOGGER = logging.getLogger(__name__)

# Concrete builtin collection types that are emitted as named, possibly
# reference-carrying statements rather than inline scalar literals.
_COLLECTION_RAWS: frozenset[type] = frozenset({list, set, tuple, dict})

# Builtin type objects that a ``type``-annotated parameter may be bound to.
# Rendered as bare ``cst.Name`` nodes, valid in any execution namespace.
_BUILTIN_CLASS_POOL: tuple[type, ...] = (
    int,
    float,
    str,
    bool,
    bytes,
    complex,
    list,
    dict,
    set,
    tuple,
    object,
)


def _raw_type_or_none(raw: type | types.UnionType) -> type | None:
    """Narrow a ``raw_type`` value to a single concrete python class.

    A ``TypeInfo.raw_type`` can be a single ``type`` or a :class:`UnionType`
    of raw types. A union does not correspond to a single concrete class, so it
    is mapped to ``None``.

    Args:
        raw: The raw type to narrow.

    Returns:
        The concrete python class, or ``None`` if it is a union.
    """
    return raw if isinstance(raw, type) else None


def _proper_type_to_raw(typ: ProperType | None) -> type | None:
    """Map a ProperType to a concrete python type, when possible.

    Args:
        typ: The proper type to map.

    Returns:
        The underlying python class, or ``None`` if it cannot be determined.
    """
    if isinstance(typ, Instance):
        return _raw_type_or_none(typ.type.raw_type)
    return None


def _field_rhs(stmt: Statement) -> cst.Attribute | None:
    """Return the ``Attribute`` RHS of a field-access statement, if it is one.

    Args:
        stmt: The statement to inspect.

    Returns:
        The ``cst.Attribute`` node on the RHS, or ``None`` if *stmt* is not a
        simple ``var = <receiver>.<field>`` assignment.
    """
    if not isinstance(stmt.node, cst.SimpleStatementLine):
        return None
    body = stmt.node.body
    if not body or not isinstance(body[0], cst.Assign):
        return None
    value = body[0].value
    return value if isinstance(value, cst.Attribute) else None


def _method_call_name(accessible: gao.GenericMethod) -> str | None:
    """Return the identifier under which a method can be called, if any.

    Prefers the accessible's stored ``method_name`` (the attribute name the
    callable is reachable under) over ``callable.__name__``, which can be a
    non-identifier such as ``<lambda>`` for callables assigned to class
    attributes.

    Args:
        accessible: The method accessible.

    Returns:
        A valid Python identifier, or ``None`` if none is available.
    """
    name = accessible.method_name or getattr(accessible.callable, "__name__", None)
    return name if isinstance(name, str) and name.isidentifier() else None


def _ndarray_mutation_elements(value: object, *, is_tuple: bool) -> list | None:
    """Extract a mutation-ready element list from a parsed ML value.

    Args:
        value: The value parsed from the statement's current RHS expression.
        is_tuple: Whether the statement's payload is rendered as a tuple.

    Returns:
        A plain list of elements, or ``None`` if *value* has the wrong shape.
    """
    if is_tuple:
        return list(value) if isinstance(value, tuple) else None
    return value if isinstance(value, list) else None


def _function_call_name(accessible: gao.GenericFunction) -> str | None:
    """Return the identifier under which a function can be called, if any.

    Prefers the accessible's stored ``function_name`` over
    ``callable.__name__``, which can be a non-identifier such as ``<lambda>``
    for callables assigned to module attributes.

    Args:
        accessible: The function accessible.

    Returns:
        A valid Python identifier, or ``None`` if none is available.
    """
    name = accessible.function_name or getattr(accessible.callable, "__name__", None)
    return name if isinstance(name, str) and name.isidentifier() else None


class TestFactory:
    """A factory for libcst-backed test-case generation.

    This factory does not own test cases; it provides the means to construct and
    modify them by inserting calls to the accessible objects of the SUT.
    """

    def __init__(
        self,
        test_cluster: ModuleTestCluster,
        constant_provider: ConstantProvider | None = None,
    ) -> None:
        """Initializes a new factory.

        Args:
            test_cluster: The underlying test cluster.
            constant_provider: An optional provider for seeded constant values.
        """
        self._test_cluster = test_cluster
        if constant_provider is None:
            constant_provider = EmptyConstantProvider()
        self._constant_provider: ConstantProvider = constant_provider

    # ------------------------------------------------------------------
    # Public API used by the GA
    # ------------------------------------------------------------------

    def insert_random_statement(self, test_case: tc.TestCase, position: int) -> int:
        """Insert a randomly chosen accessible call at (roughly) *position*.

        Args:
            test_case: The test case to extend.
            position: The desired insertion position.

        Returns:
            The position at which a statement was inserted, or ``-1`` on failure.
        """
        accessible = self._test_cluster.get_random_accessible()
        if accessible is None:
            return -1
        return self._emit_accessible(test_case, accessible, position, 0)

    def append_generic_accessible(
        self, test_case: tc.TestCase, accessible: gao.GenericAccessibleObject
    ) -> int:
        """Emit a single call statement for *accessible* at the end of *test_case*.

        Args:
            test_case: The test case to extend.
            accessible: The accessible object to call.

        Returns:
            The position at which the statement was inserted, or ``-1`` on failure.
        """
        return self._emit_accessible(test_case, accessible, test_case.size(), 0)

    def append_statement(
        self,
        test_case: tc.TestCase,
        statement: Statement,
        *,
        position: int = -1,
        allow_none: bool = True,
    ) -> None:
        """Append an already-built statement to *test_case*.

        Args:
            test_case: The test case to extend.
            statement: The statement to append.
            position: The position to insert at; ``-1`` appends at the end.
            allow_none: Unused; kept for API compatibility.
        """
        if position < 0:
            test_case.add_statement(statement)
        else:
            test_case.insert_statement(position, statement)

    def has_call_on_sut(self, test_case: tc.TestCase) -> bool:
        """Return whether *test_case* contains a call to an accessible under test.

        Args:
            test_case: The test case to inspect.

        Returns:
            True if any statement calls an accessible object under test.
        """
        under_test = self._test_cluster.accessible_objects_under_test
        return any(
            statement.accessible is not None and statement.accessible in under_test
            for statement in test_case.statements()
        )

    @staticmethod
    def delete_statement(test_case: tc.TestCase, position: int) -> bool:
        """Delete the statement at *position*.

        Args:
            test_case: The test case to modify.
            position: The index to delete.

        Returns:
            True if a statement was removed.
        """
        if 0 <= position < test_case.size():
            test_case.remove_statement(position)
            return True
        return False

    @staticmethod
    def delete_statement_gracefully(test_case: tc.TestCase, position: int) -> bool:
        """Delete the statement at *position* and any statement depending on it.

        Dependencies are computed by variable name: a later statement depends on
        the deleted statement if it reads the variable that statement binds.

        Args:
            test_case: The test case to modify.
            position: The index to delete.

        Returns:
            True if anything was removed.
        """
        if not (0 <= position < test_case.size()):
            return False

        # Name-based cascade: collect the set of indices to remove by following
        # the variable produced by the deleted statement to its forward readers.
        statements = test_case.statements()
        to_remove: set[int] = {position}
        # variables that become invalid once their producing statement is removed
        dead_vars: set[str] = set()
        bv = statements[position].bound_variable
        if bv is not None:
            dead_vars.add(bv)

        changed = True
        while changed:
            changed = False
            for idx in range(position + 1, len(statements)):
                if idx in to_remove:
                    continue
                if statements[idx].used_variables() & dead_vars:
                    to_remove.add(idx)
                    nbv = statements[idx].bound_variable
                    if nbv is not None and nbv not in dead_vars:
                        dead_vars.add(nbv)
                        changed = True

        test_case.remove_statements_batch(to_remove)
        return True

    def change_random_call(
        self,
        test_case: tc.TestCase,
        position: int,
    ) -> bool:
        """Replace the call at *position* with another call of the same return type.

        Dependency statements for the replacement are inserted before *position*
        so that the original statement's bound variable is preserved, avoiding
        NameError in any later statement that reads that variable.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to change.

        Returns:
            True if the call was changed.
        """
        if not (0 <= position < test_case.size()):
            return False
        statement = test_case.get_statement(position)
        if statement.accessible is None or not isinstance(
            statement.accessible, (gao.GenericCallableAccessibleObject, gao.GenericField)
        ):
            return False

        generated = statement.accessible.generated_type()
        alternatives = self._test_cluster.get_generators_for(generated)
        candidates = [a for a in alternatives if a != statement.accessible]
        if not candidates:
            return False

        replacement = randomness.choice(candidates)
        pre_size = test_case.size()

        built = self._build_replacement_node(test_case, replacement, position)
        if built is None:
            return False
        node, bound_type, _cursor = built

        return self._replace_with_node(
            test_case, position, pre_size, node, bound_type, replacement, keep_assertions=False
        )

    def change_statement_type(self, test_case: tc.TestCase, position: int) -> bool:
        """Replace the statement at *position* with one of a different type.

        Keeps the statement's bound variable name so later readers stay valid
        (they reference the name, which survives); the value they read may now
        be of a different type, which is deliberate search pressure.  Rolls the
        three-way choice of the reference implementation, reusing the local
        search different-type weights so behaviour matches when local search is
        active:

        * ``p <= ls_different_type_primitive_probability`` -> random primitive
          literal;
        * ``p <= ...primitive + ...collection`` -> random collection literal;
        * otherwise -> a random generator accessible.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to change.

        Returns:
            True if the statement type was changed.
        """
        if not (0 <= position < test_case.size()):
            return False
        stmt = test_case.get_statement(position)
        if stmt.bound_variable is None:
            return False

        probability = randomness.next_float()
        primitive_p = config.configuration.local_search.ls_different_type_primitive_probability
        collection_p = config.configuration.local_search.ls_different_type_collection_probability
        if probability <= primitive_p:
            return self._change_to_literal(
                test_case, position, stmt, (bool, int, float, str, bytes)
            )
        if probability <= primitive_p + collection_p:
            return self._change_to_literal(test_case, position, stmt, (list, set, tuple, dict))
        return self._change_to_accessible(test_case, position, stmt)

    def _change_to_literal(
        self,
        test_case: tc.TestCase,
        position: int,
        stmt: Statement,
        raw_types: tuple[type, ...],
    ) -> bool:
        """Replace *stmt* in place with a literal of a type drawn from *raw_types*.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to change.
            stmt: The statement being replaced.
            raw_types: The candidate python types to draw the new type from.

        Returns:
            True if the statement was changed.
        """
        choices = [t for t in raw_types if t is not stmt.bound_type]
        if not choices:
            return False
        new_raw = randomness.choice(choices)
        expr = literalgen.generate_literal(new_raw, self._constant_provider)
        assign_var = stmt.bound_variable
        assert assign_var is not None
        new_node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(assign_var))],
                    value=expr,
                )
            ]
        )
        test_case.replace_statement(
            position,
            Statement(
                node=new_node,
                bound_variable=assign_var,
                bound_type=new_raw,
                accessible=None,
            ),
        )
        return True

    def _change_to_accessible(self, test_case: tc.TestCase, position: int, stmt: Statement) -> bool:
        """Replace *stmt* with a call to a random generator accessible.

        Dependency statements are inserted before *position*; the resulting
        statement is bound to *stmt*'s original variable name.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to change.
            stmt: The statement being replaced.

        Returns:
            True if the statement was changed.
        """
        accessible = self._test_cluster.get_random_accessible()
        if accessible is None or accessible == stmt.accessible:
            return False
        pre_size = test_case.size()
        built = self._build_replacement_node(test_case, accessible, position)
        if built is None:
            return False
        node, bound_type, _cursor = built
        return self._replace_with_node(
            test_case, position, pre_size, node, bound_type, accessible, keep_assertions=False
        )

    def _replace_with_node(  # noqa: PLR0917
        self,
        test_case: tc.TestCase,
        position: int,
        pre_size: int,
        node: cst.BaseExpression,
        bound_type: type | None,
        accessible: gao.GenericAccessibleObject | None,
        *,
        keep_assertions: bool,
    ) -> bool:
        """Bind *node* to the (shifted) statement at *position*'s variable.

        Dependency statements inserted before *position* since *pre_size* shift
        the original statement to ``position + num_deps``; its variable name is
        reused (or a fresh one allocated) for the replacement assignment.

        Args:
            test_case: The test case being modified.
            position: The original index of the replaced statement.
            pre_size: The test case size before dependency statements were added.
            node: The RHS expression of the replacement assignment.
            bound_type: The bound type of the replacement.
            accessible: The accessible attached to the replacement, if any.
            keep_assertions: Whether to carry over the old statement's assertions.

        Returns:
            True.
        """
        num_deps = test_case.size() - pre_size
        old_index = position + num_deps
        old_stmt = test_case.get_statement(old_index)
        assign_var = (
            old_stmt.bound_variable
            if old_stmt.bound_variable is not None
            else test_case.next_var_name()
        )
        new_assign = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(assign_var))],
                    value=node,
                )
            ]
        )
        test_case.replace_statement(
            old_index,
            Statement(
                node=new_assign,
                bound_variable=assign_var,
                bound_type=bound_type,
                accessible=accessible,
                assertions=list(old_stmt.assertions) if keep_assertions else [],
            ),
        )
        return True

    def change_random_field_call(self, test_case: tc.TestCase, position: int) -> bool:
        """Replace the field read at *position* with another same-typed field.

        The receiver variable is kept; only the accessed attribute is swapped
        for another field of the same generated type.  Assertions and the bound
        variable are preserved.

        Args:
            test_case: The test case to modify.
            position: The index of the field statement to change.

        Returns:
            True if the field was swapped.
        """
        if not (0 <= position < test_case.size()):
            return False
        statement = test_case.get_statement(position)
        accessible = statement.accessible
        if not isinstance(accessible, gao.GenericField):
            return False
        rhs = _field_rhs(statement)
        if rhs is None or statement.bound_variable is None:
            return False
        candidates = [
            a
            for a in self._test_cluster.get_generators_for(accessible.generated_type())
            if isinstance(a, gao.GenericField) and a != accessible
        ]
        if not candidates:
            return False
        replacement = randomness.choice(candidates)
        new_rhs = rhs.with_changes(attr=cst.Name(replacement.field))
        new_node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(statement.bound_variable))],
                    value=new_rhs,
                )
            ]
        )
        test_case.replace_statement(
            position,
            Statement(
                node=new_node,
                bound_variable=statement.bound_variable,
                bound_type=statement.bound_type,
                assertions=list(statement.assertions),
                accessible=replacement,
            ),
        )
        return True

    def _build_replacement_node(
        self,
        test_case: tc.TestCase,
        replacement: gao.GenericAccessibleObject,
        cursor: int,
    ) -> tuple[cst.BaseExpression, type | None, int] | None:
        """Build the call expression and any dependencies for *replacement*.

        Inserts dependency statements into *test_case* starting at *cursor*,
        advancing the cursor with each insertion.  Returns the call expression,
        its bound type, and the updated cursor, or ``None`` if the replacement
        cannot be built (e.g. no receiver could be found for a method).

        Args:
            test_case: The test case to extend with dependency statements.
            replacement: The accessible to build a call expression for.
            cursor: Current insertion cursor.

        Returns:
            A tuple of (call node, bound type, updated cursor), or ``None``.
        """
        if isinstance(replacement, gao.GenericConstructor):
            args, cursor = self._satisfy_params(
                test_case, replacement.inferred_signature, cursor, 0, accessible=replacement
            )
            owner = replacement.owner
            class_name = owner.name if owner is not None else "object"
            func: cst.BaseExpression = cst.Attribute(
                value=cst.Name(self._module_alias()), attr=cst.Name(class_name)
            )
            bound_type = _raw_type_or_none(owner.raw_type) if owner is not None else None
            return cst.Call(func=func, args=args), bound_type, cursor
        if isinstance(replacement, gao.GenericMethod):
            method_name = _method_call_name(replacement)
            if method_name is None:
                return None
            owner_raw = _raw_type_or_none(replacement.owner.raw_type)
            receiver = self._find_variable_of_type(test_case, owner_raw, cursor)
            if receiver is None:
                owner_type = self._test_cluster.type_system.make_instance(replacement.owner)
                receiver, cursor = self._create_var_of_type(
                    test_case, owner_type, owner_raw, cursor, 0
                )
            if receiver is None:
                return None
            args, cursor = self._satisfy_params(
                test_case, replacement.inferred_signature, cursor, 0, accessible=replacement
            )
            func = cst.Attribute(value=cst.Name(receiver), attr=cst.Name(method_name))
            bound_type_m = _proper_type_to_raw(replacement.generated_type())
            return cst.Call(func=func, args=args), bound_type_m, cursor
        if isinstance(replacement, gao.GenericFunction):
            function_name = _function_call_name(replacement)
            if function_name is None:
                return None
            args, cursor = self._satisfy_params(
                test_case, replacement.inferred_signature, cursor, 0, accessible=replacement
            )
            func = cst.Attribute(
                value=cst.Name(self._module_alias()),
                attr=cst.Name(function_name),
            )
            bound_type_f = _proper_type_to_raw(replacement.generated_type())
            return cst.Call(func=func, args=args), bound_type_f, cursor
        if isinstance(replacement, gao.GenericEnum):
            node, bound_type = self._build_enum(replacement)
            return node, bound_type, cursor
        if isinstance(replacement, gao.GenericField):
            return self._build_field(test_case, replacement, cursor, 0)
        return None

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    def _emit_accessible(
        self,
        test_case: tc.TestCase,
        accessible: gao.GenericAccessibleObject,
        position: int,
        depth: int,
    ) -> int:
        """Emit a statement calling *accessible*, inserting at *position*.

        All dependency statements (receiver, arguments) are inserted at the
        cursor which starts at *position* and advances with each insertion.
        The call statement itself is inserted at the final cursor position.

        Args:
            test_case: The test case to extend.
            accessible: The accessible object to call.
            position: The desired insertion position.
            depth: Current recursion depth for object creation.

        Returns:
            The position at which the call statement was inserted, or ``-1`` on
            failure.
        """
        cursor = min(max(position, 0), test_case.size())

        node: cst.BaseExpression
        bound_type: type | None

        if isinstance(accessible, gao.GenericConstructor):
            built = self._build_constructor(test_case, accessible, cursor, depth)
            node, bound_type, cursor = built
        elif isinstance(accessible, gao.GenericMethod):
            built_method = self._build_method(test_case, accessible, cursor, depth)
            if built_method is None:
                return -1
            node, bound_type, cursor = built_method
        elif isinstance(accessible, gao.GenericFunction):
            built_fn = self._build_function(test_case, accessible, cursor, depth)
            if built_fn is None:
                return -1
            node, bound_type, cursor = built_fn
        elif isinstance(accessible, gao.GenericEnum):
            node, bound_type = self._build_enum(accessible)
        elif isinstance(accessible, gao.GenericField):
            built_field = self._build_field(test_case, accessible, cursor, depth)
            if built_field is None:
                return -1
            node, bound_type, cursor = built_field
        else:
            return -1

        var_name = test_case.next_var_name()
        assign = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(var_name))],
                    value=node,
                )
            ]
        )
        statement = Statement(
            node=assign,
            bound_variable=var_name,
            bound_type=bound_type,
            accessible=accessible,
        )
        insert_pos = min(cursor, test_case.size())
        test_case.insert_statement(insert_pos, statement)
        return insert_pos

    def _build_constructor(
        self,
        test_case: tc.TestCase,
        accessible: gao.GenericConstructor,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, type | None, int]:
        """Build the CST node for a constructor call.

        Args:
            test_case: The test case to extend with dependency statements.
            accessible: The constructor to call.
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (call node, bound type, updated cursor).
        """
        args, cursor = self._satisfy_params(
            test_case, accessible.inferred_signature, cursor, depth, accessible=accessible
        )
        owner = accessible.owner
        class_name = owner.name if owner is not None else "object"
        func = cst.Attribute(
            value=cst.Name(self._module_alias()),
            attr=cst.Name(class_name),
        )
        bound_type = _raw_type_or_none(owner.raw_type) if owner is not None else None
        return cst.Call(func=func, args=args), bound_type, cursor

    def _build_method(
        self,
        test_case: tc.TestCase,
        accessible: gao.GenericMethod,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, type | None, int] | None:
        """Build the CST node for a method call, acquiring a receiver if needed.

        Args:
            test_case: The test case to extend with dependency statements.
            accessible: The method to call.
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (call node, bound type, updated cursor), or ``None`` if
            no suitable receiver could be found or created.
        """
        method_name = _method_call_name(accessible)
        if method_name is None:
            return None
        owner_raw = _raw_type_or_none(accessible.owner.raw_type)
        receiver = self._find_variable_of_type(test_case, owner_raw, cursor)
        if receiver is None:
            owner_type = self._test_cluster.type_system.make_instance(accessible.owner)
            receiver, cursor = self._create_var_of_type(
                test_case, owner_type, owner_raw, cursor, depth
            )
        if receiver is None and randomness.next_bool():
            # Deliberately wrong-typed receiver: reaches __getattr__ delegation
            # and duck-typed code, mirroring the permissive receiver selection
            # of the reference implementation.
            receiver = self._find_any_variable(test_case, cursor)
        if receiver is None:
            return None
        args, cursor = self._satisfy_params(
            test_case, accessible.inferred_signature, cursor, depth, accessible=accessible
        )
        func = cst.Attribute(value=cst.Name(receiver), attr=cst.Name(method_name))
        bound_type = _proper_type_to_raw(accessible.generated_type())
        return cst.Call(func=func, args=args), bound_type, cursor

    def _build_function(
        self,
        test_case: tc.TestCase,
        accessible: gao.GenericFunction,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, type | None, int] | None:
        """Build the CST node for a free-function call.

        Args:
            test_case: The test case to extend with dependency statements.
            accessible: The function to call.
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (call node, bound type, updated cursor), or ``None`` if
            the function has no valid identifier to call it by.
        """
        func_name = _function_call_name(accessible)
        if func_name is None:
            return None
        args, cursor = self._satisfy_params(
            test_case, accessible.inferred_signature, cursor, depth, accessible=accessible
        )
        func = cst.Attribute(value=cst.Name(self._module_alias()), attr=cst.Name(func_name))
        bound_type = _proper_type_to_raw(accessible.generated_type())
        return cst.Call(func=func, args=args), bound_type, cursor

    def _build_enum(self, accessible: gao.GenericEnum) -> tuple[cst.BaseExpression, type | None]:
        """Build the CST node for an enum member access.

        Args:
            accessible: The enum accessible.

        Returns:
            A tuple of (attribute node, bound type).
        """
        owner = accessible.owner
        enum_name = owner.name if owner is not None else "Enum"
        members = list(getattr(accessible, "names", []) or [])
        member = randomness.choice(members) if members else "value"
        node = cst.Attribute(
            value=cst.Attribute(
                value=cst.Name(self._module_alias()),
                attr=cst.Name(enum_name),
            ),
            attr=cst.Name(member),
        )
        bound_type = _raw_type_or_none(owner.raw_type) if owner is not None else None
        return node, bound_type

    def _build_field(
        self,
        test_case: tc.TestCase,
        accessible: gao.GenericField,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, type | None, int] | None:
        """Build the CST node for a field access, acquiring a receiver if needed.

        Emits ``<receiver>.<field>`` where the receiver is an in-scope variable of
        the field owner's type, creating one via a generator when none is
        available.  Mirrors :meth:`_build_method` including the permissive
        wrong-typed-receiver coin flip.

        Args:
            test_case: The test case to extend with dependency statements.
            accessible: The field to access.
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (attribute node, bound type, updated cursor), or ``None``
            if the field name is not an identifier or no receiver could be found
            or created.
        """
        if not accessible.field.isidentifier():
            return None
        owner_raw = _raw_type_or_none(accessible.owner.raw_type)
        receiver = self._find_variable_of_type(test_case, owner_raw, cursor)
        if receiver is None:
            owner_type = self._test_cluster.type_system.make_instance(accessible.owner)
            receiver, cursor = self._create_var_of_type(
                test_case, owner_type, owner_raw, cursor, depth
            )
        if receiver is None and randomness.next_bool():
            # Deliberately wrong-typed receiver: reaches duck-typed attribute
            # access, mirroring the permissive receiver selection of methods.
            receiver = self._find_any_variable(test_case, cursor)
        if receiver is None:
            return None
        node = cst.Attribute(value=cst.Name(receiver), attr=cst.Name(accessible.field))
        bound_type = _proper_type_to_raw(accessible.generated_type())
        return node, bound_type, cursor

    # ------------------------------------------------------------------
    # Parameter satisfaction
    # ------------------------------------------------------------------

    def _satisfy_params(
        self,
        test_case: tc.TestCase,
        signature: InferredSignature,
        position: int,
        depth: int,
        accessible: gao.GenericCallableAccessibleObject | None = None,
    ) -> tuple[list[cst.Arg], int]:
        """Build the argument list for a call, reusing or generating values.

        Parameters with kind ``VAR_POSITIONAL`` or ``VAR_KEYWORD`` are skipped.
        Optional parameters (those with a default value) are skipped with
        probability ``skip_optional_parameter_probability``.  Once a
        ``POSITIONAL_ONLY`` optional parameter is skipped, all subsequent
        ``POSITIONAL_ONLY`` parameters are also skipped to avoid gaps.

        ``POSITIONAL_ONLY`` parameters are emitted as positional
        :class:`cst.Arg` nodes (no keyword).  All other kinds use keyword
        arguments.

        Args:
            test_case: The test case providing reusable variables.
            signature: The inferred signature of the callable.
            position: The insertion cursor; advances with each inserted dep.
            depth: Current recursion depth for object creation.
            accessible: The callable accessible the parameters are satisfied
                for; ignored by the base implementation, used by ML-aware
                subclasses to look up constraint data.

        Returns:
            A tuple of (arg list, updated cursor).
        """
        args: list[cst.Arg] = []
        cursor = position
        positional_only_skipped = False

        for name, param_type in signature.original_parameters.items():
            param = signature.signature.parameters.get(name)
            if param is not None and param.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue

            is_positional_only = (
                param is not None and param.kind == inspect.Parameter.POSITIONAL_ONLY
            )
            has_default = param is not None and param.default is not inspect.Parameter.empty

            # If a previous POSITIONAL_ONLY was skipped, all subsequent ones must
            # also be skipped (cannot pass positional args with a gap).
            if is_positional_only and positional_only_skipped:
                continue

            # Probabilistically skip optional parameters.
            if has_default and (
                randomness.next_float()
                < config.configuration.test_creation.skip_optional_parameter_probability
            ):
                if is_positional_only:
                    positional_only_skipped = True
                continue

            raw = _proper_type_to_raw(param_type)
            value, cursor = self._resolve_arg_value(test_case, param_type, raw, cursor, depth)

            if is_positional_only:
                args.append(cst.Arg(value=value))
            else:
                args.append(cst.Arg(keyword=cst.Name(name), value=value))

        return args, cursor

    def _resolve_arg_value(
        self,
        test_case: tc.TestCase,
        param_type: ProperType,
        raw: type | None,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, int]:
        """Resolve the CST expression to use as a call argument for *raw*.

        Tries to reuse or create a named variable; falls back to an inline
        literal when no suitable variable is available.  Primitive types are
        emitted as named ``var_N = <literal>`` statements so that
        :meth:`mutate_value` can later perturb them.

        Args:
            test_case: The test case to scan and extend.
            param_type: The ProperType of the parameter.
            raw: The concrete Python class for the type (may be ``None``).
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (CST expression, updated cursor).
        """
        var_name, cursor = self._create_or_reuse_var(test_case, param_type, raw, cursor, depth)
        if var_name is not None:
            return cst.Name(var_name), cursor
        if raw is type:
            emitted = self._emit_class_statement(test_case, cursor)
            if emitted is not None:
                return cst.Name(emitted[0]), emitted[1]
        if raw is not None and raw in _COLLECTION_RAWS:
            # Named, possibly reference-carrying collection statement.
            var_name, cursor = self._emit_collection_statement(
                test_case, raw, param_type, cursor, depth
            )
            return cst.Name(var_name), cursor
        if raw is not None and raw in literalgen.LITERAL_TYPES:
            # Emit as a named statement so it can be reused and mutated later.
            var_name, cursor = self._emit_primitive_statement(test_case, raw, cursor)
            return cst.Name(var_name), cursor
        mapped = literalgen.map_abstract_collection(raw) if raw is not None else None
        if mapped is not None:
            var_name, cursor = self._emit_collection_statement(
                test_case, mapped, param_type, cursor, depth
            )
            return cst.Name(var_name), cursor
        # Unresolvable (Any) parameter, or a type we can neither reuse nor
        # construct: coin-flip between reusing an arbitrary in-scope variable
        # and generating a literal.  Real objects reach code that accesses
        # attributes or calls methods on the argument, while literals keep
        # exploring string/number-guarded branches; both matter.
        any_var = self._find_any_variable(test_case, cursor)
        if any_var is not None and randomness.next_bool():
            return cst.Name(any_var), cursor
        return self._fallback_literal_value(raw), cursor

    def _emit_primitive_statement(
        self, test_case: tc.TestCase, raw: type, position: int
    ) -> tuple[str, int]:
        """Insert a named ``var_N = <literal>`` statement at *position*.

        Args:
            test_case: The test case to extend.
            raw: The primitive python type to generate a literal for.
            position: The cursor position at which to insert.

        Returns:
            A tuple of (newly allocated variable name, updated cursor).
        """
        var_name = test_case.next_var_name()
        expr = literalgen.generate_literal(raw, self._constant_provider)
        node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(var_name))],
                    value=expr,
                )
            ]
        )
        test_case.insert_statement(
            position, Statement(node=node, bound_variable=var_name, bound_type=raw)
        )
        return var_name, position + 1

    # ------------------------------------------------------------------
    # Class / type-object literals
    # ------------------------------------------------------------------

    def _class_literal_candidates(self) -> list[cst.BaseExpression]:
        """Return the candidate expressions a ``type`` parameter may reference.

        Includes every class declared in the module under test (rendered as
        ``module_alias.ClassName``) plus a fixed pool of builtin type objects
        (rendered as bare ``cst.Name`` nodes).  Nested classes (whose qualname
        contains a dot) are skipped because they are not reachable as a simple
        ``alias.Name`` attribute, and widening beyond the SUT module would
        require extra import machinery in the exporter.

        Returns:
            A non-empty list of CST expressions usable as a class literal RHS.
        """
        candidates: list[cst.BaseExpression] = [
            cst.Name(builtin.__name__) for builtin in _BUILTIN_CLASS_POOL
        ]
        module_name = config.configuration.module_name
        alias = self._module_alias()
        for type_info in self._test_cluster.type_system.get_all_types():
            if type_info.module != module_name:
                continue
            if "." in type_info.qualname:
                continue
            if not type_info.name.isidentifier():
                continue
            candidates.append(cst.Attribute(value=cst.Name(alias), attr=cst.Name(type_info.name)))
        return candidates

    def _emit_class_statement(
        self, test_case: tc.TestCase, position: int
    ) -> tuple[str, int] | None:
        """Insert a ``var_N = <class literal>`` statement at *position*.

        Args:
            test_case: The test case to extend.
            position: The cursor position at which to insert.

        Returns:
            A tuple of (newly allocated variable name, updated cursor), or
            ``None`` if no candidate class literal is available.
        """
        candidates = self._class_literal_candidates()
        if not candidates:
            return None
        expr = randomness.choice(candidates)
        var_name = test_case.next_var_name()
        node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(var_name))],
                    value=expr,
                )
            ]
        )
        test_case.insert_statement(
            position, Statement(node=node, bound_variable=var_name, bound_type=type)
        )
        return var_name, position + 1

    def _mutate_class_literal(self, test_case: tc.TestCase, position: int) -> bool:
        """Replace a class-literal statement's RHS with a different candidate.

        Args:
            test_case: The test case to modify.
            position: The index of the class-literal statement.

        Returns:
            True if the RHS was changed to a different class literal.
        """
        stmt = test_case.get_statement(position)
        if stmt.bound_variable is None or not isinstance(stmt.node, cst.SimpleStatementLine):
            return False
        body = stmt.node.body
        if not body or not isinstance(body[0], cst.Assign):
            return False
        old_code = cst.Module(body=[]).code_for_node(body[0].value)
        candidates = [
            expr
            for expr in self._class_literal_candidates()
            if cst.Module(body=[]).code_for_node(expr) != old_code
        ]
        if not candidates:
            return False
        new_expr = randomness.choice(candidates)
        new_node = stmt.node.with_changes(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(stmt.bound_variable))],
                    value=new_expr,
                )
            ]
        )
        test_case.replace_statement(
            position,
            Statement(
                node=new_node,
                bound_variable=stmt.bound_variable,
                bound_type=type,
                assertions=list(stmt.assertions),
                accessible=None,
            ),
        )
        return True

    # ------------------------------------------------------------------
    # Reference-carrying collection literals
    # ------------------------------------------------------------------

    def _reference_pool(self, test_case: tc.TestCase, position: int) -> list[cst.BaseExpression]:
        """Return ``cst.Name`` references to variables bound before *position*.

        Args:
            test_case: The test case to scan.
            position: Only variables bound strictly before this index are pooled.

        Returns:
            A list of ``cst.Name`` nodes referencing in-scope variables.
        """
        return [
            cst.Name(statement.bound_variable)
            for idx, statement in enumerate(test_case.statements())
            if idx < position and statement.bound_variable is not None
        ]

    def _collection_element(
        self,
        test_case: tc.TestCase,
        elem_type: ProperType | None,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, int]:
        """Build one collection element, creating a dependency variable if typed.

        For a resolvable element type, an existing variable is reused or a new
        producer statement is inserted before the collection (the element then
        becomes a ``cst.Name`` reference).  For primitive element types a named
        literal statement is emitted so the reference can later be mutated.  When
        the element type is unknown, a pooled reference or a random literal is
        used inline.

        Args:
            test_case: The test case to extend.
            elem_type: The element ProperType, or ``None`` if unknown.
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (element expression, updated cursor).
        """
        if elem_type is not None:
            raw_elem = _proper_type_to_raw(elem_type)
            var, cursor = self._create_or_reuse_var(test_case, elem_type, raw_elem, cursor, depth)
            if var is not None:
                return cst.Name(var), cursor
            if raw_elem is not None and raw_elem in _COLLECTION_RAWS:
                var, cursor = self._emit_collection_statement(
                    test_case, raw_elem, elem_type, cursor, depth
                )
                return cst.Name(var), cursor
            if raw_elem is not None and raw_elem in literalgen.LITERAL_TYPES:
                var, cursor = self._emit_primitive_statement(test_case, raw_elem, cursor)
                return cst.Name(var), cursor
        pool = self._reference_pool(test_case, cursor)
        return literalgen._element_value(self._constant_provider, pool), cursor  # noqa: SLF001

    def _collection_element_types(
        self, raw: type, param_type: ProperType | None
    ) -> tuple[list[ProperType | None], bool]:
        """Determine element types and size behaviour for a collection parameter.

        Args:
            raw: The concrete collection type (``list``/``set``/``tuple``/``dict``).
            param_type: The parameter's ProperType, carrying generic args.

        Returns:
            A tuple of (per-slot element types, fixed_size).  ``fixed_size`` is
            True only for a typed, known-size tuple, where the length is dictated
            by the number of type args.
        """
        size = randomness.next_int(0, config.configuration.test_creation.collection_size + 1)
        if raw is tuple:
            if (
                isinstance(param_type, TupleType)
                and not param_type.unknown_size
                and param_type.args
            ):
                return list(param_type.args), True
            return [None] * size, False
        if raw is dict:
            return [None] * size, False  # dict handled specially by the caller
        elem_type: ProperType | None = None
        if isinstance(param_type, Instance) and param_type.args:
            elem_type = param_type.args[0]
        return [elem_type] * size, False

    def _emit_collection_statement(
        self,
        test_case: tc.TestCase,
        raw: type,
        param_type: ProperType | None,
        position: int,
        depth: int,
    ) -> tuple[str, int]:
        """Insert a named collection statement, creating typed element deps first.

        The collection's elements may be ``cst.Name`` references to variables
        bound *before* the collection statement (typed element producers inserted
        here, or arbitrary in-scope variables via the reference pool), enabling
        reference-carrying collections such as ``list_2 = [int_0, int_1]``.

        Args:
            test_case: The test case to extend.
            raw: The concrete collection type to build.
            param_type: The parameter's ProperType (for element-type inference).
            position: The cursor position at which to insert dependencies.
            depth: Current recursion depth (guards against runaway recursion).

        Returns:
            A tuple of (newly allocated variable name, updated cursor).
        """
        cursor = position
        if depth >= config.configuration.test_creation.max_recursion:
            # Too deep for element construction: emit a pooled/literal collection.
            pool = self._reference_pool(test_case, cursor)
            expr = literalgen.generate_literal(raw, self._constant_provider, pool)
            return self._insert_collection(test_case, expr, raw, cursor)

        if raw is dict:
            expr, cursor = self._build_dict(test_case, param_type, cursor, depth)
            return self._insert_collection(test_case, expr, raw, cursor)

        elem_types, _fixed = self._collection_element_types(raw, param_type)
        element_nodes: list[cst.BaseExpression] = []
        for elem_type in elem_types:
            value, cursor = self._collection_element(test_case, elem_type, cursor, depth + 1)
            element_nodes.append(value)

        if raw is list:
            expr = cst.List(elements=[cst.Element(value=v) for v in element_nodes])
        elif raw is set:
            if not element_nodes:
                expr = cst.Call(func=cst.Name("set"))
            else:
                expr = cst.Set(elements=[cst.Element(value=v) for v in element_nodes])
        else:  # tuple
            tuple_elements = [cst.Element(value=v) for v in element_nodes]
            expr = cst.Tuple(elements=literalgen._tuple_elements(tuple_elements))  # noqa: SLF001
        return self._insert_collection(test_case, expr, raw, cursor)

    def _build_dict(
        self,
        test_case: tc.TestCase,
        param_type: ProperType | None,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, int]:
        """Build a dict expression with literal keys and reference-aware values.

        Keys stay literal (of the annotated key primitive type when known, else
        strings) so the mapping remains hashable; values may reference existing
        variables via :meth:`_collection_element`.

        Args:
            test_case: The test case to extend.
            param_type: The parameter's ProperType (for key/value type inference).
            cursor: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (dict expression, updated cursor).
        """
        size = randomness.next_int(0, config.configuration.test_creation.collection_size + 1)
        key_type: ProperType | None = None
        value_type: ProperType | None = None
        if isinstance(param_type, Instance) and len(param_type.args) >= 2:
            key_type, value_type = param_type.args[0], param_type.args[1]
        key_raw = _proper_type_to_raw(key_type) if key_type is not None else None
        entries: list[cst.DictElement] = []
        for _ in range(size):
            if (
                key_raw is not None
                and key_raw in literalgen.LITERAL_TYPES
                and (key_raw not in _COLLECTION_RAWS)
            ):
                key_expr = literalgen.generate_literal(key_raw, self._constant_provider)
            else:
                key_expr = literalgen.generate_literal(str, self._constant_provider)
            value_expr, cursor = self._collection_element(test_case, value_type, cursor, depth + 1)
            entries.append(cst.DictElement(key=key_expr, value=value_expr))
        return cst.Dict(elements=entries), cursor

    def _insert_collection(
        self, test_case: tc.TestCase, expr: cst.BaseExpression, raw: type, cursor: int
    ) -> tuple[str, int]:
        """Insert a ``var_N = <collection expr>`` statement at *cursor*.

        Args:
            test_case: The test case to extend.
            expr: The collection RHS expression.
            raw: The collection type to register as ``bound_type``.
            cursor: The insertion cursor.

        Returns:
            A tuple of (newly allocated variable name, updated cursor).
        """
        var_name = test_case.next_var_name()
        node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(var_name))],
                    value=expr,
                )
            ]
        )
        test_case.insert_statement(
            cursor, Statement(node=node, bound_variable=var_name, bound_type=raw)
        )
        return var_name, cursor + 1

    def mutate_value(self, test_case: tc.TestCase, position: int) -> bool:
        """Perturb the literal value of the primitive statement at *position*.

        The current RHS expression is extracted from the statement node and
        passed to :func:`~pynguin.testcase.literalgen.mutate_literal` so that
        the mutated value stays in the same neighbourhood as the original.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to mutate.

        Returns:
            True if the statement was mutated.
        """
        if not (0 <= position < test_case.size()):
            return False
        stmt = test_case.get_statement(position)
        if stmt.bound_type is type:
            return self._mutate_class_literal(test_case, position)
        if stmt.bound_type is None or stmt.bound_type not in literalgen.LITERAL_TYPES:
            return False
        assert stmt.bound_variable is not None

        # Extract the current RHS expression from the CST node.
        if not isinstance(stmt.node, cst.SimpleStatementLine):
            return False
        body = stmt.node.body
        if not body or not isinstance(body[0], cst.Assign):
            return False
        old_expr: cst.BaseExpression = body[0].value

        # Reference-carrying collections may mutate towards/away from variable
        # references bound strictly before this statement.
        pool: list[cst.BaseExpression] = (
            self._reference_pool(test_case, position) if stmt.bound_type in _COLLECTION_RAWS else []
        )
        new_expr = literalgen.mutate_literal(
            old_expr, stmt.bound_type, self._constant_provider, pool
        )
        new_node = stmt.node.with_changes(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(stmt.bound_variable))],
                    value=new_expr,
                )
            ]
        )
        test_case.replace_statement(
            position,
            Statement(
                node=new_node,
                bound_variable=stmt.bound_variable,
                bound_type=stmt.bound_type,
                assertions=list(stmt.assertions),
                accessible=None,
            ),
        )
        return True

    def _regen_args_in_place(  # noqa: C901
        self,
        test_case: tc.TestCase,
        signature: InferredSignature,
        position: int,
        accessible: gao.GenericCallableAccessibleObject | None = None,
    ) -> list[cst.Arg]:
        """Regenerate call arguments without adding new statements to *test_case*.

        Reuses already-available variables or falls back to inline literals.
        Used by :meth:`mutate_call` where inserting new dependency statements
        would break ordering.  Applies the same optional-skipping and
        positional-only rules as :meth:`_satisfy_params`.

        Args:
            test_case: The test case whose existing variables may be reused.
            signature: The inferred signature of the callable being mutated.
            position: Only consider statements before this index for reuse.
            accessible: The callable accessible the arguments belong to;
                ignored by the base implementation, available to ML-aware
                subclasses.

        Returns:
            A freshly generated list of CST arguments.
        """
        args: list[cst.Arg] = []
        positional_only_skipped = False

        for name, param_type in signature.original_parameters.items():
            param = signature.signature.parameters.get(name)
            if param is not None and param.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue

            is_positional_only = (
                param is not None and param.kind == inspect.Parameter.POSITIONAL_ONLY
            )
            has_default = param is not None and param.default is not inspect.Parameter.empty

            if is_positional_only and positional_only_skipped:
                continue

            if has_default and (
                randomness.next_float()
                < config.configuration.test_creation.skip_optional_parameter_probability
            ):
                if is_positional_only:
                    positional_only_skipped = True
                continue

            raw = _proper_type_to_raw(param_type)
            existing = self._find_variable_of_type(test_case, raw, position)
            if existing is None and (
                raw is None
                or (
                    raw not in literalgen.LITERAL_TYPES
                    and literalgen.map_abstract_collection(raw) is None
                )
            ):
                # Unresolvable (Any) parameter or unconstructible type: any
                # in-scope variable is a candidate, mirroring _resolve_arg_value.
                existing = self._find_any_variable(test_case, position)
            value: cst.BaseExpression
            if existing is not None and randomness.next_bool():
                value = cst.Name(existing)
            elif raw is type:
                value = randomness.choice(self._class_literal_candidates())
            elif raw is not None and raw in literalgen.LITERAL_TYPES:
                # Collections may reference in-scope variables inline (no new
                # dependency statements are inserted here).
                inline_pool: list[cst.BaseExpression] = (
                    self._reference_pool(test_case, position) if raw in _COLLECTION_RAWS else []
                )
                value = literalgen.generate_literal(raw, self._constant_provider, inline_pool)
            else:
                value = self._fallback_literal_value(raw, self._reference_pool(test_case, position))

            if is_positional_only:
                args.append(cst.Arg(value=value))
            else:
                args.append(cst.Arg(keyword=cst.Name(name), value=value))

        return args

    def _fallback_literal_value(
        self,
        raw: type | None,
        element_pool: list[cst.BaseExpression] | None = None,
    ) -> cst.BaseExpression:
        """Return a fallback CST literal for types not handled by create-or-reuse.

        Tries abstract-collection mapping first (e.g. ``Iterable`` → ``list``).
        For completely unresolvable types (``raw is None`` / ``Any``), returns a
        random primitive literal 90 % of the time and ``None`` 10 % of the time
        so that ``if x is None:`` branches remain reachable.

        Args:
            raw: The concrete Python class, or ``None`` for AnyType.
            element_pool: Optional in-scope reference expressions usable when the
                fallback generates a collection literal.

        Returns:
            A CST expression suitable for use as an argument literal.
        """
        pool = element_pool if element_pool is not None else []
        mapped = literalgen.map_abstract_collection(raw) if raw is not None else None
        if mapped is not None:
            return literalgen.generate_literal(mapped, self._constant_provider, pool)
        if raw is None:
            # AnyType / unresolvable: random primitive, occasionally None.
            if randomness.next_float() < 0.1:
                return cst.Name("None")
            fallback = randomness.choice(sorted(literalgen.LITERAL_TYPES, key=str))
            return literalgen.generate_literal(fallback, self._constant_provider, pool)
        return cst.Name("None")

    def mutate_call(self, test_case: tc.TestCase, position: int) -> bool:  # noqa: C901
        """Regenerate the argument values of the call statement at *position*.

        This mirrors the original ``statement.mutate()`` behaviour: it keeps the
        same callable but picks fresh argument values, reusing already-available
        variables where possible and falling back to literals elsewhere.  Unlike
        :meth:`_satisfy_params` it never inserts new dependency statements, so
        the call's position in the test case does not change.

        Args:
            test_case: The test case to modify.
            position: Index of the statement to mutate.

        Returns:
            True if the statement was mutated.
        """
        if not (0 <= position < test_case.size()):
            return False
        stmt = test_case.get_statement(position)
        if stmt.accessible is None or stmt.bound_variable is None:
            return False

        accessible = stmt.accessible
        if isinstance(accessible, gao.GenericConstructor):
            args = self._regen_args_in_place(
                test_case, accessible.inferred_signature, position, accessible=accessible
            )
            owner = accessible.owner
            class_name = owner.name if owner is not None else "object"
            new_call: cst.BaseExpression = cst.Call(
                func=cst.Attribute(value=cst.Name(self._module_alias()), attr=cst.Name(class_name)),
                args=args,
            )
        elif isinstance(accessible, gao.GenericMethod):
            method_name = _method_call_name(accessible)
            if method_name is None:
                return False
            owner_raw = _raw_type_or_none(accessible.owner.raw_type)
            receiver = self._find_variable_of_type(test_case, owner_raw, position)
            if receiver is None:
                return False
            args = self._regen_args_in_place(
                test_case, accessible.inferred_signature, position, accessible=accessible
            )
            new_call = cst.Call(
                func=cst.Attribute(value=cst.Name(receiver), attr=cst.Name(method_name)),
                args=args,
            )
        elif isinstance(accessible, gao.GenericFunction):
            function_name = _function_call_name(accessible)
            if function_name is None:
                return False
            args = self._regen_args_in_place(
                test_case, accessible.inferred_signature, position, accessible=accessible
            )
            new_call = cst.Call(
                func=cst.Attribute(
                    value=cst.Name(self._module_alias()),
                    attr=cst.Name(function_name),
                ),
                args=args,
            )
        elif isinstance(accessible, gao.GenericEnum):
            owner = accessible.owner
            enum_name = owner.name if owner is not None else "Enum"
            members = list(getattr(accessible, "names", []) or [])
            member = randomness.choice(members) if members else "value"
            new_call = cst.Attribute(
                value=cst.Attribute(value=cst.Name(self._module_alias()), attr=cst.Name(enum_name)),
                attr=cst.Name(member),
            )
        elif isinstance(accessible, gao.GenericField):
            owner_raw = _raw_type_or_none(accessible.owner.raw_type)
            receiver = self._find_variable_of_type(test_case, owner_raw, position)
            if receiver is None:
                return False
            new_call = cst.Attribute(value=cst.Name(receiver), attr=cst.Name(accessible.field))
        else:
            return False

        new_node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(stmt.bound_variable))],
                    value=new_call,
                )
            ]
        )
        test_case.replace_statement(
            position,
            Statement(
                node=new_node,
                bound_variable=stmt.bound_variable,
                bound_type=stmt.bound_type,
                assertions=list(stmt.assertions),
                accessible=accessible,
            ),
        )
        return True

    # ------------------------------------------------------------------
    # Variable / type helpers
    # ------------------------------------------------------------------

    def _create_or_reuse_var(
        self,
        test_case: tc.TestCase,
        param_type: ProperType,
        raw: type | None,
        position: int,
        depth: int,
    ) -> tuple[str | None, int]:
        """Return a variable name for *param_type*, reusing existing or creating one.

        For primitive types (bool, int, float, str, bytes), an existing variable
        is reused with probability ``primitive_reuse_probability``; otherwise
        ``None`` is returned so the caller falls through to literal generation.

        For all other concrete types, an existing variable is reused with
        probability ``object_reuse_probability``; if not reused (or none
        exists), a new variable is created via a generator accessible.

        Unresolvable types (``raw is None``) always return ``None``.

        Args:
            test_case: The test case to scan/extend.
            param_type: The ProperType needed for the parameter.
            raw: The concrete Python class for the type (may be ``None``).
            position: Current insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (variable name or ``None``, updated cursor).
        """
        if raw is None:
            return None, position

        is_primitive = issubclass(raw, (bool, int, float, complex, str, bytes))
        existing = self._find_variable_of_type(test_case, raw, position)

        if existing is not None:
            reuse_prob = (
                config.configuration.test_creation.primitive_reuse_probability
                if is_primitive
                else config.configuration.test_creation.object_reuse_probability
            )
            if randomness.next_float() < reuse_prob:
                return existing, position

        if is_primitive:
            # Caller handles literal generation.
            return None, position

        return self._create_var_of_type(test_case, param_type, raw, position, depth)

    def _create_var_of_type(
        self,
        test_case: tc.TestCase,
        param_type: ProperType,
        raw: type | None,
        position: int,
        depth: int,
    ) -> tuple[str | None, int]:
        """Try to create a new variable of *param_type* by calling a generator.

        Args:
            test_case: The test case to extend.
            param_type: The ProperType to generate.
            raw: The concrete Python class (used for post-creation lookup).
            position: Insertion cursor.
            depth: Current recursion depth.

        Returns:
            A tuple of (bound variable name or ``None``, updated cursor).
        """
        if depth >= config.configuration.test_creation.max_recursion:
            return None, position
        generators = list(self._test_cluster.get_generators_for(param_type))
        if not generators:
            return None, position
        generator = randomness.choice(generators)
        new_pos = self._emit_accessible(test_case, generator, position, depth + 1)
        if new_pos < 0:
            return None, position
        stmt = test_case.get_statement(new_pos)
        return stmt.bound_variable, new_pos + 1

    @staticmethod
    def _find_any_variable(test_case: tc.TestCase, position: int) -> str | None:
        """Return a random variable name bound before *position*, of any type.

        Args:
            test_case: The test case to scan.
            position: Only consider statements before this index.

        Returns:
            A variable name, or ``None`` if no bound variable is in scope.
        """
        candidates: list[str] = []
        for idx, statement in enumerate(test_case.statements()):
            if idx >= position:
                break
            if statement.bound_variable is not None:
                candidates.append(statement.bound_variable)
        if not candidates:
            return None
        return randomness.choice(candidates)

    @staticmethod
    def _find_variable_of_type(
        test_case: tc.TestCase, raw: type | None, position: int
    ) -> str | None:
        """Return a variable name bound to *raw* declared before *position*.

        Args:
            test_case: The test case to scan.
            raw: The python type to match.
            position: Only consider statements before this index.

        Returns:
            A matching variable name, or ``None``.
        """
        if raw is None:
            return None
        candidates: list[str] = []
        for idx, statement in enumerate(test_case.statements()):
            if idx >= position:
                break
            if statement.bound_variable is None or statement.bound_type is None:
                continue
            try:
                # Subclass instances are valid wherever the base type is
                # expected, so consider them for reuse as well.
                matches = statement.bound_type is raw or issubclass(statement.bound_type, raw)
            except TypeError:
                matches = False
            if matches:
                candidates.append(statement.bound_variable)
        if not candidates:
            return None
        return randomness.choice(candidates)

    def _module_alias(self) -> str:
        """Return the import alias for the module under test.

        Returns:
            The module alias string.
        """
        return get_module_alias(config.configuration.module_name)


class MLTestFactory(TestFactory):
    """A factory variant for ML-specific test-case generation.

    Consults the per-parameter constraint data (:class:`MLParameter`) attached
    to accessibles via :meth:`ModuleTestCluster.get_ml_data_for` and emits the
    classic ML statement chain::

        var_0 = [[7, -3], [0, 12]]                  # ndarray literal
        var_1 = 'int32'                             # dtype pick
        var_2 = np.array(object=var_0, dtype=var_1)  # ml_call
        var_3 = torch.tensor(x=var_2)                # ml_call (optional)

    ML-specific statements carry :class:`MLStatementInfo` metadata and are
    treated as an atomic unit by mutation and crossover.
    """

    def append_statement(
        self,
        test_case: tc.TestCase,
        statement: Statement,
        *,
        position: int = -1,
        allow_none: bool = True,
    ) -> None:
        """Append an already-built statement, refusing ML-specific statements.

        ML statement chains (ndarray + dtype + ``np.array`` + constructor) are
        atomic; appending single members during crossover would produce broken
        chains, so such statements are silently ignored (mirrors the behaviour
        of the class-based implementation).

        Args:
            test_case: The test case to extend.
            statement: The statement to append.
            position: The position to insert at; ``-1`` appends at the end.
            allow_none: Unused; kept for API compatibility.
        """
        if statement.ml_info is not None:
            return
        super().append_statement(test_case, statement, position=position, allow_none=allow_none)

    def change_random_call(self, test_case: tc.TestCase, position: int) -> bool:
        """Replace the call at *position*, never touching ML statements.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to change.

        Returns:
            True if the call was changed.
        """
        if not (0 <= position < test_case.size()):
            return False
        if test_case.get_statement(position).ml_info is not None:
            return False
        return super().change_random_call(test_case, position)

    def mutate_call(self, test_case: tc.TestCase, position: int) -> bool:
        """Regenerate the argument values of the call at *position*.

        ML statements are never mutated this way; their glue calls
        (``np.array``/constructor) must keep their exact arguments.

        Args:
            test_case: The test case to modify.
            position: Index of the statement to mutate.

        Returns:
            True if the statement was mutated.
        """
        if not (0 <= position < test_case.size()):
            return False
        if test_case.get_statement(position).ml_info is not None:
            return False
        return super().mutate_call(test_case, position)

    def change_statement_type(self, test_case: tc.TestCase, position: int) -> bool:
        """Replace the statement at *position*, never touching ML statements.

        ML statement chains are atomic; replacing a single member with an
        arbitrary-typed statement would break the chain.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to change.

        Returns:
            True if the statement type was changed.
        """
        if not (0 <= position < test_case.size()):
            return False
        if test_case.get_statement(position).ml_info is not None:
            return False
        return super().change_statement_type(test_case, position)

    def _satisfy_params(  # noqa: C901
        self,
        test_case: tc.TestCase,
        signature: InferredSignature,
        position: int,
        depth: int,
        accessible: gao.GenericCallableAccessibleObject | None = None,
    ) -> tuple[list[cst.Arg], int]:
        """Build the argument list, consulting ML constraints when available.

        Falls back to the base implementation when no constraint data exists
        for *accessible* or when the ``ignore_constraints_probability`` coin
        flip says so.  Otherwise, values are emitted in the constraint
        *generation order* (shape/dtype dependencies first) while the final
        argument list is assembled in signature order.

        Args:
            test_case: The test case providing reusable variables.
            signature: The inferred signature of the callable.
            position: The insertion cursor; advances with each inserted dep.
            depth: Current recursion depth for object creation.
            accessible: The callable accessible the parameters are satisfied for.

        Returns:
            A tuple of (arg list, updated cursor).
        """
        ml_data = None
        if accessible is not None and isinstance(accessible, gao.GenericCallableAccessibleObject):
            ml_data = self._test_cluster.get_ml_data_for(accessible)
        if (
            ml_data is None
            or not ml_data.parameters
            or randomness.next_float()
            < config.configuration.pynguinml.ignore_constraints_probability
        ):
            return super()._satisfy_params(test_case, signature, position, depth, accessible)

        import pynguin.utils.pynguinml.ml_testfactory_utils as mltu  # noqa: PLC0415

        mltu.reset_parameter_objects(ml_data.parameters)

        # First pass (signature order): decide skip/include and arg style once.
        included: dict[str, tuple[ProperType, bool]] = {}
        positional_only_skipped = False
        for name, param_type in signature.original_parameters.items():
            param = signature.signature.parameters.get(name)
            if param is not None and param.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue

            is_positional_only = (
                param is not None and param.kind == inspect.Parameter.POSITIONAL_ONLY
            )
            has_default = param is not None and param.default is not inspect.Parameter.empty

            if is_positional_only and positional_only_skipped:
                continue

            if has_default and (
                randomness.next_float()
                < config.configuration.test_creation.skip_optional_parameter_probability
            ):
                if is_positional_only:
                    positional_only_skipped = True
                continue

            included[name] = (param_type, is_positional_only)

        # Second pass (generation order): emit values so that parameters that
        # other parameters' shapes/dtypes depend on are generated first.
        ordered = mltu.change_generation_order(
            ml_data.generation_order,
            {name: typ for name, (typ, _) in included.items()},
        )
        values: dict[str, cst.BaseExpression] = {}
        cursor = position
        for name, param_type in ordered.items():
            parameter_obj = ml_data.parameters.get(name)
            raw = _proper_type_to_raw(param_type)
            if parameter_obj is None:
                value, cursor = self._resolve_arg_value(test_case, param_type, raw, cursor, depth)
            else:
                try:
                    value, cursor = self._ml_arg_for_parameter(
                        test_case, parameter_obj, cursor, depth
                    )
                except ConstructionFailedException:
                    _LOGGER.debug(
                        "Construction via constraints failed for parameter %r; "
                        "falling back to default generation.",
                        name,
                    )
                    value, cursor = self._resolve_arg_value(
                        test_case, param_type, raw, cursor, depth
                    )
            values[name] = value

        # Third pass (signature order): assemble the final argument list.
        args: list[cst.Arg] = []
        for name, (_, is_positional_only) in included.items():
            value = values[name]
            if is_positional_only:
                args.append(cst.Arg(value=value))
            else:
                args.append(cst.Arg(keyword=cst.Name(name), value=value))
        return args, cursor

    def _ml_arg_for_parameter(  # noqa: PLR0914
        self,
        test_case: tc.TestCase,
        parameter_obj: MLParameter,
        cursor: int,
        depth: int,
    ) -> tuple[cst.BaseExpression, int]:
        """Generate the argument value for a constrained parameter.

        Port of the class-based ``_attempt_generation_by_constraints``: picks
        enum values, dtypes, shapes, and payloads per the parameter's
        constraints and emits the ML statement chain into *test_case*.

        Args:
            test_case: The test case to extend.
            parameter_obj: The constraint data of the parameter.
            cursor: Current insertion cursor.
            depth: Current recursion depth (unused; ML values are leaves).

        Returns:
            A tuple of (argument expression, updated cursor).

        Raises:
            ConstructionFailedException: If no value satisfying the
                constraints could be generated.
        """
        del depth  # ML-generated values never recurse into object creation.
        import pynguin.utils.pynguinml.ml_parsing_utils as mlpu  # noqa: PLC0415
        import pynguin.utils.pynguinml.ml_testfactory_utils as mltu  # noqa: PLC0415
        from pynguin.utils.pynguinml import ndarray_cst  # noqa: PLC0415

        if parameter_obj.valid_enum_values:
            allowed = list(mlpu.convert_values(parameter_obj.valid_enum_values))
            value = randomness.choice(allowed)
            parameter_obj.current_data = value
            var, cursor = self._emit_ml_assign(
                test_case,
                ndarray_cst.ml_value_to_cst(value),
                cursor,
                MLStatementInfo(kind="allowed_values", allowed_values=allowed),
                bound_type=type(value),
            )
            return cst.Name(var), cursor

        dtype = mltu.select_dtype(parameter_obj)

        if "None" in dtype:
            parameter_obj.current_data = None
            var, cursor = self._emit_ml_assign(
                test_case,
                cst.Name("None"),
                cursor,
                MLStatementInfo(kind="ml_scalar", dtype="None"),
                bound_type=None,
            )
            return cst.Name(var), cursor

        ndim = mltu.select_ndim(parameter_obj, dtype)
        shape = mltu.generate_shape(parameter_obj, ndim)
        # A var dependency can change the ndim, so derive it from the shape.
        ndim = len(shape)

        if ndim == 0:
            return self._emit_ml_scalar(test_case, parameter_obj, dtype, cursor)

        nested, low, high = mltu.generate_ndarray(parameter_obj, shape, dtype)
        as_tuple = parameter_obj.structure == "tuple" and ndim == 1
        payload: list | tuple = tuple(nested) if as_tuple else nested
        # The structure constraint means the SUT consumes the plain list/tuple
        # directly; only then is the variable eligible for generic reuse.
        is_final_value = parameter_obj.structure is not None and ndim == 1
        bound_type: type | None = None
        if is_final_value:
            bound_type = tuple if as_tuple else list
        ndarray_var, cursor = self._emit_ml_assign(
            test_case,
            ndarray_cst.ml_value_to_cst(payload),
            cursor,
            MLStatementInfo(
                kind="ndarray",
                dtype=dtype,
                low=float(low),
                high=float(high),
                is_tuple=as_tuple,
            ),
            bound_type=bound_type,
        )
        if is_final_value:
            return cst.Name(ndarray_var), cursor

        dtype_var, cursor = self._emit_ml_assign(
            test_case,
            ndarray_cst.ml_value_to_cst(dtype),
            cursor,
            MLStatementInfo(kind="allowed_values", allowed_values=[dtype]),
            bound_type=None,
        )
        var, cursor = self._emit_tensor_calls(test_case, ndarray_var, dtype_var, cursor)
        return cst.Name(var), cursor

    def _emit_ml_scalar(
        self,
        test_case: tc.TestCase,
        parameter_obj: MLParameter,
        dtype: str,
        cursor: int,
    ) -> tuple[cst.BaseExpression, int]:
        """Emit a ``var_N = <scalar literal>`` statement for a 0-dim parameter.

        Args:
            test_case: The test case to extend.
            parameter_obj: The constraint data of the parameter.
            dtype: The selected numpy dtype name.
            cursor: Current insertion cursor.

        Returns:
            A tuple of (argument expression, updated cursor).

        Raises:
            ConstructionFailedException: If the dtype has no scalar generation
                strategy (e.g. ``str``).
        """
        import pynguin.utils.pynguinml.ml_testfactory_utils as mltu  # noqa: PLC0415
        from pynguin.utils.pynguinml import ndarray_cst  # noqa: PLC0415

        value: bool | int | float | complex
        low: float
        high: float
        if dtype == "bool":
            low = high = 0.0
            value = randomness.next_bool()
        elif dtype.startswith(("int", "uint")):
            low, high = mltu.get_range(parameter_obj, dtype)
            value = randomness.next_int(int(low), int(high) + 1)
        elif dtype.startswith("float"):
            low, high = mltu.get_range(parameter_obj, dtype)
            precision = randomness.next_int(0, 7)
            value = round(low + (high - low) * randomness.next_float(), precision)
        elif dtype.startswith("complex"):
            low, high = mltu.get_range(parameter_obj, "float64")
            real = round(low + (high - low) * randomness.next_float(), randomness.next_int(0, 7))
            imag = round(low + (high - low) * randomness.next_float(), randomness.next_int(0, 7))
            value = complex(real, imag)
        else:
            # str and other exotic dtypes: defer to the base generation path.
            raise ConstructionFailedException(
                f"No ML scalar generation strategy for dtype {dtype}."
            )

        parameter_obj.current_data = value
        var, cursor = self._emit_ml_assign(
            test_case,
            ndarray_cst.ml_value_to_cst(value),
            cursor,
            MLStatementInfo(kind="ml_scalar", dtype=dtype, low=float(low), high=float(high)),
            bound_type=type(value),
        )
        return cst.Name(var), cursor

    def _emit_tensor_calls(
        self,
        test_case: tc.TestCase,
        ndarray_var: str,
        dtype_var: str,
        cursor: int,
    ) -> tuple[str, int]:
        """Emit the ``np.array(...)`` call and the optional constructor call.

        Args:
            test_case: The test case to extend.
            ndarray_var: The variable name of the ndarray literal.
            dtype_var: The variable name of the dtype string.
            cursor: Current insertion cursor.

        Returns:
            A tuple of (variable name of the final tensor value, updated cursor).
        """
        import pynguin.utils.pynguinml.ml_testing_resources as tr  # noqa: PLC0415

        np_call = cst.Call(
            func=cst.Attribute(value=cst.Name("np"), attr=cst.Name("array")),
            args=[
                cst.Arg(keyword=cst.Name("object"), value=cst.Name(ndarray_var)),
                cst.Arg(keyword=cst.Name("dtype"), value=cst.Name(dtype_var)),
            ],
        )
        nparray_var, cursor = self._emit_ml_assign(
            test_case,
            np_call,
            cursor,
            MLStatementInfo(kind="ml_call"),
            bound_type=None,
            accessible=tr.get_nparray_function(self._test_cluster),
        )

        constructor = tr.get_constructor_function(self._test_cluster)
        if constructor is None:
            return nparray_var, cursor

        func = _attribute_chain(config.configuration.pynguinml.constructor_function)
        parameter_name = config.configuration.pynguinml.constructor_function_parameter
        ctor_call = cst.Call(
            func=func,
            args=[cst.Arg(keyword=cst.Name(parameter_name), value=cst.Name(nparray_var))],
        )
        tensor_var, cursor = self._emit_ml_assign(
            test_case,
            ctor_call,
            cursor,
            MLStatementInfo(kind="ml_call"),
            bound_type=None,
            accessible=constructor,
        )
        return tensor_var, cursor

    def _emit_ml_assign(  # noqa: PLR0917
        self,
        test_case: tc.TestCase,
        expr: cst.BaseExpression,
        cursor: int,
        ml_info: MLStatementInfo,
        bound_type: type | None = None,
        accessible: gao.GenericAccessibleObject | None = None,
    ) -> tuple[str, int]:
        """Insert a ``var_N = <expr>`` statement carrying ML metadata.

        Args:
            test_case: The test case to extend.
            expr: The RHS expression of the assignment.
            cursor: Current insertion cursor.
            ml_info: The ML metadata to attach to the statement.
            bound_type: The type the bound variable is registered under.
            accessible: The accessible attached to the statement (for
                ``np.array``/constructor calls).

        Returns:
            A tuple of (newly allocated variable name, updated cursor).
        """
        var_name = test_case.next_var_name()
        node = cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(var_name))],
                    value=expr,
                )
            ]
        )
        test_case.insert_statement(
            cursor,
            Statement(
                node=node,
                bound_variable=var_name,
                bound_type=bound_type,
                accessible=accessible,
                ml_info=ml_info,
            ),
        )
        return var_name, cursor + 1

    def mutate_value(self, test_case: tc.TestCase, position: int) -> bool:
        """Perturb the value of the statement at *position*, ML-aware.

        ML metadata drives the mutation: ``ml_call`` statements are never
        mutated, ``allowed_values`` statements re-pick from their pool,
        ``ml_scalar`` statements re-draw from their ``[low, high]`` range, and
        ``ndarray`` statements are mutated shape-aware.  Statements without ML
        metadata are handled by the base implementation.

        Args:
            test_case: The test case to modify.
            position: The index of the statement to mutate.

        Returns:
            True if the statement was mutated.
        """
        if not (0 <= position < test_case.size()):
            return False
        stmt = test_case.get_statement(position)
        info = stmt.ml_info
        if info is None:
            return super().mutate_value(test_case, position)
        if info.kind == "ml_call" or stmt.bound_variable is None:
            return False

        # Extract the current RHS expression from the CST node.
        if not isinstance(stmt.node, cst.SimpleStatementLine):
            return False
        body = stmt.node.body
        if not body or not isinstance(body[0], cst.Assign):
            return False
        old_expr: cst.BaseExpression = body[0].value

        new_expr = self._mutated_ml_expr(info, old_expr)
        if new_expr is None:
            return False

        new_node = stmt.node.with_changes(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name(stmt.bound_variable))],
                    value=new_expr,
                )
            ]
        )
        test_case.replace_statement(
            position,
            Statement(
                node=new_node,
                bound_variable=stmt.bound_variable,
                bound_type=stmt.bound_type,
                assertions=list(stmt.assertions),
                accessible=stmt.accessible,
                ml_info=info,
            ),
        )
        return True

    @staticmethod
    def _mutated_ml_expr(
        info: MLStatementInfo, old_expr: cst.BaseExpression
    ) -> cst.BaseExpression | None:
        """Compute a mutated RHS expression for an ML statement.

        Args:
            info: The ML metadata of the statement.
            old_expr: The current RHS expression.

        Returns:
            The mutated expression, or ``None`` if no mutation is possible.
        """
        from pynguin.utils.pynguinml import ndarray_cst, ndarray_mutation  # noqa: PLC0415

        if info.kind == "allowed_values":
            if not info.allowed_values or len(info.allowed_values) <= 1:
                return None
            new_value = randomness.choice(info.allowed_values)
            return ndarray_cst.ml_value_to_cst(new_value)

        if info.kind == "ml_scalar":
            if info.dtype is None or info.dtype == "None" or info.low is None or info.high is None:
                return None
            scalar = ndarray_mutation.replacement_value(info.dtype, info.low, info.high)
            return ndarray_cst.ml_value_to_cst(scalar)

        if info.kind == "ndarray":
            if info.dtype is None or info.low is None or info.high is None:
                return None
            value = ndarray_cst.ml_cst_to_value(old_expr)
            elements = _ndarray_mutation_elements(value, is_tuple=info.is_tuple)
            if elements is None:
                return None
            elements, changed = ndarray_mutation.mutate_ndarray(
                elements, info.dtype, info.low, info.high
            )
            if not changed:
                return None
            payload: list | tuple = tuple(elements) if info.is_tuple else elements
            return ndarray_cst.ml_value_to_cst(payload)

        return None

    # Note: _regen_args_in_place is deliberately NOT overridden.  Regenerating
    # arguments in place cannot rebuild ML statement chains (that would require
    # inserting new statements), and mutate_call already refuses to touch ML
    # statements themselves; for non-ML calls with constrained signatures the
    # base behaviour (reuse variables / inline literals) is an acceptable,
    # conservative fallback.


def _attribute_chain(dotted_path: str) -> cst.BaseExpression:
    """Build a CST attribute chain from a dotted path.

    E.g. ``"torch.tensor"`` becomes ``Attribute(Name("torch"), Name("tensor"))``.

    Args:
        dotted_path: The dotted path, e.g. ``"torch.tensor"``.

    Returns:
        A ``cst.Name`` for a bare identifier, else a nested ``cst.Attribute``.
    """
    parts = dotted_path.split(".")
    node: cst.BaseExpression = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node
