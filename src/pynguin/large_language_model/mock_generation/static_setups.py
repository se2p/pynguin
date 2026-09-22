#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Static, deterministic mock return-value setups derived from the SUT's AST.

A bare ``MagicMock`` reaches a function's entry branches but not its
value-dependent ones. Reading the module under test, this step derives two kinds
of setup without the LLM: candidate return values for attribute chains compared
against a literal, and iteration defaults so a mocked value yields one element.
The setups are attached to the mock templates the hint generator produces.
"""

from __future__ import annotations

import ast
import builtins as _builtins
from typing import Any

from pynguin.large_language_model.mock_generation.ast_helpers import param_names
from pynguin.large_language_model.mock_generation.mock_generator import RaiseException

#: Literal types that can be rendered as an ``ast.Constant`` candidate.
_CONST_TYPES = (int, float, str, bool, bytes, type(None))

#: Names of builtin exceptions, introspected (not hardcoded). A builtin except
#: type needs no import in the generated test, so only these are seeded.
_BUILTIN_EXCEPTIONS = frozenset(
    name
    for name in dir(_builtins)
    if isinstance(getattr(_builtins, name, None), type)
    and issubclass(getattr(_builtins, name), BaseException)
)


def function_param_setups(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, tuple[list[tuple[str, list[Any]]], list[str]]]:
    """Derive static setups per parameter of a single function.

    Each parameter is analysed on its own so a setup is attributed to the single
    parameter (and therefore the single mock target) it comes from, rather than
    shared across every mock in the module.

    Args:
        func: The function AST node.

    Returns:
        A mapping of parameter name to ``(mutable, lines)``, where ``mutable`` is
        a list of ``(attribute_chain, candidates)`` and ``lines`` is a list of
        fixed ``"m.<chain> = <rhs>"`` setup lines. Parameters with no setups are
        omitted.
    """
    result: dict[str, tuple[list[tuple[str, list[Any]]], list[str]]] = {}
    for param in param_names(func):
        single = {param}
        aliases = _collect_aliases(func, single)
        constants: dict[str, set[Any]] = {}
        lines: set[str] = set()
        side_effects: dict[str, set[str]] = {}
        _collect_branch_constants(func, single, aliases, constants)
        _collect_truthiness(func, single, aliases, constants)
        _collect_container_magic(func, single, aliases, constants, lines)
        _collect_iteration_defaults(func, single, aliases, lines)
        _collect_numeric_defaults(func, single, aliases, constants, lines)
        _collect_exception_setups(func, single, aliases, side_effects)
        mutable = _build_mutable(constants, side_effects)
        if mutable or lines:
            result[param] = (mutable, sorted(lines))
    return result


def _build_mutable(
    constants: dict[str, set[Any]], side_effects: dict[str, set[str]]
) -> list[tuple[str, list[Any]]]:
    """Build the ``(chain, candidates)`` list from collected constants and side-effects.

    Args:
        constants: Branch/truthiness constants keyed by attribute chain.
        side_effects: Builtin exception names keyed by method chain.

    Returns:
        The list of search-mutable setups.
    """
    mutable: list[tuple[str, list[Any]]] = []
    for chain, values in constants.items():
        candidates = _candidates(values)
        if candidates:
            mutable.append((chain, candidates))
    for method_chain, names in side_effects.items():
        target = f"{method_chain}.side_effect" if method_chain else "side_effect"
        # None = no side effect (happy path); each RaiseException flips an except.
        mutable.append((target, [None, *(RaiseException(name=n) for n in sorted(names))]))
    return mutable


def module_setups(source: str) -> tuple[list[tuple[str, list[Any]]], list[str]]:
    """Derive mock setups from parameter usage across the whole module.

    Aggregates :func:`function_param_setups` over every function. Use
    :func:`function_param_setups` when setups must stay attributed to a single
    parameter (as the generator does when attaching them per mock target).

    Args:
        source: the module-under-test source code.

    Returns:
        A pair ``(mutable, lines)`` where ``mutable`` is a list of
        ``(attribute_chain, candidates)`` for search-mutable return-value setups,
        and ``lines`` is a list of fixed ``"m.<chain> = <rhs>"`` setup lines. Both
        are meant to be attached to a mock template; ``m`` is renamed to the mock
        variable at render time.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    merged: dict[str, list[Any]] = {}
    lines: set[str] = set()
    for func in _iter_functions(tree):
        for mutable, param_lines in function_param_setups(func).values():
            for chain, candidates in mutable:
                bucket = merged.setdefault(chain, [])
                for candidate in candidates:
                    if candidate not in bucket:
                        bucket.append(candidate)
            lines.update(param_lines)
    return list(merged.items()), sorted(lines)


