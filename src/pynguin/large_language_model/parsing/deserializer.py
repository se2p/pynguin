# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
# SPDX-FileCopyrightText: 2023 Microsoft
#
# SPDX-License-Identifier: MIT
#
"""Deserializes LLM-emitted Python source into ``TestCase`` objects.

Because the internal representation stores libcst statement nodes directly,
turning LLM-generated source into ``TestCase``/``Statement`` objects is mostly
"parse + validate + normalize": there is no separate statement class hierarchy
or variable-reference graph to reconstruct.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import importlib
import logging
from typing import TYPE_CHECKING, Any

import libcst as cst

import pynguin.assertion.assertion as ass
import pynguin.testcase.testcase as tc
from pynguin import configuration as config
from pynguin.large_language_model.parsing.rewriter import rewrite_tests
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.naming import get_module_alias
from pynguin.utils.type_utils import is_assertable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pynguin.analyses.module import TestCluster
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DeserializationResult:
    """Result of deserializing LLM-emitted source into test cases."""

    test_cases: list[tc.TestCase]
    total_statements: int
    parsed_statements: int
    uninterpreted_statements: int


# ---------------------------------------------------------------------------
# Small, self-contained CST helpers
# ---------------------------------------------------------------------------


def _dotted_chain(node: cst.BaseExpression) -> list[str] | None:
    """Return the root-first component list of a pure ``Name``/``Attribute`` chain.

    Args:
        node: The expression to inspect.

    Returns:
        The list of components (e.g. ``["foo", "bar"]`` for ``foo.bar``), or
        ``None`` if *node* is not a pure attribute chain rooted in a ``Name``
        (e.g. it contains a call or subscript).
    """
    parts: list[str] = []
    cur: cst.BaseExpression = node
    while isinstance(cur, cst.Attribute):
        parts.append(cur.attr.value)
        cur = cur.value
    if isinstance(cur, cst.Name):
        parts.append(cur.value)
        parts.reverse()
        return parts
    return None


def _build_chain(parts: list[str]) -> cst.BaseExpression:
    """Build a ``Name``/``Attribute`` chain from root-first *parts*.

    Args:
        parts: The root-first component list.

    Returns:
        The corresponding CST expression.
    """
    node: cst.BaseExpression = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _try_literal(node: cst.BaseExpression) -> tuple[type, Any] | None:
    """Try to evaluate *node* as a Python literal.

    Args:
        node: The expression to evaluate.

    Returns:
        A tuple of (type, value), or ``None`` if *node* is not a literal.
    """
    src = cst.Module(body=[cst.SimpleStatementLine(body=[cst.Expr(value=node)])]).code.strip()
    try:
        value = ast.literal_eval(src)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    return type(value), value


class _RootNameCollector(cst.CSTVisitor):
    """Collects the root names read by a statement.

    Unlike a naive ``Name``-leaf collector, attribute chains (``foo.bar.baz``)
    only contribute their root (``foo``); the intermediate/leaf attribute
    names are member names, not references, and must not be confused with
    variable reads.
    """

    def __init__(self) -> None:
        self.names: set[str] = set()
        self._in_target = 0

    @staticmethod
    def collect(node: cst.CSTNode) -> set[str]:
        """Collect the root names read by *node*.

        Args:
            node: The node to inspect.

        Returns:
            The set of root names read by *node*.
        """
        collector = _RootNameCollector()
        node.visit(collector)
        return collector.names

    def visit_AssignTarget(self, node: cst.AssignTarget) -> bool:  # noqa: N802
        self._in_target += 1
        return True

    def leave_AssignTarget(self, original_node: cst.AssignTarget) -> None:  # noqa: N802
        self._in_target -= 1

    def visit_Arg(self, node: cst.Arg) -> bool:  # noqa: N802
        # A call argument's ``keyword`` (e.g. ``param4`` in ``f(param4=x)``) is a
        # parameter name, not a variable read; only its ``value`` is. Visit the
        # value manually and skip the rest of the node's children.
        node.value.visit(self)
        return False

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        chain = _dotted_chain(node)
        if chain is not None:
            if self._in_target == 0:
                self.names.add(chain[0])
            return False
        return True

    def visit_Name(self, node: cst.Name) -> bool:  # noqa: N802
        if self._in_target == 0:
            self.names.add(node.value)
        return True


class _LocalRenamer(cst.CSTTransformer):
    """Renames bare ``Name`` leaves according to a mapping."""

    def __init__(self, rename: dict[str, str]) -> None:
        self._rename = rename

    def leave_Name(  # noqa: N802
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.Name:
        new = self._rename.get(updated_node.value)
        return updated_node.with_changes(value=new) if new is not None else updated_node


def _imported_local_names(node: cst.Import | cst.ImportFrom) -> list[str]:
    """Return the local (bound) names introduced by an import statement.

    Args:
        node: The import statement.

    Returns:
        The list of local names bound by the import.
    """
    names = node.names
    if isinstance(names, cst.ImportStar):
        return []
    result = []
    for alias in names:
        if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
            result.append(alias.asname.name.value)
        elif isinstance(alias.name, cst.Name):
            result.append(alias.name.value)
        elif isinstance(alias.name, cst.Attribute):
            chain = _dotted_chain(alias.name)
            if chain:
                result.append(chain[0])
    return result


def _count_statements(node: cst.CSTNode) -> int:
    """Count all non-assert statements in *node*'s subtree (excluding *node*).

    Args:
        node: The node whose subtree should be counted.

    Returns:
        The number of non-assert statements.
    """

    class _Counter(cst.CSTVisitor):
        def __init__(self) -> None:
            self.count = 0

        def on_visit(self, inner: cst.CSTNode) -> bool:
            if isinstance(inner, cst.SimpleStatementLine):
                self.count += sum(1 for small in inner.body if not isinstance(small, cst.Assert))
            elif isinstance(inner, cst.BaseCompoundStatement):
                self.count += 1
            return True

    counter = _Counter()
    node.visit(counter)
    return counter.count


def _proper_type_to_raw(proper_type: Any) -> type | None:
    """Best-effort conversion of a ``ProperType`` to a raw Python type.

    Args:
        proper_type: The ``ProperType`` to convert.

    Returns:
        The raw Python type, or ``None`` if it could not be determined.
    """
    raw = getattr(getattr(proper_type, "type", None), "raw_type", None)
    return raw if isinstance(raw, type) else None


# ---------------------------------------------------------------------------
# SUT-alias normalization
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _SutBinding:
    """A rule that rewrites references to a locally-bound SUT import."""

    required_next: tuple[str, ...]
    substitution_head: tuple[str, ...]


class _SutReferenceNormalizer(cst.CSTTransformer):
    """Rewrites LLM-emitted references to the module under test.

    Detects ``import foo.bar``, ``import foo.bar as m`` and
    ``from foo.bar import baz [as b]`` style imports of the module under
    test, drops those import lines, and rewrites every reference to the
    canonical ``get_module_alias(...)`` attribute form used everywhere else
    in the generated/exported code.
    """

    def __init__(self, module_name: str, module_alias: str) -> None:
        self._module_name = module_name
        self._module_alias = module_alias
        self._bindings: dict[str, _SutBinding] = {}
        self._replacements: dict[int, cst.BaseExpression] = {}

    def _resolve(self, chain: list[str]) -> list[str] | None:
        root, *rest = chain
        binding = self._bindings.get(root)
        if binding is None:
            return None
        n = len(binding.required_next)
        if tuple(rest[:n]) != binding.required_next:
            return None
        leftover = rest[n:]
        return [self._module_alias, *binding.substitution_head, *leftover]

    def _handle_import(self, node: cst.Import) -> cst.Import | None:
        kept = []
        for alias in node.names:
            dotted = _dotted_chain(alias.name)
            if dotted is not None and ".".join(dotted) == self._module_name:
                if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
                    self._bindings[alias.asname.name.value] = _SutBinding((), ())
                else:
                    self._bindings[dotted[0]] = _SutBinding(tuple(dotted[1:]), ())
                continue
            kept.append(alias)
        if not kept:
            return None
        return node.with_changes(names=kept)

    def _handle_import_from(self, node: cst.ImportFrom) -> cst.ImportFrom | None:
        if node.relative or node.module is None:
            return node
        dotted = _dotted_chain(node.module)
        if dotted is None or ".".join(dotted) != self._module_name:
            return node
        if isinstance(node.names, cst.ImportStar):
            return node
        for alias in node.names:
            if not isinstance(alias.name, cst.Name):
                continue
            member = alias.name.value
            local = (
                alias.asname.name.value
                if alias.asname is not None and isinstance(alias.asname.name, cst.Name)
                else member
            )
            self._bindings[local] = _SutBinding((), (member,))
        return None

    def leave_SimpleStatementLine(  # noqa: N802
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        new_body: list[cst.BaseSmallStatement] = []
        for small in updated_node.body:
            if isinstance(small, cst.Import):
                kept_import = self._handle_import(small)
                if kept_import is not None:
                    new_body.append(kept_import)
            elif isinstance(small, cst.ImportFrom):
                kept_from = self._handle_import_from(small)
                if kept_from is not None:
                    new_body.append(kept_from)
            else:
                new_body.append(small)
        if not new_body:
            return cst.RemoveFromParent()
        return updated_node.with_changes(body=new_body)

    def visit_Import(self, node: cst.Import) -> bool:  # noqa: N802
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:  # noqa: N802
        return False

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        chain = _dotted_chain(node)
        if chain is not None:
            replacement = self._resolve(chain)
            if replacement is not None:
                self._replacements[id(node)] = _build_chain(replacement)
            return False
        return True

    def leave_Attribute(  # noqa: N802
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        return self._replacements.pop(id(original_node), updated_node)

    def visit_Name(self, node: cst.Name) -> bool:  # noqa: N802
        replacement = self._resolve([node.value])
        if replacement is not None:
            self._replacements[id(node)] = _build_chain(replacement)
        return True

    def leave_Name(  # noqa: N802
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        return self._replacements.pop(id(original_node), updated_node)


def normalize_sut_references(module: cst.Module, module_name: str, module_alias: str) -> cst.Module:
    """Rewrite every reference to *module_name* in *module* to the canonical alias.

    ``CstStatementDeserializer.deserialize_function`` runs :class:`_SutReferenceNormalizer`
    over each individual function body, matching the shape of LLM-flattened code
    (where the rewriter pre-pass hoists imports into every test function). Callers
    that instead have a single, module-level SUT import shared by every test
    function -- e.g. Pynguin's own exported test suites, consumed by
    initial-population seeding -- should normalize the whole module once with this
    function before handing individual ``FunctionDef``s to
    :meth:`CstStatementDeserializer.deserialize_function`.

    Args:
        module: The module to normalize.
        module_name: The dotted name of the module under test.
        module_alias: The canonical alias for the module under test.

    Returns:
        The normalized module, with SUT imports removed and references rewritten.
    """
    normalized = module.visit(_SutReferenceNormalizer(module_name, module_alias))
    assert isinstance(normalized, cst.Module)
    return normalized


# ---------------------------------------------------------------------------
# Assertion lifting (shared between the deserializer and the LLM assertion
# generator's round-trip)
# ---------------------------------------------------------------------------


def _resolve_type_ref(node: cst.BaseExpression) -> tuple[str, str] | tuple[None, None]:
    if isinstance(node, cst.Name):
        if node.value in dir(builtins):
            return "builtins", node.value
        return None, None
    chain = _dotted_chain(node)
    if chain and len(chain) >= 2:
        return config.configuration.module_name, ".".join(chain[1:])
    return None, None


def _parse_bare_name_assertion(
    test: cst.BaseExpression, known_vars: Mapping[str, type | None]
) -> tuple[str, ass.Assertion] | None:
    """Parse the ``assert x`` shape."""
    if isinstance(test, cst.Name) and test.value in known_vars:
        return test.value, ass.ObjectAssertion(test.value, value=True)
    return None


def _parse_isinstance_assertion(
    test: cst.BaseExpression, known_vars: Mapping[str, type | None]
) -> tuple[str, ass.Assertion] | None:
    """Parse the ``assert isinstance(x, T)`` shape."""
    if not (
        isinstance(test, cst.Call)
        and isinstance(test.func, cst.Name)
        and test.func.value == "isinstance"
        and len(test.args) == 2
    ):
        return None
    recv = test.args[0].value
    if isinstance(recv, cst.Name) and recv.value in known_vars:
        module, qualname = _resolve_type_ref(test.args[1].value)
        if module is not None:
            return recv.value, ass.IsInstanceAssertion(recv.value, module, qualname)
    return None


def _is_len_equality(test: cst.BaseExpression) -> bool:
    """Whether *test* has the ``len(x) == <literal>`` comparison shape."""
    if not (isinstance(test, cst.Comparison) and len(test.comparisons) == 1):
        return False
    if not isinstance(test.comparisons[0].operator, cst.Equal):
        return False
    left = test.left
    if not (isinstance(left, cst.Call) and isinstance(left.func, cst.Name)):
        return False
    return left.func.value == "len" and len(left.args) == 1


def _parse_len_equality_assertion(
    test: cst.BaseExpression, known_vars: Mapping[str, type | None]
) -> tuple[str, ass.Assertion] | None:
    """Parse the ``assert len(x) == n`` shape."""
    if not (_is_len_equality(test) and isinstance(test, cst.Comparison)):
        return None
    left = test.left
    assert isinstance(left, cst.Call)
    recv = left.args[0].value
    lit = _try_literal(test.comparisons[0].comparator)
    if (
        isinstance(recv, cst.Name)
        and recv.value in known_vars
        and lit is not None
        and isinstance(lit[1], int)
    ):
        return recv.value, ass.CollectionLengthAssertion(recv.value, lit[1])
    return None


def _parse_equality_literal_assertion(
    test: cst.BaseExpression, known_vars: Mapping[str, type | None]
) -> tuple[str, ass.Assertion] | None:
    """Parse the ``assert x == <literal>``/``assert x is <literal>`` shape."""
    if not (
        isinstance(test, cst.Comparison)
        and len(test.comparisons) == 1
        and isinstance(test.comparisons[0].operator, cst.Equal | cst.Is)
        and isinstance(test.left, cst.Name)
        and test.left.value in known_vars
    ):
        return None
    lit = _try_literal(test.comparisons[0].comparator)
    if lit is None:
        return None
    typ, value = lit
    if typ is float:
        return test.left.value, ass.FloatAssertion(test.left.value, value)
    if is_assertable(value):
        return test.left.value, ass.ObjectAssertion(test.left.value, value)
    return None


_ASSERTION_SHAPE_PARSERS = (
    _parse_bare_name_assertion,
    _parse_isinstance_assertion,
    _parse_len_equality_assertion,
    _parse_equality_literal_assertion,
)


def parse_assertion(
    node: cst.Assert | str,
    known_vars: Mapping[str, type | None],
) -> tuple[str, ass.Assertion] | None:
    """Parse a single supported ``assert`` shape into an ``Assertion``.

    Supported shapes: ``assert x``, ``assert x == <literal>``/``assert x is
    <literal>``, ``assert isinstance(x, T)``, ``assert len(x) == n`` and
    ``assert a or b`` (each operand tried in turn).

    Args:
        node: The assert statement (or its source line) to parse.
        known_vars: The variable names currently in scope.

    Returns:
        A tuple of (bound variable name, assertion), or ``None`` if the
        assertion shape is not supported or references an unknown variable.
    """
    if isinstance(node, str):
        try:
            parsed = cst.parse_statement(node.strip())
        except cst.ParserSyntaxError:
            return None
        if not (
            isinstance(parsed, cst.SimpleStatementLine)
            and len(parsed.body) == 1
            and isinstance(parsed.body[0], cst.Assert)
        ):
            return None
        assert_node = parsed.body[0]
    else:
        assert_node = node

    test = assert_node.test

    if isinstance(test, cst.BooleanOperation) and isinstance(test.operator, cst.Or):
        left = parse_assertion(cst.Assert(test=test.left), known_vars)
        if left is not None:
            return left
        return parse_assertion(cst.Assert(test=test.right), known_vars)

    for shape_parser in _ASSERTION_SHAPE_PARSERS:
        result = shape_parser(test, known_vars)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# Statement deserialization
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _FunctionDeserializationState:
    """Mutable state threaded through a single function's deserialization."""

    known: set[str]
    testcase: tc.TestCase = dataclasses.field(default_factory=tc.TestCase)
    rename_map: dict[str, str] = dataclasses.field(default_factory=dict)
    last_index_for_name: dict[str, int] = dataclasses.field(default_factory=dict)
    bound_types_by_orig: dict[str, type | None] = dataclasses.field(default_factory=dict)


