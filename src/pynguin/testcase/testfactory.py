#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a factory for libcst-backed test-case generation.

This factory is re-derived against the existing analysis model
(:class:`~pynguin.analyses.module.ModuleTestCluster` and
:class:`~pynguin.utils.generic.genericaccessibleobject.GenericAccessibleObject`).
It emits :mod:`libcst` nodes directly and refers to variables by *name*
(``var_N``) instead of ``VariableReference`` objects.
"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING

import libcst as cst

import pynguin.configuration as config
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.constants import ConstantProvider, EmptyConstantProvider
from pynguin.analyses.typesystem import Instance, ProperType
from pynguin.testcase import literalgen
from pynguin.testcase.testcase import Statement
from pynguin.utils import randomness
from pynguin.utils.naming import get_module_alias

if TYPE_CHECKING:
    import types

    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.analyses.typesystem import InferredSignature


_LOGGER = logging.getLogger(__name__)


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
            statement.accessible, gao.GenericCallableAccessibleObject
        ):
            return False

        generated = statement.accessible.generated_type()
        alternatives = self._test_cluster.get_generators_for(generated)
        candidates = [a for a in alternatives if a != statement.accessible]
        if not candidates:
            return False

        replacement = randomness.choice(candidates)
        old_var = statement.bound_variable
        pre_size = test_case.size()

        built = self._build_replacement_node(test_case, replacement, position)
        if built is None:
            return False
        node, bound_type, _cursor = built

        # Number of dependency statements inserted before the old statement.
        num_deps = test_case.size() - pre_size
        old_index = position + num_deps
        assign_var = old_var if old_var is not None else test_case.next_var_name()
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
                test_case, replacement.inferred_signature, cursor, 0
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
                test_case, replacement.inferred_signature, cursor, 0
            )
            func = cst.Attribute(value=cst.Name(receiver), attr=cst.Name(method_name))
            bound_type_m = _proper_type_to_raw(replacement.generated_type())
            return cst.Call(func=func, args=args), bound_type_m, cursor
        if isinstance(replacement, gao.GenericFunction):
            function_name = _function_call_name(replacement)
            if function_name is None:
                return None
            args, cursor = self._satisfy_params(
                test_case, replacement.inferred_signature, cursor, 0
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
        args, cursor = self._satisfy_params(test_case, accessible.inferred_signature, cursor, depth)
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
        args, cursor = self._satisfy_params(test_case, accessible.inferred_signature, cursor, depth)
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
        args, cursor = self._satisfy_params(test_case, accessible.inferred_signature, cursor, depth)
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

    # ------------------------------------------------------------------
    # Parameter satisfaction
    # ------------------------------------------------------------------

    def _satisfy_params(
        self,
        test_case: tc.TestCase,
        signature: InferredSignature,
        position: int,
        depth: int,
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
        if raw is not None and raw in literalgen.LITERAL_TYPES:
            # Emit as a named statement so it can be reused and mutated later.
            var_name, cursor = self._emit_primitive_statement(test_case, raw, cursor)
            return cst.Name(var_name), cursor
        mapped = literalgen.map_abstract_collection(raw) if raw is not None else None
        if mapped is not None:
            return literalgen.generate_literal(mapped, self._constant_provider), cursor
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

        new_expr = literalgen.mutate_literal(old_expr, stmt.bound_type, self._constant_provider)
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

    def _regen_args_in_place(
        self,
        test_case: tc.TestCase,
        signature: InferredSignature,
        position: int,
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
            elif raw is not None and raw in literalgen.LITERAL_TYPES:
                value = literalgen.generate_literal(raw, self._constant_provider)
            else:
                value = self._fallback_literal_value(raw)

            if is_positional_only:
                args.append(cst.Arg(value=value))
            else:
                args.append(cst.Arg(keyword=cst.Name(name), value=value))

        return args

    def _fallback_literal_value(self, raw: type | None) -> cst.BaseExpression:
        """Return a fallback CST literal for types not handled by create-or-reuse.

        Tries abstract-collection mapping first (e.g. ``Iterable`` → ``list``).
        For completely unresolvable types (``raw is None`` / ``Any``), returns a
        random primitive literal 90 % of the time and ``None`` 10 % of the time
        so that ``if x is None:`` branches remain reachable.

        Args:
            raw: The concrete Python class, or ``None`` for AnyType.

        Returns:
            A CST expression suitable for use as an argument literal.
        """
        mapped = literalgen.map_abstract_collection(raw) if raw is not None else None
        if mapped is not None:
            return literalgen.generate_literal(mapped, self._constant_provider)
        if raw is None:
            # AnyType / unresolvable: random primitive, occasionally None.
            if randomness.next_float() < 0.1:
                return cst.Name("None")
            fallback = randomness.choice(sorted(literalgen.LITERAL_TYPES, key=str))
            return literalgen.generate_literal(fallback, self._constant_provider)
        return cst.Name("None")

    def mutate_call(self, test_case: tc.TestCase, position: int) -> bool:
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
            args = self._regen_args_in_place(test_case, accessible.inferred_signature, position)
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
            args = self._regen_args_in_place(test_case, accessible.inferred_signature, position)
            new_call = cst.Call(
                func=cst.Attribute(value=cst.Name(receiver), attr=cst.Name(method_name)),
                args=args,
            )
        elif isinstance(accessible, gao.GenericFunction):
            function_name = _function_call_name(accessible)
            if function_name is None:
                return False
            args = self._regen_args_in_place(test_case, accessible.inferred_signature, position)
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

        is_primitive = issubclass(raw, (bool, int, float, str, bytes))
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

    The ML-specific generation path is currently inert; this subclass exists so
    that wiring expecting ``MLTestFactory`` keeps working. It defers to the base
    factory for all behaviour.
    """
