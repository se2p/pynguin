#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Align an original test with its LLM-refined version.

Matches original statements to refined ones by their (normalised) values, which yields
how the refinement renamed variables and which literal variables it inlined.
"""

import ast
import copy
import dataclasses


def expr_calls_pytest(node: ast.expr, names: frozenset[str]) -> bool:
    """Return whether ``node`` is a call to one of ``pytest.<name>``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return isinstance(func, ast.Attribute) and func.attr in names


def flatten_unconditional(stmts: list[ast.stmt]) -> list[ast.stmt]:
    """Return the statements of *stmts* that always run, in execution order.

    Statements inside ``with`` blocks run unconditionally and are included, except for
    ``pytest.raises``/``pytest.warns`` blocks, which stop at the raising call.  The
    compound statements themselves, and the bodies of ``if``/``for``/``while``/``try``
    blocks, are left out.
    """
    flat: list[ast.stmt] = []
    for stmt in stmts:
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            if not any(
                expr_calls_pytest(item.context_expr, frozenset({"raises", "warns"}))
                for item in stmt.items
            ):
                flat.extend(flatten_unconditional(stmt.body))
        elif not hasattr(stmt, "body"):
            flat.append(stmt)
    return flat


def matchable_value(stmt: ast.stmt) -> tuple[str | None, ast.expr] | None:
    """Return ``(target_name, value)`` for a statement that can anchor assertions.

    Single-name assignments yield their target; expression statements yield ``None``.
    """
    if (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
    ):
        return stmt.targets[0].id, stmt.value
    if isinstance(stmt, ast.Expr) and not isinstance(stmt.value, ast.Constant):
        return None, stmt.value
    return None


def literal_value(node: ast.expr) -> ast.expr | None:
    """Return *node* if it is a literal (e.g. ``5``, ``-1.5``, ``'a'``, ``(1, 2)``)."""
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None
    return node


def is_immutable_literal(node: ast.expr) -> bool:
    """Return whether the literal *node* evaluates to an immutable value."""
    if isinstance(node, ast.Tuple):
        return all(is_immutable_literal(elt) for elt in node.elts)
    return isinstance(node, (ast.Constant, ast.UnaryOp))


class VariableRenamer(ast.NodeTransformer):
    """Rename loaded variable names, or replace them by literal expressions."""

    def __init__(
        self, rename_map: dict[str, str], literal_map: dict[str, ast.expr] | None = None
    ) -> None:
        """Create a renamer.

        Args:
            rename_map: Maps original variable names to refined ones.
            literal_map: Maps variable names to the literal expressions replacing them.
        """
        self._rename_map = rename_map
        self._literal_map = literal_map or {}

    def visit_Name(self, node: ast.Name) -> ast.expr:  # noqa: N802
        """Rename or replace a loaded name.

        Args:
            node: The name node.

        Returns:
            The renamed name, the substituted literal, or the unchanged node.
        """
        if isinstance(node.ctx, ast.Load):
            if node.id in self._rename_map:
                return ast.copy_location(ast.Name(id=self._rename_map[node.id], ctx=node.ctx), node)
            if node.id in self._literal_map:
                return ast.copy_location(copy.deepcopy(self._literal_map[node.id]), node)
        return node


def normalise_expression(
    node: ast.expr, rename_map: dict[str, str], literal_map: dict[str, ast.expr]
) -> str:
    """Unparse *node* after applying renames and inlining literal variables."""
    return ast.unparse(VariableRenamer(rename_map, literal_map).visit(copy.deepcopy(node)))


@dataclasses.dataclass
class StatementAlignment:
    """How an original test function lines up with its refined version."""

    rename_map: dict[str, str] = dataclasses.field(default_factory=dict)
    # Original variables holding literals that the refined test inlined.
    literal_map: dict[str, ast.expr] = dataclasses.field(default_factory=dict)
    # Original statement -> matched refined statement.
    anchors: dict[int, ast.stmt] = dataclasses.field(default_factory=dict)
    # Original variable -> refined expression statement that dropped its result.
    unbound: dict[str, ast.Expr] = dataclasses.field(default_factory=dict)


def align_statements(orig_stmts: list[ast.stmt], ref_stmts: list[ast.stmt]) -> StatementAlignment:
    """Match the original statements to refined ones by their (normalised) values.

    Original variables are renamed to the refined ones as they are matched, so that
    chained statements such as ``foo_0 = module_0.Foo(int_0)`` match
    ``foo = module_0.Foo(value)``.  Unmatched variables holding literals are inlined,
    so that ``int_0 = 5; foo_0 = Foo(int_0)`` matches ``foo = Foo(5)``.  An assignment
    may match a refined expression statement that dropped the unused result.
    """
    alignment = StatementAlignment()
    ref_values = [matchable_value(stmt) for stmt in ref_stmts]
    ref_keys = [ast.unparse(value[1]) if value else None for value in ref_values]
    used: set[int] = set()
    last = -1

    for orig_stmt in orig_stmts:
        orig_value = matchable_value(orig_stmt)
        if orig_value is None:
            continue
        orig_var, value = orig_value
        key = normalise_expression(value, alignment.rename_map, alignment.literal_map)
        candidates = [idx for idx, ref_key in enumerate(ref_keys) if ref_key == key]
        # Prefer the first match after the previous one, to keep the statement order.
        match = next(
            (idx for idx in candidates if idx > last and idx not in used),
            next((idx for idx in candidates if idx not in used), None),
        )
        if match is None:
            if orig_var is not None:
                literal = literal_value(ast.parse(key, mode="eval").body)
                if literal is not None:
                    alignment.literal_map[orig_var] = literal
            continue
        used.add(match)
        last = max(last, match)
        ref_stmt = ref_stmts[match]
        alignment.anchors[id(orig_stmt)] = ref_stmt
        ref_var = ref_values[match][0]  # type: ignore[index]
        if orig_var is None:
            continue
        if ref_var is not None:
            alignment.rename_map[orig_var] = ref_var
        elif isinstance(ref_stmt, ast.Expr):
            alignment.unbound[orig_var] = ref_stmt
    return alignment


def find_test_function(tree: ast.Module) -> ast.FunctionDef | None:
    """Return the test function of *tree*, skipping helper functions.

    Prefers the first function whose name starts with ``test``; falls back to the last
    top-level function, since helpers are usually defined before the test.
    """
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    return next((f for f in funcs if f.name.startswith("test")), funcs[-1] if funcs else None)