def _iter_functions(tree: ast.AST):
    """Yield every function/method definition anywhere in the module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _chain_of(node: ast.expr, params: set[str], aliases: dict[str, str]) -> str | None:
    """Return the mock attribute chain for an expression rooted at a mocked value.

    A call becomes ``return_value``. The root must be a parameter or a local
    variable aliased to a mocked chain. Returns None otherwise.
    """
    parts: list[str] = []
    current: ast.expr = node
    while True:
        if isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        elif isinstance(current, ast.Call):
            parts.append("return_value")
            current = current.func
        else:
            break
    if not isinstance(current, ast.Name):
        return None
    if current.id in params:
        base = ""
    elif current.id in aliases:
        base = aliases[current.id]
    else:
        return None
    tail = ".".join(reversed(parts))
    if base and tail:
        return f"{base}.{tail}"
    return base or tail or None


def _collect_aliases(func: ast.AST, params: set[str]) -> dict[str, str]:
    """Map a local variable to the mock chain it was assigned from.

    Iterates to a fixpoint so chained aliases resolve.
    """
    aliases: dict[str, str] = {}
    for _ in range(3):
        changed = False
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                chain = _chain_of(node.value, params, aliases)
                name = node.targets[0].id
                if chain and name not in params and aliases.get(name) != chain:
                    aliases[name] = chain
                    changed = True
        if not changed:
            break
    return aliases


def _collect_branch_constants(
    func: ast.AST, params: set[str], aliases: dict[str, str], out: dict[str, set[Any]]
) -> None:
    """Record ``chain -> {literals}`` for ``mocked-expr <cmp> literal`` predicates."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        left, right = node.left, node.comparators[0]
        for expr, other in ((left, right), (right, left)):
            chain = _chain_of(expr, params, aliases)
            if (
                chain is not None
                and isinstance(other, ast.Constant)
                and isinstance(other.value, _CONST_TYPES)
            ):
                out.setdefault(chain, set()).add(other.value)


def _collect_truthiness(
    func: ast.AST, params: set[str], aliases: dict[str, str], out: dict[str, set[Any]]
) -> None:
    """Seed mocked values used in truthiness / is-None guards.

    A bare mock attribute is a truthy MagicMock, so only one side of such a guard
    is reached. Seed a truthy value and a falsy value so the search flips both.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.If | ast.While | ast.IfExp):
            _seed_test(node.test, params, aliases, out)


def _seed_test(
    test: ast.expr, params: set[str], aliases: dict[str, str], out: dict[str, set[Any]]
) -> None:
    """Recurse through a boolean condition, seeding truthiness / is-None atoms."""
    if isinstance(test, ast.BoolOp):
        for value in test.values:
            _seed_test(value, params, aliases, out)
    elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        _seed_test(test.operand, params, aliases, out)
    elif isinstance(test, ast.Compare) and len(test.ops) == 1:
        # is / is-not None: seed a None and a non-None value
        if isinstance(test.ops[0], ast.Is | ast.IsNot):
            for expr, other in (
                (test.left, test.comparators[0]),
                (test.comparators[0], test.left),
            ):
                chain = _chain_of(expr, params, aliases)
                if chain and isinstance(other, ast.Constant) and other.value is None:
                    out.setdefault(chain, set()).update({None, True})
        # equality is handled by _collect_branch_constants
    else:
        # bare truthiness: seed a truthy and a falsy value
        chain = _chain_of(test, params, aliases)
        if chain:
            out.setdefault(chain, set()).update({True, None})


def _is_param(node: ast.expr, params: set[str]) -> bool:
    """Whether *node* is a bare parameter name."""
    return isinstance(node, ast.Name) and node.id in params


def _magic_key(
    node: ast.expr, params: set[str], aliases: dict[str, str], dunder: str
) -> str | None:
    """Attribute-chain key for a container dunder on a mocked value, else None."""
    chain = _chain_of(node, params, aliases)
    if chain:
        return f"{chain}.{dunder}.return_value"
    if _is_param(node, params):
        return f"{dunder}.return_value"
    return None


def _collect_container_magic(
    func: ast.AST,
    params: set[str],
    aliases: dict[str, str],
    consts: dict[str, set[Any]],
    lines: set[str],
) -> None:
    """Seed container dunders so length, membership and subscription branch.

    Length and membership are seeded as search-mutable values so both sides of a
    guard are reachable. Subscription gets a fixed mock element so it does not
    raise on a bare mock.
    """
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "len"
            and len(node.args) == 1
        ):
            key = _magic_key(node.args[0], params, aliases, "__len__")
            if key:
                consts.setdefault(key, set()).update({0, 1})
        elif (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.In | ast.NotIn)
        ):
            key = _magic_key(node.comparators[0], params, aliases, "__contains__")
            if key:
                consts.setdefault(key, set()).update({True, False})
        elif isinstance(node, ast.Subscript):
            chain = _chain_of(node.value, params, aliases)
            if chain:
                lines.add(f"m.{chain}.__getitem__.return_value = MagicMock()")
            elif _is_param(node.value, params):
                lines.add("m.__getitem__.return_value = MagicMock()")


def _collect_numeric_defaults(
    func: ast.AST,
    params: set[str],
    aliases: dict[str, str],
    consts: dict[str, set[Any]],
    lines: set[str],
) -> None:
    """Give a numeric default to a mocked value used in arithmetic.

    Arithmetic on a bare mock raises ``TypeError``, so seed ``0``. Skipped when
    the chain already has a branch constant.
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.BinOp):
            continue
        for operand in (node.left, node.right):
            chain = _chain_of(operand, params, aliases)
            if chain and chain not in consts:
                lines.add(f"m.{chain} = 0")