class CstStatementDeserializer:
    """Per-test-function parser: LLM-emitted CST statements -> ``Statement``s."""

    def __init__(self, test_cluster: TestCluster, *, create_assertions: bool) -> None:  # noqa: D107
        self._test_cluster = test_cluster
        self._create_assertions = create_assertions
        self._module_name = config.configuration.module_name
        self._module_alias = get_module_alias(self._module_name)
        self._ambient_names = self._compute_ambient_names()

    def _compute_ambient_names(self) -> frozenset[str]:
        names: set[str] = set(dir(builtins)) | {"pytest", self._module_alias}
        module = None
        try:
            module = importlib.import_module(self._module_name)
        except BaseException:  # noqa: BLE001
            logger.debug("Could not import %s to compute ambient names", self._module_name)
        if module is not None:
            names.update(vars(module).keys())
        for obj in getattr(self._test_cluster, "accessible_objects_under_test", ()):
            func_name = getattr(obj, "function_name", None)
            if func_name:
                names.add(func_name)
            owner = getattr(obj, "owner", None)
            if owner is not None and getattr(owner, "name", None):
                names.add(owner.name)
        return frozenset(names)

    def _resolve_call(
        self, call: cst.Call, bound_types: dict[str, type | None]
    ) -> GenericAccessibleObject | None:
        func = call.func
        if isinstance(func, cst.Name):
            call_name = func.value
            receiver_name: str | None = None
        elif isinstance(func, cst.Attribute) and isinstance(func.value, cst.Name):
            call_name = func.attr.value
            receiver_name = func.value.value
        else:
            return None

        # A bare call (``Foo()``) or a call through the canonical module alias
        # (``<alias>.Foo()``, the form ``_SutReferenceNormalizer`` rewrites SUT
        # references to) both refer to a constructor/module-level function, not
        # a method call on an instance.
        is_module_level_call = receiver_name is None or receiver_name == self._module_alias

        for obj in self._test_cluster.accessible_objects_under_test:
            if isinstance(obj, GenericConstructor):
                owner_name = obj.owner.name if obj.owner is not None else None
                if is_module_level_call and call_name == owner_name:
                    return obj
            elif isinstance(obj, GenericMethod):
                if receiver_name is not None and call_name == obj.method_name:
                    receiver_type = bound_types.get(receiver_name)
                    owner_name = obj.owner.name if obj.owner is not None else None
                    if (
                        receiver_type is None
                        or getattr(receiver_type, "__name__", None) == owner_name
                    ):
                        return obj
            elif (
                isinstance(obj, GenericFunction)
                and is_module_level_call
                and call_name == obj.function_name
            ):
                return obj
        return None

    def _infer_rhs(
        self, value: cst.BaseExpression, bound_types: dict[str, type | None]
    ) -> tuple[type | None, GenericAccessibleObject | None, bool]:
        lit = _try_literal(value)
        if lit is not None:
            return lit[0], None, True
        if isinstance(value, cst.Call):
            accessible = self._resolve_call(value, bound_types)
            if accessible is not None:
                return _proper_type_to_raw(accessible.generated_type()), accessible, True
            return None, None, False
        return None, None, False

    def _admit_small_statement(
        self, small: cst.BaseSmallStatement, bound_types: dict[str, type | None]
    ) -> (
        tuple[
            cst.SimpleStatementLine, str | None, type | None, GenericAccessibleObject | None, bool
        ]
        | None
    ):
        if isinstance(small, cst.Assign):
            if len(small.targets) != 1:
                return None
            target = small.targets[0].target
            if not isinstance(target, cst.Name):
                return None
            bound_type, accessible, resolved = self._infer_rhs(small.value, bound_types)
            node = cst.SimpleStatementLine(body=[small])
            return node, target.value, bound_type, accessible, not resolved
        if isinstance(small, cst.Expr):
            _, accessible, resolved = self._infer_rhs(small.value, bound_types)
            node = cst.SimpleStatementLine(body=[small])
            return node, None, None, accessible, not resolved
        return None

    def _handle_assert(self, small: cst.Assert, state: _FunctionDeserializationState) -> int:
        """Handle a single ``assert`` small-statement.

        Either lifts it into an ``Assertion`` attached to the statement that
        bound the referenced variable, keeps it as a raw (renamed) statement
        when its shape is unsupported but all referenced names are known, or
        drops it.

        Args:
            small: The assert small-statement.
            state: The mutable per-function deserialization state.

        Returns:
            The number of uninterpreted statements contributed (0 or 1).
        """
        result = parse_assertion(small, state.bound_types_by_orig)
        if result is not None:
            var, assertion = result
            idx = state.last_index_for_name.get(var)
            if idx is not None:
                bound_stmt = state.testcase.get_statement(idx)
                # parse_assertion resolves against the pre-rename source, so
                # the assertion's source still carries the original variable
                # name; retarget it to the fresh var_N name actually bound by
                # the statement it is attached to.
                if bound_stmt.bound_variable is not None:
                    assertion.source = bound_stmt.bound_variable
                bound_stmt.assertions.append(assertion)
            return 0

        names = _RootNameCollector.collect(small)
        if not names <= state.known:
            return 0

        assert_node = cst.SimpleStatementLine(body=[small])
        # Kept raw asserts may reference variables bound by earlier
        # statements, which have since been renamed to var_N; without this
        # rename they'd reference the (no longer defined) original name and
        # raise a NameError at runtime.
        if state.rename_map:
            renamed_assert = assert_node.visit(_LocalRenamer(state.rename_map))
            assert isinstance(renamed_assert, cst.SimpleStatementLine)
            assert_node = renamed_assert
        state.testcase.add_statement(tc.Statement(node=assert_node))
        return 1

    def _handle_ordinary_statement(
        self, small: cst.BaseSmallStatement, state: _FunctionDeserializationState
    ) -> tuple[int, int]:
        """Handle a non-assert, non-import small-statement.

        Args:
            small: The small-statement.
            state: The mutable per-function deserialization state.

        Returns:
            A tuple of (parsed delta, uninterpreted delta), each 0 or 1.
        """
        admitted = self._admit_small_statement(small, state.bound_types_by_orig)
        if admitted is None:
            return 0, 0
        node, bound_var, bound_type, accessible, is_uninterpreted = admitted
        names = _RootNameCollector.collect(node)
        if bound_var is not None:
            names.discard(bound_var)
        if not names <= state.known:
            return 0, 0

        new_bound = None
        if bound_var is not None:
            new_bound = state.testcase.next_var_name()
            state.rename_map[bound_var] = new_bound
            state.known.add(bound_var)
            state.bound_types_by_orig[bound_var] = bound_type
            state.last_index_for_name[bound_var] = state.testcase.size()
        # The rename map must include *this* statement's own binding (if any)
        # before renaming its node, otherwise the statement's target keeps
        # its original name while later statements reference the fresh
        # var_N name, producing a NameError at runtime.
        if state.rename_map:
            renamed = node.visit(_LocalRenamer(state.rename_map))
            assert isinstance(renamed, cst.SimpleStatementLine)
            node = renamed
        state.testcase.add_statement(
            tc.Statement(
                node=node,
                bound_variable=new_bound,
                bound_type=bound_type,
                accessible=accessible,
            )
        )
        return 1, (1 if is_uninterpreted else 0)

    def deserialize_function(self, fn: cst.FunctionDef) -> tuple[tc.TestCase, int, int, int]:
        """Deserialize a single ``test_*``/``seed_test_*`` function.

        Args:
            fn: The function definition to deserialize.

        Returns:
            A tuple of (test case, total statements, parsed statements,
            uninterpreted statements). The test case may be empty if nothing
            could be parsed.
        """
        total = _count_statements(fn.body)
        normalizer = _SutReferenceNormalizer(self._module_name, self._module_alias)
        normalized = fn.body.visit(normalizer)
        assert isinstance(normalized, cst.IndentedBlock)

        state = _FunctionDeserializationState(known=set(self._ambient_names))
        parsed = 0
        uninterpreted = 0

        for line in normalized.body:
            if not isinstance(line, cst.SimpleStatementLine):
                continue  # Compound statement: unsupported shape, dropped.
            for small in line.body:
                if isinstance(small, cst.Assert):
                    if not self._create_assertions:
                        continue
                    uninterpreted += self._handle_assert(small, state)
                    continue

                if isinstance(small, cst.Import | cst.ImportFrom):
                    parsed += 1
                    uninterpreted += 1
                    state.known.update(_imported_local_names(small))
                    state.testcase.add_statement(
                        tc.Statement(node=cst.SimpleStatementLine(body=[small]))
                    )
                    continue

                parsed_delta, uninterpreted_delta = self._handle_ordinary_statement(small, state)
                parsed += parsed_delta
                uninterpreted += uninterpreted_delta

        return state.testcase, total, parsed, uninterpreted


