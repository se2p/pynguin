#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Generates return-value hints for mocked parameters.

A bare ``MagicMock`` lets a function run past a boundary call, but branches that
depend on the value the boundary returns stay uncovered. For each function this
module finds the parameters that will be mocked, whether by their type annotation
or by the attributes accessed on an untyped parameter, reads how their return
values are used, asks the proxy-cache for concrete setup lines, and builds
:class:`MockTemplate` hints keyed by the class FQN.
"""

from __future__ import annotations

import ast
import logging
from typing import TYPE_CHECKING

from pynguin.mock_generation import llm_classifier_client
from pynguin.mock_generation.ast_helpers import import_alias_map, param_names
from pynguin.mock_generation.mock_generator import MockTemplate
from pynguin.mock_generation.mock_rule_generator import (
    canonical_fqn,
)
from pynguin.mock_generation.untyped_param_analyzer import (
    _direct_attr_accesses,
    match_candidate_classes,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_logger = logging.getLogger(__name__)


def _annotation_fqns(node: ast.expr | None, alias_map: dict[str, str]) -> list[str]:
    """Candidate FQNs an annotation could denote, unwrapping ``X | Y`` / ``Optional``."""
    if node is None:
        return []
    out: list[str] = []
    if isinstance(node, ast.Name):
        out.append(alias_map.get(node.id, node.id))
    elif isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.expr = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(alias_map.get(cur.id, cur.id))
            out.append(".".join(reversed(parts)))
    elif isinstance(node, ast.Subscript):
        out += _annotation_fqns(node.value, alias_map)
        sl = node.slice
        elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
        for elt in elts:
            out += _annotation_fqns(elt, alias_map)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        out += _annotation_fqns(node.left, alias_map)
        out += _annotation_fqns(node.right, alias_map)
    return out


def mocked_params(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    alias_map: dict[str, str],
    mock_targets: set[str],
    candidate_classes: list[type],
    untyped_bindings: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map parameter name to mock-target FQN for the params this function mocks."""
    result: dict[str, str] = {}

    for arg in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs):
        for fqn in _annotation_fqns(arg.annotation, alias_map):
            canonical = canonical_fqn(fqn)
            if canonical in mock_targets:
                result[arg.arg] = canonical
                break

    _resolve_untyped_params(
        func,
        result,
        mock_targets,
        candidate_classes,
        untyped_bindings,
    )

    return result


def _resolve_untyped_params(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    result: dict[str, str],
    mock_targets: set[str],
    candidate_classes: list[type],
    untyped_bindings: dict[str, str] | None,
) -> None:
    """Populate *result* with mocked untyped parameters.

    When *untyped_bindings* is provided (even empty), it is authoritative and the
    weak attribute matcher is skipped, so we mock exactly what the injector binds.
    """
    if untyped_bindings is not None:
        for param, fqn in untyped_bindings.items():
            if param not in result and fqn in mock_targets:
                result[param] = fqn
        return

    untyped = param_names(func, untyped_only=True) - result.keys()
    if not (untyped and candidate_classes):
        return

    accesses = _direct_attr_accesses(func, untyped)
    for name, attrs in accesses.items():
        for fqn in match_candidate_classes([attrs], candidate_classes):
            if fqn in mock_targets:
                result[name] = fqn
                break