def _collect_iteration_defaults(
    func: ast.AST, params: set[str], aliases: dict[str, str], out: set[str]
) -> None:
    """Record setup lines so iterating a mocked value runs the loop, not crashes."""
    for node in ast.walk(func):
        if not isinstance(node, ast.For):
            continue
        chain = _chain_of(node.iter, params, aliases)
        if chain:
            # return one-item list
            out.add(f"m.{chain} = [MagicMock()]")
        elif isinstance(node.iter, ast.Name) and node.iter.id in params:
            out.add("m.__iter__.return_value = iter([MagicMock()])")


def _builtin_exc_names(node: ast.expr | None) -> set[str]:
    """Builtin exception names named by an ``except`` clause (Name or tuple of Names)."""
    if node is None:
        return set()
    elts = node.elts if isinstance(node, ast.Tuple) else [node]
    return {e.id for e in elts if isinstance(e, ast.Name) and e.id in _BUILTIN_EXCEPTIONS}


def _method_chain(func_expr: ast.expr, params: set[str], aliases: dict[str, str]) -> str | None:
    """Mock attribute chain for the callable in a call.

    Returns ``""`` when the mock itself is called, or None when the callable is
    not rooted at a mocked value.
    """
    chain = _chain_of(func_expr, params, aliases)
    if chain is not None:
        return chain
    if _is_param(func_expr, params):
        return ""
    return None


def _collect_exception_setups(
    func: ast.AST, params: set[str], aliases: dict[str, str], out: dict[str, set[str]]
) -> None:
    """Record ``method chain -> {builtin exceptions}`` for mocked calls inside a try.

    When a mocked call sits in a ``try`` whose ``except`` catches a builtin
    exception, seed the mock's ``side_effect`` to raise it in some tests so the
    error-handling branch is reached (and not raise in others for the happy path).
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.Try):
            continue
        names: set[str] = set()
        for handler in node.handlers:
            names |= _builtin_exc_names(handler.type)
        if not names:
            continue
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call):
                    method = _method_chain(sub.func, params, aliases)
                    if method is not None:
                        out.setdefault(method, set()).update(names)


def _candidates(values: set[Any]) -> list[Any]:
    """Constants to explore for a branch attribute, plus one out-of-range value."""
    consts = [v for v in values if isinstance(v, _CONST_TYPES)]
    if not consts:
        return []
    out = list(dict.fromkeys(consts))
    ints = [v for v in out if isinstance(v, int) and not isinstance(v, bool)]
    if ints:
        extra = max(ints) + 1
        if extra not in out:
            out.append(extra)
    return out