def deserialize_code_to_testcases(
    test_file_contents: str,
    test_cluster: TestCluster,
    *,
    create_assertions: bool | None = None,
) -> DeserializationResult | None:
    """Extract as many ``TestCase`` objects as possible from the given code.

    Args:
        test_file_contents: Code containing tests.
        test_cluster: The test cluster to deserialize with.
        create_assertions: Whether to lift ``assert`` statements into
            ``Assertion`` objects. Defaults to whether the configured
            assertion generator is ``LLM``.

    Returns:
        The deserialization result, or ``None`` if the code could not be
        parsed at all.
    """
    if create_assertions is None:
        create_assertions = (
            config.configuration.test_case_output.assertion_generation
            == config.AssertionGenerator.LLM
        )

    try:
        rewritten = rewrite_tests(test_file_contents)
        joined = "\n\n".join(rewritten.values())
        module = cst.parse_module(joined)
    except BaseException as e:  # noqa: BLE001
        logger.error(e)
        return None

    deserializer = CstStatementDeserializer(test_cluster, create_assertions=create_assertions)
    test_cases: list[tc.TestCase] = []
    total_statements = 0
    parsed_statements = 0
    uninterpreted_statements = 0

    for stmt_ in module.body:
        if not isinstance(stmt_, cst.FunctionDef):
            continue
        if not (stmt_.name.value.startswith(("test_", "seed_test_"))):
            continue
        testcase, f_total, f_parsed, f_uninterpreted = deserializer.deserialize_function(stmt_)
        total_statements += f_total
        parsed_statements += f_parsed
        uninterpreted_statements += f_uninterpreted
        if testcase.size() > 0:
            test_cases.append(testcase)
            logger.debug("Successfully imported %s.", stmt_.name.value)
        else:
            logger.debug("Failed to parse %s.", stmt_.name.value)

    return DeserializationResult(
        test_cases, total_statements, parsed_statements, uninterpreted_statements
    )