def iter_named_functions(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Yield ``(qualname, funcdef)`` for module-level functions and class methods.

    Qualnames use ``__qualname__``-style keys so they match the injector's
    bindings for method and constructor boundaries, not just top-level functions.
    """
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef):
                    yield f"{node.name}.{sub.name}", sub


def generate_templates(  # noqa: PLR0914
    module_path: Path,
    mock_targets: set[str],
    candidate_classes: list[type] | None = None,
    module_name: str = "",
    untyped_bindings: dict[tuple[str, str], str] | None = None,
) -> dict[str, MockTemplate]:
    """Return return-value hint templates keyed by target FQN (needs the proxy-cache).

    For each function that mocks a parameter, the proxy-cache produces concrete
    return-value setup lines, gathered into one :class:`MockTemplate` per mocked
    class. *untyped_bindings* selects which untyped params to hint.
    """
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    alias_map = import_alias_map(tree)
    candidates = candidate_classes or []
    templates: dict[str, MockTemplate] = {}

    # Index untyped bindings by callable key so each function hints only its params
    bindings_by_func: dict[str, dict[str, str]] = {}
    for (callable_key, param), fqn in (untyped_bindings or {}).items():
        bindings_by_func.setdefault(callable_key, {})[param] = fqn

    injector_mode = untyped_bindings is not None
    for qualname, func in iter_named_functions(tree):
        func_key = f"{module_name}.{qualname}" if module_name else qualname
        per_func = bindings_by_func.get(func_key, {}) if injector_mode else None
        params = mocked_params(func, alias_map, mock_targets, candidates, per_func)
        if not params:
            continue
        # Tell the LLM which attributes each param uses and the values it branches on
        accesses = _direct_attr_accesses(func, set(params))
        deps = [
            {
                "name": name,
                "mock_target": fqn,
                "reason": "boundary",
                "accessed_attributes": sorted(accesses.get(name, set())),
            }
            for name, fqn in params.items()
        ]
        branch_constants = _branch_constants(func)
        usage_context = _usage_context(params, accesses, branch_constants)
        # func_key (module.qualname) is the proxy-cache key, unique per module and method
        try:
            response = llm_classifier_client.generate_mock_config(
                func_key,
                ast.get_source_segment(source, func) or "",
                deps,
                usage_context,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Hint generation failed for %s: %s", func_key, exc)
            continue
        _merge(templates, response, params, branch_constants)

    total = sum(len(t.setup_lines) + len(t.mutable_setups) for t in templates.values())
    _logger.info("Return-value hints: %d setup(s) across %d target(s)", total, len(templates))
    return templates


def _usage_context(
    params: dict[str, str],
    accesses: dict[str, set[str]],
    branch_constants: dict[type, list],
) -> str:
    """Usage facts for the LLM prompt to provide context for the right return values."""
    parts: list[str] = []
    for name in params:
        attrs = sorted(accesses.get(name, set()))
        parts.append(
            f"parameter '{name}' is accessed as: {', '.join(attrs)}"
            if attrs
            else f"parameter '{name}' has no statically observed attribute access"
        )
    values = [repr(v) for vals in branch_constants.values() for v in vals]
    if values:
        parts.append(
            "the function branches on these literal values (use them as return "
            f"values so each branch is reachable): {', '.join(values)}"
        )
    return "; ".join(parts)


def _branch_constants(func: ast.AST) -> dict[type, list]:
    """Constants a function compares against, grouped by type.

    These seed the mutable return values so the search can drive each branch.
    """
    out: dict[type, list] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Compare):
            continue
        for operand in (node.left, *node.comparators):
            if isinstance(operand, ast.Constant) and isinstance(operand.value, int | str):
                bucket = out.setdefault(type(operand.value), [])
                if operand.value not in bucket:
                    bucket.append(operand.value)
    return out


def _split_setup_line(line: str) -> tuple[str, object] | None:
    """Parse ``<root>.<chain> = <const>`` into (chain, value) for primitive consts."""
    try:
        assign = ast.parse(line.strip()).body[0]
    except (SyntaxError, ValueError, IndexError):
        return None
    if not isinstance(assign, ast.Assign) or not isinstance(assign.value, ast.Constant):
        return None
    target = assign.targets[0]
    if not isinstance(target, ast.Attribute):
        return None
    chain: list[str] = []
    node: ast.expr = target
    while isinstance(node, ast.Attribute):
        chain.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join(reversed(chain)), assign.value.value


def _merge(
    templates: dict[str, MockTemplate],
    response: dict,
    params: dict[str, str],
    branch_constants: dict[type, list] | None = None,
) -> None:
    """Fold a /generate-mock response into *templates*, keyed by mocked target FQN.

    The proxy-cache may echo a different ``mock_target`` than the canonical FQN, so
    map each returned mock to a target via the dependency name we sent, falling
    back to the echoed target, then to the sole mocked target of the function.
    Setup lines with a primitive constant become mutable setups seeded with the
    function's branch constants.
    """
    constants = branch_constants or {}
    wanted = set(params.values())
    sole = next(iter(wanted)) if len(wanted) == 1 else None
    for mock in response.get("mocks", []):
        lines = [
            m["return_value_setup"]
            for m in mock.get("methods", [])
            if isinstance(m, dict) and m.get("return_value_setup")
        ]
        if not lines:
            continue
        echoed = mock.get("mock_target")
        target = (
            params.get(mock.get("dependency", "")) or (echoed if echoed in wanted else None) or sole
        )
        if target is None:
            continue
        template = templates.get(target)
        if template is None:
            template = MockTemplate(
                dependency=mock.get("dependency", ""),
                import_path=target.split(".", 1)[0],
                mock_target=target,
            )
            templates[target] = template
        _add_setups(template, lines, constants)


def _add_setups(template: MockTemplate, lines: list[str], constants: dict[type, list]) -> None:
    """Add setup lines to *template*, making primitive-valued ones mutable."""
    from pynguin.mock_generation.mock_generator import (  # noqa: PLC0415
        MutableSetup,
    )

    existing = {ms.target for ms in template.mutable_setups}
    for line in lines:
        parsed = _split_setup_line(line)
        if parsed is None:
            if line not in template.setup_lines:
                template.setup_lines.append(line)
            continue
        chain, value = parsed
        if chain in existing:
            continue
        # Candidate values from _branch_constants plus the proxy-cache suggestion
        pool = [value]
        for extra in constants.get(type(value), []):
            if extra not in pool:
                pool.append(extra)
        template.mutable_setups.append(MutableSetup(target=chain, candidates=pool))
        existing.add(chain)
