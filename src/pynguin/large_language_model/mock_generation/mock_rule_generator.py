#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
r"""Creates heuristic base rules for the dependency analyzer.

Mines the test suites of Python projects to discover which external libraries are
mocked, producing a flat list of entries in the same schema as proxy-cache
``classify_library`` responses so the dependency analyzer can use them without LLM
calls. Two signals are mined, ``@patch`` targets such as
``@patch('urllib3.poolmanager.PoolManager')``, and mock-helper imports where
``responses`` implies ``requests``, ``moto`` implies ``boto3``, and so on.

CLI usage::

    python -m pynguin.large_language_model.mock_generation.mock_rule_generator \
        --projects ./projects/requests ./projects/httpx \
        --cache my-rules \
        --min-files 2
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import inspect
import json
import logging
import sys
import types
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from pynguin.large_language_model.mock_generation.proxy_cache_resolver import (
    require_proxy_cache_url,
)

_logger = logging.getLogger(__name__)

#: Test/mock framework names, never a real dependency to mock.
_FRAMEWORK_NAMES = frozenset({
    "unittest",
    "mock",
    "pytest",
    "hypothesis",
    "faker",
    "factory",
    "freezegun",
    "time_machine",
})

#: Directory names skipped during test-file discovery.
_EXCLUDE_DIRS = frozenset({
    "docs",
    "doc",
    "documentation",
    "examples",
    "example",
    "benchmarks",
    "benchmark",
    "build",
    "dist",
    ".git",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "vendor",
    "migrations",
})


def top_level(name: str) -> str:
    """Return the top-level package of a dotted module name."""
    return name.split(".", maxsplit=1)[0]


def _is_dotted_name(value: str) -> bool:
    """True when *value* is a dotted Python name with at least one dot (e.g. a.b.C)."""
    parts = value.split(".")
    return len(parts) >= 2 and all(part.isidentifier() for part in parts)


def _attr_to_dotted(node: ast.expr) -> str | None:
    """Return the dotted name for an attribute chain (``a.b.C``), else None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def build_import_map(source: str) -> dict[str, str]:
    """Map an imported name → the full dotted path it refers to.

    Examples::

        "from requests import Session"   → {"Session": "requests.Session"}
        "from urllib3.util import retry" → {"retry": "urllib3.util.retry"}
        "import boto3"                   → {"boto3": "boto3"}
        "import redis.client as rc"      → {"rc": "redis.client"}
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mapping[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                mapping[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return mapping


def _patch_target(call: ast.Call) -> set[str]:
    """Extract the mocked target FQN from a ``patch("a.b.C")`` call node, if any."""
    func = call.func
    is_patch = (isinstance(func, ast.Name) and func.id == "patch") or (
        isinstance(func, ast.Attribute) and func.attr == "patch"
    )
    if not (is_patch and call.args):
        return set()
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _is_dotted_name(arg.value):
        return {arg.value}
    return set()


def _spec_target(call: ast.Call, import_map: dict[str, str]) -> set[str]:
    """Extract the mocked target FQN from a ``Mock(spec=...)`` / ``MagicMock(spec=...)`` call.

    Handles two forms:
    * ``spec=redis.StrictRedis`` → ``redis.StrictRedis``
    * ``spec=MongoClient``       → resolved via *import_map* to ``pymongo.MongoClient``
    """
    func = call.func
    is_mock = (isinstance(func, ast.Name) and func.id in {"Mock", "MagicMock", "patch"}) or (
        isinstance(func, ast.Attribute) and func.attr in {"Mock", "MagicMock", "patch"}
    )
    if not is_mock:
        return set()
    for kw in call.keywords:
        if kw.arg != "spec":
            continue
        dotted = _attr_to_dotted(kw.value)
        if dotted and _is_dotted_name(dotted):
            return {dotted}
        if isinstance(kw.value, ast.Name) and kw.value.id in import_map:
            resolved = import_map[kw.value.id]
            if _is_dotted_name(resolved):
                return {resolved}
    return set()


def resolve_target(dotted: str) -> tuple[str, str]:
    """Resolve *dotted* to ``(fqn, kind)``, best-effort.

    kind is one of ``class`` / ``function`` / ``module`` / ``constant`` /
    ``unresolved``. A class (or any member of a class, e.g. a patched method)
    resolves to the class's canonical FQN with kind ``class``; other importable
    objects keep the dotted name with their kind; names whose library is not
    importable are ``unresolved``.
    """
    parts = dotted.split(".")
    module = None
    split = 0
    for i in range(len(parts) - 1, 0, -1):
        try:
            module = importlib.import_module(".".join(parts[:i]))
            split = i
            break
        except Exception:  # noqa: BLE001, S112
            continue
    if module is None:
        return dotted, "unresolved"

    obj: Any = module
    last_class: type | None = None
    for attr in parts[split:]:
        obj = getattr(obj, attr, None)
        if obj is None:
            return dotted, "unresolved"
        if isinstance(obj, type):
            last_class = obj

    if last_class is not None:  # the target is a class or a member of one
        return f"{last_class.__module__}.{last_class.__name__}", "class"
    if inspect.isroutine(obj):
        return dotted, "function"
    if isinstance(obj, types.ModuleType):
        return dotted, "module"
    return dotted, "constant"


def canonical_fqn(dotted: str) -> str:
    """Canonical FQN for *dotted* (class members resolve to their class)."""
    return resolve_target(dotted)[0]


class MockRuleGenerator:
    """Mine mock patterns from test suites and produce base entries for the dependency analyzer.

    Args:
        project_dirs: Root directories of Python projects to mine.
        min_files: Drop a library found in fewer than this many test files.
    """

    def __init__(
        self,
        project_dirs: list[Path],
        min_files: int = 1,
    ) -> None:
        """Initialize the generator."""
        self._projects = project_dirs
        self._min_files = min_files
        self._generated = False
        self.source_projects: list[str] = []

    def generate(self) -> dict[str, Any]:
        """Mine all configured projects and return class-level rule data (targets)."""
        file_hits: dict[str, set[str]] = defaultdict(set)
        self_names: set[str] = set()

        for project_dir in self._projects:
            if not project_dir.is_dir():
                _logger.warning("Project directory not found, skipping: %s", project_dir)
                continue

            project_name = project_dir.resolve().name
            self_names.add(project_name)
            test_files = self.find_test_files(project_dir)
            _logger.debug("Project '%s': found %d test file(s)", project_name, len(test_files))

            for test_file in test_files:
                try:
                    targets = self.extract_mocked_targets(test_file)
                except OSError as exc:
                    _logger.warning("Cannot read %s: %s", test_file, exc)
                    continue

                for raw in targets:
                    file_hits[raw].add(str(test_file))

        self.source_projects = sorted(self_names)

        # Resolve raw (import-path) targets to canonical class FQNs, keeping only
        # classes (and unresolvable names, best-effort): a constant/function/module
        # can never be a parameter type, so it never drives injection.
        resolved_hits: dict[str, set[str]] = defaultdict(set)
        for raw, files in file_hits.items():
            fqn, kind = resolve_target(raw)
            # handle class and classlike unresolved
            leaf = fqn.rsplit(".", 1)[-1]
            class_like = bool(leaf) and leaf[0].isupper() and not leaf.isupper()
            if kind == "class" or (kind == "unresolved" and class_like):
                resolved_hits[fqn].update(files)

        entries: list[dict[str, Any]] = []
        for target in sorted(resolved_hits):
            count = len(resolved_hits[target])
            if count < self._min_files:
                continue
            entries.append({
                "target": target,
                "decision": "mock",
                "reason": "Commonly-mocked class in source projects",
                "source": "mock-rule-generator",
                "confidence": round(count / (count + 1), 2),
            })

        self._generated = True
        return {"targets": entries}

    def find_test_files(self, project_dir: Path) -> list[Path]:
        """Return sorted list of ``test_*.py`` / ``*_test.py`` files under *project_dir*."""
        found: set[Path] = set()
        for py_file in project_dir.rglob("*.py"):
            if any(part in _EXCLUDE_DIRS for part in py_file.parts):
                continue
            name = py_file.name
            if name.startswith("test_") or name.endswith("_test.py"):
                found.add(py_file)
        return sorted(found)

    def extract_mocked_targets(self, test_file: Path) -> set[str]:
        """Return the set of mocked target FQNs (``a.b.C``) found in *test_file*.

        Combines ``@patch("a.b.C")`` targets and ``Mock(spec=...)`` specs. Framework
        (unittest/pytest/…) and standard-library targets are dropped.

        Raises:
            OSError: If the file cannot be read.
        """
        source = test_file.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(test_file))
        except SyntaxError:
            _logger.debug("Skipping unparseable file: %s", test_file)
            return set()

        import_map = build_import_map(source)
        targets: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                targets.update(_patch_target(node))
                targets.update(_spec_target(node, import_map))

        return {
            target
            for target in targets
            if top_level(target) not in _FRAMEWORK_NAMES
            and top_level(target) not in sys.stdlib_module_names
        }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mock_rule_generator",
        description=(
            "Mine test suites to discover mocked libraries and upload base rules "
            "to the proxy-cache for use by the dependency analyzer."
        ),
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        metavar="DIR",
        required=True,
        help="One or more project root directories to mine.",
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Only include a library found in at least N test files (default: 1). "
            "Raise to 2-5 for large multi-project runs to suppress one-off artifacts."
        ),
    )
    parser.add_argument(
        "--cache",
        metavar="IDENTIFIER",
        required=True,
        help=(
            "Upload generated rules to the proxy-cache under this identifier. "
            "A content hash is appended for versioning."
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def _upload_rules_to_cache(identifier: str, data: dict, source_projects: list[str]) -> None:
    """Upload *data* to the proxy-cache under *identifier-<hash>*."""
    content_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]
    versioned_id = f"{identifier}-{content_hash}"
    resp = httpx.put(
        f"{require_proxy_cache_url()}/api/v1/pynguin/rules/{versioned_id}",
        json={"rules": data, "source_projects": source_projects},
        timeout=10.0,
    )
    resp.raise_for_status()
    _logger.info("Rules uploaded to proxy-cache as '%s'", versioned_id)
    sys.stdout.write(f"Rules cached under identifier: {versioned_id}\n")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    generator = MockRuleGenerator(
        project_dirs=[Path(p) for p in args.projects],
        min_files=args.min_files,
    )
    data = generator.generate()

    _upload_rules_to_cache(args.cache, data, generator.source_projects)

    targets = data.get("targets", [])
    sys.stdout.write(f"Discovered {len(targets)} mocked class(es).\n")
    for entry in targets:
        sys.stdout.write(f"  {entry['target']}: confidence={entry['confidence']}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
