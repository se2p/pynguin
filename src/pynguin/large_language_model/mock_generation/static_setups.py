#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Static, deterministic mock return-value setups derived from the SUT's AST.

A bare ``MagicMock`` reaches a function's entry branches but not its
value-dependent ones. With no LLM and no hardcoded vocabulary, this module reads
the module under test and derives two kinds of setup. For every
``<mocked-expr> <cmp> literal`` predicate it seeds the mock attribute chain with
those literals so the search can flip the branch. When a mocked value is iterated
it makes it yield one element so the loop body runs instead of raising. A mocked
expression is one rooted at a parameter, or at a local variable assigned from a
parameter's attribute or call chain, for example ``resp = session.get(...)`` makes
``resp.status_code`` resolve to ``get.return_value.status_code``.
"""

from __future__ import annotations

import ast
import builtins as _builtins
from typing import Any

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


def module_setups(source: str) -> tuple[list[tuple[str, list[Any]]], list[str]]:
    """Derive mock setups from parameter usage in *source*.

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

    constants: dict[str, set[Any]] = {}
    lines: set[str] = set()
    side_effects: dict[str, set[str]] = {}
    for func in _iter_functions(tree):
        params = _param_names(func)
        if not params:
            continue
        aliases = _collect_aliases(func, params)
        _collect_branch_constants(func, params, aliases, constants)
        _collect_truthiness(func, params, aliases, constants)
        _collect_container_magic(func, params, aliases, constants, lines)
        _collect_iteration_defaults(func, params, aliases, lines)
        _collect_numeric_defaults(func, params, aliases, constants, lines)
        _collect_exception_setups(func, params, aliases, side_effects)

    mutable: list[tuple[str, list[Any]]] = []
    for chain, values in constants.items():
        candidates = _candidates(values)
        if candidates:
            mutable.append((chain, candidates))
    for method_chain, names in side_effects.items():
        target = f"{method_chain}.side_effect" if method_chain else "side_effect"
        # None = no side effect (happy path); each RaiseException flips an except.
        candidates = [None, *(RaiseException(name=n) for n in sorted(names))]
        mutable.append((target, candidates))
    return mutable, sorted(lines)


def _iter_functions(tree: ast.AST):
    """Yield every function/method definition anywhere in the module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _param_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func.args
    return {
        a.arg
        for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)
        if a.arg not in {"self", "cls"}
    }


def _chain_of(node: ast.expr, params: set[str], aliases: dict[str, str]) -> str | None:
    """Return the mock attribute chain for an expression rooted at a mocked value.

    A call becomes ``return_value``. The root must be a parameter or a local
    variable aliased to a mocked chain. ``param.attr`` -> ``"attr"``;
    ``resp.status_code`` where ``resp = session.get(...)`` ->
    ``"get.return_value.status_code"``. Returns None otherwise.
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

    ``resp = session.get(...)`` -> ``{"resp": "get.return_value"}``. Iterates to a
    fixpoint so chained aliases (``a = p.x``; ``b = a.y``) resolve.
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

    Library code branches far more on ``if x.enabled:`` / ``if result is None:``
    than on ``x == literal``. A bare mock attribute is a truthy MagicMock, so only
    one side of each such guard is ever reached. Seed a truthy value (True) and a
    falsy value (None) so the search can flip both sides.
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
        # ``x is None`` / ``x is not None`` -> seed both a None and a non-None value.
        if isinstance(test.ops[0], ast.Is | ast.IsNot):
            for expr, other in (
                (test.left, test.comparators[0]),
                (test.comparators[0], test.left),
            ):
                chain = _chain_of(expr, params, aliases)
                if chain and isinstance(other, ast.Constant) and other.value is None:
                    out.setdefault(chain, set()).update({None, True})
        # ``x == literal`` is already handled by _collect_branch_constants.
    else:
        # Bare truthiness: ``if x.attr:`` -> seed a truthy and a falsy value.
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
    """Seed container dunders so ``len(x)`` / ``k in x`` / ``x[k]`` behave and branch.

    ``len`` and ``in`` are seeded as search-mutable values so both sides of a size
    or membership guard are reachable; subscription gets a fixed mock element so
    ``x[k]`` does not raise on a bare mock.
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

    ``x.attr + 1`` on a bare mock raises ``TypeError``; seed ``0`` so the
    expression runs. Skipped when the chain already has a branch constant (which
    is itself a usable value), to avoid a redundant assignment.
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
            # e.g. `for x in resp.items()` -> make items() return a one-item list.
            out.add(f"m.{chain} = [MagicMock()]")
        elif isinstance(node.iter, ast.Name) and node.iter.id in params:
            # `for x in param` -> make the mock itself iterable with one item.
            out.add("m.__iter__.return_value = iter([MagicMock()])")


def _builtin_exc_names(node: ast.expr | None) -> set[str]:
    """Builtin exception names named by an ``except`` clause (Name or tuple of Names)."""
    if node is None:
        return set()
    elts = node.elts if isinstance(node, ast.Tuple) else [node]
    return {e.id for e in elts if isinstance(e, ast.Name) and e.id in _BUILTIN_EXCEPTIONS}


def _method_chain(func_expr: ast.expr, params: set[str], aliases: dict[str, str]) -> str | None:
    """Mock attribute chain for the callable in a call, e.g. ``param.get`` -> ``"get"``.

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
