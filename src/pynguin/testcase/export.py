#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Writes generated test suites to pytest files."""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import importlib
import logging
import re
import sys
import threading
import types
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

import libcst as cst

from pynguin.assertion.assertion import FloatAssertion, IsInstanceAssertion
from pynguin.assertion.assertion_to_ast import assertion_to_cst
from pynguin.testcase.execution import OutputSuppressionContext, suppress_logging
from pynguin.utils.cst_imports import RelativeImportNormalizer, dotted_chain, imported_local_names
from pynguin.utils.exceptions import TracingAbortedException
from pynguin.utils.fs_isolation import FilesystemIsolation
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
from pynguin.utils.naming import canonical_module_name, get_module_alias, get_package_anchor
from pynguin.utils.orderedset import OrderedSet

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from pynguin.ga.testsuitechromosome import TestSuiteChromosome
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.testcase.testcase import Statement, TestCase

_LOGGER = logging.getLogger(__name__)

# Wall-clock limit for re-executing a single statement during export.  Without
# it a generated statement containing an unbounded loop hangs the whole run.
_STATEMENT_EXECUTION_TIMEOUT: float = 5.0


def _exec_statement_guarded(
    code_str: str,
    namespace: dict,
    tracer: object | None,
) -> tuple[bool, type[BaseException] | None]:
    """Execute one rendered statement in a watchdog thread.

    The statement runs with output suppression and filesystem isolation.  All
    ``BaseException``s are captured — including ``SystemExit``, which SUTs like
    setuptools commands raise routinely and which must not escape and abort the
    export of the entire suite.

    Args:
        code_str: The rendered source of the statement.
        namespace: The namespace shared by the test case's statements.
        tracer: Optional instrumentation tracer to disable during execution.

    Returns:
        A tuple ``(finished, exception_type)``: *finished* is False when the
        watchdog timeout expired; *exception_type* is the type of the raised
        exception, or ``None`` if the statement executed without error.
    """
    outcome: list[type[BaseException] | None] = [None]
    aborted = [False]

    def _target() -> None:
        try:
            with (
                OutputSuppressionContext(),
                suppress_logging(),
                FilesystemIsolation(),
            ):
                if tracer is not None:
                    # Rebind the tracer's thread-identity guard to this watchdog thread
                    # and suppress trace recording so instrumented SUT code does not raise
                    # a spurious ``TracingAbortedException``.
                    with tracer, tracer.temporarily_disable():  # type: ignore[attr-defined]
                        exec(compile(code_str, "<stmt>", "exec"), namespace)  # noqa: S102
                else:
                    exec(compile(code_str, "<stmt>", "exec"), namespace)  # noqa: S102
        except TracingAbortedException:
            # Pynguin-internal thread-identity control signal raised by instrumented
            # SUT code running on this watchdog thread — never a real SUT exception.
            # Once it fires the namespace is left partially populated, so exception
            # detection is unreliable from here on; treat the pass as inconclusive
            # rather than misrecording it as the statement's exception.
            aborted[0] = True
        except BaseException as exc:  # noqa: BLE001
            outcome[0] = type(exc)

    thread = threading.Thread(target=_target, daemon=True)
    # Suppress logging from the *parent* thread rather than inside ``_target``.
    # ``suppress_logging`` flips the process-global ``logging.disable`` switch, so
    # if the watchdog times out and its daemon thread leaks while still inside the
    # context, the restoring ``finally`` never runs and logging stays disabled for
    # the rest of the process, which breaks every later test (and real run)
    # that expects log output. Owning the suppression here guarantees the restore
    # runs even when the thread is abandoned, and still covers the exec window.
    with suppress_logging():
        thread.start()
        thread.join(_STATEMENT_EXECUTION_TIMEOUT)
    if thread.is_alive() or aborted[0]:
        # Either the watchdog timeout expired or tracing aborted the re-execution;
        # in both cases the namespace state is unknown, so detection is inconclusive.
        return False, None
    return True, outcome[0]


_LICENSE_HEADER = """\
#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
#  This file was automatically generated using Pynguin.
"""

_COVERAGE_BY_IMPORT_COMMENT = "# Importing this module achieves coverage.\n"


class _PytestReferenceVisitor(cst.CSTVisitor):
    """Detects whether a CST node contains any reference to the identifier 'pytest'."""

    def __init__(self) -> None:
        self.has_pytest = False

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        if node.value == "pytest":
            self.has_pytest = True


def _xfail_decorator() -> cst.Decorator:
    """Build the ``@pytest.mark.xfail(strict=True)`` decorator node.

    Returns:
        The CST decorator node.
    """
    return cst.Decorator(
        decorator=cst.Call(
            func=cst.Attribute(
                value=cst.Attribute(value=cst.Name("pytest"), attr=cst.Name("mark")),
                attr=cst.Name("xfail"),
            ),
            args=[
                cst.Arg(
                    keyword=cst.Name("strict"),
                    value=cst.Name("True"),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            ],
        )
    )


class _ReferencedNameCollector(cst.CSTVisitor):
    """Collects every bare name a CST node references.

    Attribute members (``bar`` in ``foo.bar``) and call keywords (``x`` in
    ``f(x=1)``) are member or parameter names, not references, and are skipped,
    as are import statements, which bind names rather than read them.
    The result over-approximates the names a test reads (assignment targets are
    included), which is safe: it only decides which SUT names get imported.
    """

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        self.names.add(node.value)

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        node.value.visit(self)
        return False

    def visit_Arg(self, node: cst.Arg) -> bool:  # noqa: N802
        node.value.visit(self)
        return False

    def visit_Import(self, node: cst.Import) -> bool:  # noqa: N802
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:  # noqa: N802
        return False


def _referenced_names(nodes: Sequence[cst.CSTNode]) -> set[str]:
    """Collect the bare names referenced by the given CST nodes.

    Args:
        nodes: The nodes to inspect.

    Returns:
        The set of referenced names.
    """
    collector = _ReferencedNameCollector()
    for node in nodes:
        node.visit(collector)
    return collector.names


def _test_case_referenced_names(
    tc: TestCase,
    module_aliases: dict[str, str] | None = None,
) -> set[str]:
    """Collect the bare names a test case references once it is rendered.

    This covers the statements and the assertions rendered after them. A test
    case without statements (a seed holding raw code) is parsed from its code.

    Args:
        tc: The test case to inspect.
        module_aliases: Optional mapping from module names to their aliases, as
            used when rendering the assertions.

    Returns:
        The set of referenced names.
    """
    nodes: list[cst.CSTNode] = []
    for stmt in tc.statements():
        nodes.append(stmt.node)
        for assertion in stmt.assertions:
            cst_node = assertion_to_cst(assertion, module_aliases=module_aliases)
            if cst_node is not None:
                nodes.append(cst_node)
    if not nodes:
        with contextlib.suppress(Exception):
            nodes.extend(cst.parse_module(tc.to_code()).body)
    return _referenced_names(nodes)


def _public_sut_names(module: object, module_alias: str) -> list[str]:
    """Return the SUT module's public names, sorted.

    These are the candidates for the ``from <module> import <names>`` line of the
    rendered test file (see ``_build_sut_import_statements``). Underscore-prefixed
    names and the module alias are excluded so the alias binding is never shadowed.

    Args:
        module: The imported SUT module.
        module_alias: The alias the SUT module is imported under.

    Returns:
        The sorted list of public names.
    """
    return sorted(name for name in dir(module) if not name.startswith("_") and name != module_alias)


def _direct_module_import(
    name: str, value: object, sut_packages: frozenset[str] = frozenset()
) -> str | None:
    """Return a direct import binding *name* to the module *value*, if possible.

    A module the SUT merely imported (``os``, ``datetime``) should be imported
    by the test file itself rather than through the SUT, so the tests do not
    depend on the SUT's own imports.

    Modules of the SUT's own top-level package are excluded: their runtime
    ``__name__`` may differ from the canonical name the test file imports the SUT
    under (e.g. ``src.pkg.helper`` for a SUT emitted as ``pkg.mod``), so importing
    them by ``__name__`` could fail or load a second copy. They stay imported
    through the SUT.

    Args:
        name: The name the SUT binds the module to.
        value: The object bound to *name* in the SUT.
        sut_packages: The top-level package names of the SUT, both as
            configured and as canonically emitted.

    Returns:
        The import source, or ``None`` if *value* is not a module that can be
        imported directly by its own name.
    """
    if not isinstance(value, types.ModuleType):
        return None
    real_name = value.__name__
    if real_name.split(".", 1)[0] in sut_packages:
        return None
    if sys.modules.get(real_name) is not value:
        return None
    if real_name == name:
        return f"import {name}\n"
    return f"import {real_name} as {name}\n"


def _build_sut_import_statements(
    module_name: str,
    project_path: str | None = None,
    used_names: set[str] | None = None,
) -> list[cst.SimpleStatementLine]:
    """Build the CST import statements for the SUT.

    These statements are emitted at the top of the generated test file and also
    executed into the namespace of the dry-run statement execution so that both
    execution environments are identical and cannot drift.

    Only the SUT's public names that the tests reference are imported. Names that
    are bound to modules (e.g. ``os`` when the SUT does ``import os``) are imported
    directly instead of through the SUT.

    Args:
        module_name: The name of the module under test.
        project_path: Optional path prepended to ``sys.path``.
        used_names: The names referenced by the tests; ``None`` imports every
            public name of the SUT.

    Returns:
        A list of CST import statements for the SUT.
    """
    effective_path = project_path if project_path is not None else ""
    if effective_path and effective_path not in sys.path:
        sys.path.insert(0, effective_path)

    canonical_name = canonical_module_name(module_name)
    module_alias = get_module_alias(module_name)
    sut_packages = frozenset({
        module_name.split(".", 1)[0],
        canonical_name.split(".", 1)[0],
    })
    module_imports: list[str] = []
    from_names: list[str] = []
    try:
        sut_mod = importlib.import_module(module_name)
        public_names = _public_sut_names(sut_mod, module_alias)
    except Exception:  # noqa: BLE001
        sut_mod = None
        public_names = []
    for name in public_names:
        if used_names is not None and name not in used_names:
            continue
        value = getattr(sut_mod, name, None)
        if name == "sys" and value is sys:
            # Already bound by the header's ``import sys``.
            continue
        direct_import = _direct_module_import(name, value, sut_packages)
        if direct_import is not None:
            module_imports.append(direct_import)
        else:
            from_names.append(name)

    stmts: list[cst.SimpleStatementLine] = [
        cast("cst.SimpleStatementLine", cst.parse_statement("import sys\n")),
        cast("cst.SimpleStatementLine", cst.parse_statement(f"import {canonical_name}\n")),
        cast(
            "cst.SimpleStatementLine",
            cst.parse_statement(f"{module_alias} = sys.modules['{canonical_name}']\n"),
        ),
    ]
    stmts.extend(
        cast("cst.SimpleStatementLine", cst.parse_statement(source)) for source in module_imports
    )
    if from_names:
        names_str = ", ".join(from_names)
        stmts.append(
            cast(
                "cst.SimpleStatementLine",
                cst.parse_statement(f"from {canonical_name} import {names_str}\n"),
            )
        )
    return stmts


def _is_sut_import(node: cst.Import | cst.ImportFrom, sut_modules: set[str]) -> bool:
    """Check whether an import statement imports the SUT module or a submodule thereof."""
    if isinstance(node, cst.Import):
        for alias in node.names:
            chain = dotted_chain(alias.name)
            if chain:
                name = ".".join(chain)
                if name in sut_modules or any(name.startswith(s + ".") for s in sut_modules):
                    return True
    elif isinstance(node, cst.ImportFrom) and node.module is not None:
        chain = dotted_chain(node.module)
        if chain:
            name = ".".join(chain)
            if name in sut_modules or any(name.startswith(s + ".") for s in sut_modules):
                return True
    return False


# Builtin names. A hoisted external import binding one of them (``from math import
# pow``) would shadow the builtin for every test in the file, not just the one that
# imported it, so such names are never hoisted.
_BUILTIN_NAMES = frozenset(dir(builtins))

# Prefix of the private names the writer's seed patch binds at module level.
_WRITER_PRIVATE_PREFIX = "_pynguin_"


def _bound_names_of(stmts: Sequence[cst.CSTNode]) -> set[str]:
    """Collect the module-level names bound by import and assignment statements.

    Args:
        stmts: The statements to inspect.

    Returns:
        The set of bound names.
    """
    names: set[str] = set()
    for stmt in stmts:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.Import | cst.ImportFrom):
                names.update(imported_local_names(small))
            elif isinstance(small, cst.Assign):
                names.update(
                    target.target.value
                    for target in small.targets
                    if isinstance(target.target, cst.Name)
                )
    return names


def _split_import_aliases(
    parsed: cst.SimpleStatementLine,
    sut_modules: set[str],
    rel_normalizer: RelativeImportNormalizer | None,
) -> list[cst.Import | cst.ImportFrom]:
    """Split an import line into one non-SUT import node per imported name.

    Star imports are dropped, since the names they bind cannot be known.

    Args:
        parsed: The parsed import line.
        sut_modules: The names of the module under test.
        rel_normalizer: Optional normalizer for relative imports.

    Returns:
        One single-name import node per kept alias.
    """
    if rel_normalizer is not None:
        norm_node = parsed.visit(rel_normalizer)
        assert isinstance(norm_node, cst.SimpleStatementLine)
        parsed = norm_node

    result: list[cst.Import | cst.ImportFrom] = []
    for small in parsed.body:
        if not isinstance(small, cst.Import | cst.ImportFrom):
            continue
        if isinstance(small.names, cst.ImportStar) or _is_sut_import(small, sut_modules):
            continue
        result.extend(
            small.with_changes(names=[alias.with_changes(comma=cst.MaybeSentinel.DEFAULT)])
            for alias in small.names
        )
    return result


class _ExternalImport(NamedTuple):
    """A single-name external import hoisted to module level."""

    line: cst.SimpleStatementLine
    """The import statement."""

    name: str
    """The name the import binds."""

    value: object
    """The object the import binds the name to."""


def _execute_import(code: str, name: str, tracer: object | None) -> tuple[bool, object]:
    """Execute the import statement *code* like the dry run executes a statement.

    The import runs under the same guards as the dry run (watchdog timeout, output
    suppression, filesystem isolation, disabled tracing, and every
    ``BaseException`` caught), so an import that hangs or calls ``sys.exit()``
    cannot abort the export.

    Args:
        code: The import statement.
        name: The name the import binds.
        tracer: Optional instrumentation tracer to disable during execution.

    Returns:
        Whether the import succeeded, and the object it bound *name* to.
    """
    namespace: dict = {}
    finished, exc_type = _exec_statement_guarded(code, namespace, tracer)
    if not finished or exc_type is not None or name not in namespace:
        _LOGGER.debug("Skipping invalid external import %s: %s", code, exc_type or "timeout")
        return False, None
    return True, namespace[name]


def _plain_import_roots(
    stmts: Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement],
) -> set[str]:
    """Collect the root names bound by plain ``import a.b`` statements.

    Plain ``import a.b`` / ``import a.c`` both bind ``a`` and may coexist.

    Args:
        stmts: The statements to inspect.

    Returns:
        The set of root names.
    """
    return {
        name
        for stmt in stmts
        if isinstance(stmt, cst.SimpleStatementLine)
        for small in stmt.body
        if isinstance(small, cst.Import)
        for alias in small.names
        if alias.asname is None
        for name in imported_local_names(small.with_changes(names=[alias]))
    }


def _parse_external_import_statements(
    import_sources: Iterable[str],
    module_name: str,
    *,
    used_names: set[str],
    sut_import_stmts: Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement],
    taken_names: set[str],
    tracer: object | None = None,
) -> list[_ExternalImport]:
    """Select the external imports the rendered tests need at module level.

    An imported name is kept only if the rendered tests read it, it is not already
    bound by the SUT imports, the writer itself (*taken_names*) or as a builtin, and
    no earlier source already bound it (so the first source wins). Imports of the
    module under test, star imports and imports that fail to execute are dropped.

    Args:
        import_sources: Import statement code strings, highest priority first.
        module_name: Name of the module under test.
        used_names: The names the rendered tests read.
        sut_import_stmts: The SUT import statements of the rendered file.
        taken_names: Further module-level names the writer binds, which an external
            import must not rebind.
        tracer: Optional instrumentation tracer to disable while executing imports.

    Returns:
        List of unique, normalized single-name imports.
    """
    sut_modules = {module_name, canonical_module_name(module_name)}
    anchor = get_package_anchor(module_name)
    rel_normalizer = RelativeImportNormalizer(anchor) if anchor else None

    bound: set[str] = _bound_names_of(sut_import_stmts) | taken_names
    plain_roots = _plain_import_roots(sut_import_stmts)
    seen: set[str] = set()
    result: list[_ExternalImport] = []

    for raw_src in import_sources:
        src = raw_src.strip()
        if not src:
            continue
        try:
            parsed = cst.parse_statement(src)
        except cst.ParserSyntaxError:
            continue
        if not isinstance(parsed, cst.SimpleStatementLine):
            continue

        for node in _split_import_aliases(parsed, sut_modules, rel_normalizer):
            (name,) = imported_local_names(node)
            is_plain = (
                isinstance(node, cst.Import)
                and cast("cst.ImportAlias", cast("Sequence", node.names)[0]).asname is None
            )
            if (
                name not in used_names
                or name in _BUILTIN_NAMES
                or name.startswith(_WRITER_PRIVATE_PREFIX)
                or (name in bound and not (is_plain and name in plain_roots))
            ):
                continue
            line = cst.SimpleStatementLine(body=[node])
            code_str = cst.Module(body=[line]).code.strip()
            if code_str in seen:
                continue
            ok, value = _execute_import(code_str, name, tracer)
            if not ok:
                continue
            seen.add(code_str)
            bound.add(name)
            if is_plain:
                plain_roots.add(name)
            result.append(_ExternalImport(line, name, value))

    return result


def _exception_name(exc_type: type[BaseException], external_bindings: Mapping[str, object]) -> str:
    """The name under which ``pytest.raises(...)`` references an exception type.

    Exception types are imported by their bare name, unless a hoisted external
    import already binds that name to another object; then the exception type is
    imported under a module-qualified alias, so neither binding replaces the other.

    Args:
        exc_type: The exception type.
        external_bindings: The objects the hoisted external imports bind, by name.

    Returns:
        The name to reference the exception type by.
    """
    name = exc_type.__name__
    if exc_type.__module__ == "builtins" or external_bindings.get(name, exc_type) is exc_type:
        return name
    return f"{exc_type.__module__.replace('.', '_')}_{name}"


def _is_expected_exception(stmt: Statement, exc_type: type[BaseException]) -> bool:
    """Check whether ``exc_type`` is declared as expected by the statement's callable.

    Args:
        stmt: The statement that raised ``exc_type``.
        exc_type: The exception type raised while re-executing the statement.

    Returns:
        True if the statement's accessible object declares ``exc_type`` (by name)
        among its expected exceptions.
    """
    acc = stmt.accessible
    return (
        isinstance(acc, GenericCallableAccessibleObject)
        and exc_type.__name__ in acc.expected_exceptions
    )


def _is_executable_cst_statement(
    stmt: cst.CSTNode,
) -> bool:
    """Check whether a CST statement is executable.

    Pass statements, string literal expressions (such as docstrings), ellipsis
    expressions, imports, and ``global``/``nonlocal`` declarations are considered
    non-executable: a test body made only of them exercises no SUT code.

    Args:
        stmt: The CST statement to check.

    Returns:
        True if the statement is executable.
    """
    if isinstance(stmt, cst.BaseCompoundStatement):
        return True
    if isinstance(stmt, (cst.Pass, cst.Import, cst.ImportFrom, cst.Global, cst.Nonlocal)):
        return False
    if isinstance(stmt, cst.Expr):
        return not isinstance(stmt.value, (cst.SimpleString, cst.FormattedString, cst.Ellipsis))
    if isinstance(stmt, cst.SimpleStatementLine):
        return any(_is_executable_cst_statement(small) for small in stmt.body)
    return True


def _has_executable_cst_statements(
    body: Sequence[cst.CSTNode],
) -> bool:
    """Check whether a sequence of CST statements contains any executable statements.

    Args:
        body: The sequence of CST statements to check.

    Returns:
        True if at least one statement is executable.
    """
    return any(_is_executable_cst_statement(stmt) for stmt in body)


def _uses_coroutines(tc: TestCase) -> bool:
    """Whether the test case calls a coroutine, which its rendering runs via asyncio."""
    return any(
        isinstance(stmt.accessible, GenericCallableAccessibleObject)
        and stmt.accessible.is_coroutine
        for stmt in tc.statements()
    )


def _uses_mocks(tc: TestCase) -> bool:
    """Whether the test case uses mocks, whose rendering references ``MagicMock``."""
    return any(stmt.mock_info is not None for stmt in tc.statements())


def _setup_dry_run_namespace(
    sut_import_stmts: Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement],
    *,
    external_import_stmts: (
        Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement] | None
    ) = None,
    module_aliases: dict[str, str] | None = None,
    needs_asyncio: bool = False,
    needs_magicmock: bool = False,
) -> dict:
    import pytest  # noqa: PLC0415

    # Bind exactly what the rendered file binds: ``asyncio`` and ``MagicMock`` are
    # only imported there on demand, so a test reading them otherwise must fail here.
    namespace: dict = {
        "__builtins__": __builtins__,
        "pytest": pytest,
    }
    if needs_asyncio:
        namespace["asyncio"] = asyncio
    # Mirror the rendered test's SUT imports and definitions so dry-run re-execution
    # and test execution after export use the exact same namespace bindings.
    for stmt_node in sut_import_stmts:
        with contextlib.suppress(Exception):
            exec(cst.Module(body=[stmt_node]).code, namespace)  # noqa: S102

    if external_import_stmts:
        for stmt_node in external_import_stmts:
            with contextlib.suppress(Exception):
                exec(cst.Module(body=[stmt_node]).code, namespace)  # noqa: S102

    if needs_magicmock:
        with contextlib.suppress(Exception):
            from unittest.mock import MagicMock  # noqa: PLC0415

            namespace["MagicMock"] = MagicMock

    if module_aliases:
        for mod, alias in module_aliases.items():
            if alias not in namespace:
                with contextlib.suppress(Exception):
                    namespace[alias] = sys.modules.get(mod) or importlib.import_module(mod)

    return namespace


class TestSuiteWriter:
    """Writes a suite of test cases as a single pytest-compatible Python file."""

    def __init__(self, *, filesystem_isolation: bool = True, no_xfail: bool = False) -> None:
        """Initializes the test suite writer.

        Args:
            filesystem_isolation: Whether to use filesystem isolation during execution.
            no_xfail: If True, unexpected exceptions are wrapped with
                ``pytest.raises(...)`` instead of marking the whole test with
                ``@pytest.mark.xfail(strict=True)``.
        """
        self._filesystem_isolation = filesystem_isolation
        self._no_xfail = no_xfail

    def _per_statement_exceptions(
        self,
        tc: TestCase,
        module_name: str,
        project_path: str | None,
        subject_properties: SubjectProperties | None = None,
        *,
        module_aliases: dict[str, str] | None = None,
        sut_import_stmts: (
            Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement] | None
        ) = None,
        external_import_stmts: (
            Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement] | None
        ) = None,
        needs_asyncio: bool | None = None,
        needs_magicmock: bool | None = None,
    ) -> list[type[BaseException] | None]:
        """Execute each statement individually; return per-statement exception types.

        Args:
            tc: The test case whose statements are executed.
            module_name: The module under test.
            project_path: Optional path prepended to ``sys.path``.
            subject_properties: Optional subject properties used to disable tracing.
            module_aliases: Optional mapping from module names to their assigned aliases
                in the generated test suite.
            sut_import_stmts: Optional pre-built CST import statements for the SUT.
            external_import_stmts: Optional pre-built CST import statements for external modules.
            needs_asyncio: Whether the rendered file imports ``asyncio``; defaults to
                whether this test case awaits a coroutine.
            needs_magicmock: Whether the rendered file imports ``MagicMock``; defaults
                to whether this test case uses mocks.

        Returns:
            A list with one entry per statement: the exception type raised by that
            statement, or ``None`` if it executed without error.
        """
        effective_path = project_path if project_path is not None else ""
        if effective_path and effective_path not in sys.path:
            sys.path.insert(0, effective_path)

        try:
            importlib.import_module(module_name)
        except Exception:  # noqa: BLE001
            return [None] * tc.size()

        if sut_import_stmts is None:
            sut_import_stmts = _build_sut_import_statements(
                module_name,
                project_path,
                _test_case_referenced_names(tc, module_aliases),
            )
        namespace = _setup_dry_run_namespace(
            sut_import_stmts,
            external_import_stmts=external_import_stmts,
            module_aliases=module_aliases,
            needs_asyncio=_uses_coroutines(tc) if needs_asyncio is None else needs_asyncio,
            needs_magicmock=_uses_mocks(tc) if needs_magicmock is None else needs_magicmock,
        )

        results: list[type[BaseException] | None] = []

        tracer = subject_properties.instrumentation_tracer if subject_properties else None

        for stmt in tc.statements():
            body: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [stmt.node]
            code_str = cst.Module(body=body).code
            finished, exc_type = _exec_statement_guarded(code_str, namespace, tracer)
            if not finished:
                # The statement did not terminate within the watchdog timeout, or
                # tracing aborted the re-execution. Either way the namespace state is
                # unknown after an abandoned statement, so stop executing and mark the
                # remaining statements clean (no bogus pytest.raises wrappers).
                results.extend([None] * (tc.size() - len(results)))
                break
            results.append(exc_type)

        return results

    def _build_test_function(
        self,
        idx: int,
        tc: TestCase,
        exc_types: list[type[BaseException] | None],
        module_aliases: dict[str, str] | None = None,
        external_bindings: Mapping[str, object] | None = None,
    ) -> tuple[cst.FunctionDef, set[type[BaseException]]]:
        """Build a test function, handling expected and unexpected failures.

        A statement whose re-execution raised an exception is handled in one of
        two ways: if the exception is declared as expected by the statement's
        callable (or ``no_xfail`` is set, forcing this for every exception), it
        is wrapped in ``with pytest.raises(...):``. Otherwise the statement is
        emitted bare and the whole function is marked
        ``@pytest.mark.xfail(strict=True)``.

        Args:
            idx: The index used to name the test function.
            tc: The test case to render.
            exc_types: Per-statement exception types (parallel to tc.statements()).
            module_aliases: Optional mapping from module names to their assigned aliases
                in the generated test suite.
            external_bindings: The objects the hoisted external imports bind, by name;
                an exception type whose name they bind otherwise is aliased.

        Returns:
            A tuple of the CST function definition for this test case and the
            set of exception types actually referenced in a
            ``pytest.raises(...)`` call (used by the caller to determine which
            exception-type imports are still needed).
        """
        body: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
        used_exc_types: set[type[BaseException]] = set()
        is_failing = False

        for stmt, exc_type in zip(tc.statements(), exc_types, strict=False):
            if exc_type is None:
                body.append(stmt.node)
            elif self._no_xfail or _is_expected_exception(stmt, exc_type):
                wrapped = cst.With(
                    items=[
                        cst.WithItem(
                            item=cst.Call(
                                func=cst.Attribute(
                                    value=cst.Name("pytest"),
                                    attr=cst.Name("raises"),
                                ),
                                args=[
                                    cst.Arg(
                                        value=cst.Name(
                                            _exception_name(exc_type, external_bindings or {})
                                        )
                                    )
                                ],
                            )
                        )
                    ],
                    body=cst.IndentedBlock(body=[stmt.node]),
                )
                body.append(wrapped)
                used_exc_types.add(exc_type)
            else:
                body.append(stmt.node)
                is_failing = True
            # Append assertion nodes for this statement
            for assertion in stmt.assertions:
                cst_node = assertion_to_cst(assertion, module_aliases=module_aliases)
                if cst_node is not None:
                    body.append(cst_node)

        if not body:
            # No Statement objects — check if this is a seed with raw code.
            raw_code = tc.to_code().strip()
            if raw_code and raw_code != "pass":
                with contextlib.suppress(Exception):
                    body = list(cst.parse_module(raw_code).body)
        if not body:
            body = [cst.SimpleStatementLine(body=[cst.Pass()])]
        elif not _has_executable_cst_statements(body) and not any(
            isinstance(stmt, cst.SimpleStatementLine)
            and any(isinstance(small, cst.Pass) for small in stmt.body)
            for stmt in body
        ):
            body.append(cst.SimpleStatementLine(body=[cst.Pass()]))

        decorators = (_xfail_decorator(),) if is_failing else ()

        return (
            cst.FunctionDef(
                name=cst.Name(f"test_{idx}"),
                params=cst.Parameters(),
                body=cst.IndentedBlock(body=body),
                decorators=decorators,
            ),
            used_exc_types,
        )

    def _build_test_functions(
        self,
        test_cases: Sequence[TestCase],
        module_name: str,
        project_path: str | None,
        subject_properties: SubjectProperties | None,
        *,
        module_aliases: dict[str, str],
        sut_import_stmts: Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement],
        external_import_stmts: Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement],
        external_bindings: Mapping[str, object],
        needs_asyncio: bool,
        needs_magicmock: bool,
    ) -> tuple[
        list[cst.SimpleStatementLine | cst.BaseCompoundStatement],
        set[type[BaseException]],
        bool,
    ]:
        """Dry-run and render one test function per test case.

        Test cases that render without any executable statement are skipped.

        Args:
            test_cases: The test cases to render.
            module_name: The module under test.
            project_path: Optional path prepended to ``sys.path``.
            subject_properties: Optional subject properties used to disable tracing.
            module_aliases: The mapping from module names to their aliases.
            sut_import_stmts: The SUT import statements of the rendered file.
            external_import_stmts: The external import statements of the rendered file.
            external_bindings: The objects the external imports bind, by name.
            needs_asyncio: Whether the rendered file imports ``asyncio``.
            needs_magicmock: Whether the rendered file imports ``MagicMock``.

        Returns:
            The test functions, the exception types referenced by
            ``pytest.raises(...)``, and whether the functions need ``pytest``.
        """
        functions: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
        needs_pytest = False
        used_exc_types: set[type[BaseException]] = set()

        for tc in test_cases:
            exc_types = self._per_statement_exceptions(
                tc,
                module_name,
                project_path,
                subject_properties,
                module_aliases=module_aliases,
                sut_import_stmts=sut_import_stmts,
                external_import_stmts=external_import_stmts,
                needs_asyncio=needs_asyncio,
                needs_magicmock=needs_magicmock,
            )
            func, func_used_exc_types = self._build_test_function(
                len(functions),
                tc,
                exc_types,
                module_aliases=module_aliases,
                external_bindings=external_bindings,
            )
            if not _has_executable_cst_statements(func.body.body):
                continue
            if any(e is not None for e in exc_types) or any(
                isinstance(a, FloatAssertion) for stmt in tc.statements() for a in stmt.assertions
            ):
                needs_pytest = True
            used_exc_types.update(func_used_exc_types)
            functions.append(func)
            if not needs_pytest:
                visitor = _PytestReferenceVisitor()
                func.visit(visitor)
                if visitor.has_pytest:
                    needs_pytest = True

        return functions, used_exc_types, needs_pytest

    @staticmethod
    def _create_patch_nodes(seed: int) -> list[cst.SimpleStatementLine | cst.BaseCompoundStatement]:
        """Return module-level CST statements that patch random.Random.seed.

        Args:
            seed: The seed value to embed in the generated patch.

        Returns:
            The CST statements that install the deterministic seed patch.
        """
        patch_source = (
            "import weakref as _pynguin_weakref\n"
            "_pynguin_orig_seed = getattr(\n"
            "    _pynguin_random.Random.seed, '__pynguin_orig__', _pynguin_random.Random.seed\n"
            ")\n"
            "_pynguin_tracked = _pynguin_weakref.WeakSet()\n"
            "def _pynguin_deterministic_seed(self, x=None):\n"
            "    if x is None:\n"
            f"        x = {seed}\n"
            "    elif type(x).__hash__ is object.__hash__:\n"
            "        x = f'{type(x).__module__}.{type(x).__name__}'\n"
            "    _pynguin_orig_seed(self, x)\n"
            "    _pynguin_tracked.add(self)\n"
            "_pynguin_deterministic_seed.__pynguin_patched__ = True\n"
            "_pynguin_deterministic_seed.__pynguin_orig__ = _pynguin_orig_seed\n"
            "_pynguin_deterministic_seed.__pynguin_instances__ = _pynguin_tracked\n"
            "_pynguin_random.Random.seed = _pynguin_deterministic_seed\n"
        )
        return list(cst.parse_module(patch_source).body)

    @staticmethod
    def _create_seed_fixture(
        seed: int,
    ) -> list[cst.SimpleStatementLine | cst.BaseCompoundStatement]:
        """Return the autouse pytest fixtures that reseed before each test and restore seed after.

        Args:
            seed: The seed value to embed in the generated fixture.

        Returns:
            The CST statements defining the autouse restore and reseed fixtures.
        """
        fixtures_source = (
            "@pytest.fixture(scope='module', autouse=True)\n"
            "def _pynguin_restore_random():\n"
            "    yield\n"
            "    _pynguin_random.Random.seed = _pynguin_orig_seed\n"
            "\n"
            "@pytest.fixture(autouse=True)\n"
            "def _pynguin_seed_random():\n"
            "    _pynguin_random.Random.seed = _pynguin_deterministic_seed\n"
            f"    _pynguin_random.seed({seed})\n"
            "    _pynguin_instances = getattr(\n"
            "        _pynguin_random.Random.seed, '__pynguin_instances__', None\n"
            "    )\n"
            "    if _pynguin_instances is not None:\n"
            "        for _inst in list(_pynguin_instances):\n"
            f"            _inst.seed({seed})\n"
            "    yield\n"
            "    _pynguin_random.Random.seed = _pynguin_orig_seed\n"
        )
        return list(cst.parse_module(fixtures_source).body)

    def write(  # noqa: C901, PLR0915, PLR0914
        self,
        suite: TestSuiteChromosome,
        module_name: str,
        output_path: Path,
        project_path: str | None = None,
        *,
        format_with_black: bool = True,
        seed: int | None = None,
        subject_properties: SubjectProperties | None = None,
    ) -> Path:
        """Write all TestCase objects as a single pytest file.

        Args:
            suite: The test suite chromosome whose test cases are written.
            module_name: The module under test (used for the import statement).
            output_path: Directory in which to write the file.
            project_path: Optional path to prepend to ``sys.path`` so the
                generated file is importable when run from any working directory.
            format_with_black: Whether to format the generated tests with black.
            seed: Optional seed value for deterministic test execution.
            subject_properties: Optional subject properties used to disable
                instrumentation tracing during statement exception detection.

        Returns:
            The path of the written file.
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        module_alias = get_module_alias(module_name)
        module_name_part = module_name.rsplit(".", 1)[-1]
        out_file = output_path / f"test_{module_name_part}.py"
        # The canonical name is used only for *emitted* code (import statements
        # in the generated file); in-process work (importlib lookups below) keeps
        # using the raw, configured ``module_name``, which is guaranteed to
        # resolve in this process.
        canonical_name = canonical_module_name(module_name)

        # Collect all non-builtin, non-SUT modules referenced by isinstance assertions,
        # and assign collision-free aliases.
        isinstance_module_aliases: dict[str, str] = {
            module_name: module_alias,
            canonical_name: module_alias,
        }
        used_aliases: set[str] = {module_alias}
        used_isinstance_modules: set[str] = set()

        for individual in suite.test_case_chromosomes:
            for stmt in individual.test_case.statements():
                for assertion in stmt.assertions:
                    if isinstance(assertion, IsInstanceAssertion) and assertion.module not in {
                        "builtins",
                        module_name,
                        canonical_name,
                    }:
                        used_isinstance_modules.add(assertion.module)

        for mod in sorted(used_isinstance_modules):
            candidate = get_module_alias(mod)
            if candidate in used_aliases:
                candidate = f"{mod.replace('.', '_')}_"
            counter = 1
            while candidate in used_aliases:
                candidate = f"{mod.replace('.', '_')}_{counter}_"
                counter += 1
            used_aliases.add(candidate)
            isinstance_module_aliases[mod] = candidate

        # Drop test cases that render without any executable statement up front,
        # so import-only or docstring-only tests do not leak their imports or
        # names into the file header.
        test_cases = [
            individual.test_case
            for individual in suite.test_case_chromosomes
            if _has_executable_cst_statements(
                self._build_test_function(
                    0,
                    individual.test_case,
                    [None] * individual.test_case.size(),
                    module_aliases=isinstance_module_aliases,
                )[0].body.body
            )
        ]

        # Import only the SUT names the rendered tests reference. The same list is
        # bound in the dry-run namespace, so both resolve exactly the same names.
        used_names: set[str] = set()
        for test_case in test_cases:
            test_case.remove_unused_variables()
            used_names |= _test_case_referenced_names(test_case, isinstance_module_aliases)
        sut_import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = list(
            _build_sut_import_statements(module_name, project_path, used_names)
        )

        # The writer imports asyncio and MagicMock only on demand; the dry run binds
        # them under the same conditions, and external imports may bind them otherwise.
        needs_asyncio = any(_uses_coroutines(test_case) for test_case in test_cases)
        needs_magicmock = any(_uses_mocks(test_case) for test_case in test_cases)

        # Hoist the external (non-SUT) imports the tests read to module level, so a
        # name stays resolvable even if minimization dropped the test's own import.
        # Imports a test itself contains win over those registered for the suite.
        external_import_sources: OrderedSet[str] = OrderedSet()
        for test_case in test_cases:
            for stmt in test_case.statements():
                if isinstance(stmt.node, cst.SimpleStatementLine) and any(
                    isinstance(small, cst.Import | cst.ImportFrom) for small in stmt.node.body
                ):
                    external_import_sources.add(cst.Module(body=[stmt.node]).code.strip())
        for test_case in test_cases:
            external_import_sources.update(test_case.external_imports)
        external_import_sources.update(suite.external_imports)

        tracer = subject_properties.instrumentation_tracer if subject_properties else None
        taken_names: set[str] = {"pytest", *isinstance_module_aliases.values()}
        if needs_asyncio:
            taken_names.add("asyncio")
        if needs_magicmock:
            taken_names.add("MagicMock")

        external_imports = _parse_external_import_statements(
            external_import_sources,
            module_name,
            used_names=used_names,
            sut_import_stmts=sut_import_stmts,
            taken_names=taken_names,
            tracer=tracer,
        )
        external_import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [
            ext.line for ext in external_imports
        ]
        external_bindings = {ext.name: ext.value for ext in external_imports}
        functions, used_exc_types, needs_pytest = self._build_test_functions(
            test_cases,
            module_name,
            project_path,
            subject_properties,
            module_aliases=isinstance_module_aliases,
            sut_import_stmts=sut_import_stmts,
            external_import_stmts=external_import_stmts,
            external_bindings=external_bindings,
            needs_asyncio=needs_asyncio,
            needs_magicmock=needs_magicmock,
        )

        # An empty suite still imports the SUT below, so coverage-by-import keeps
        # working; mark the file so the emitted import gets a coverage comment and
        # a noqa F401 marker (nothing in the file otherwise references the import).
        coverage_by_import_only = not functions
        if coverage_by_import_only:
            functions = [cst.parse_statement("def test_empty():\n    pass\n")]

        preamble: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []

        # Build exception imports for non-builtin exception types that are still
        # referenced by a pytest.raises(...) call (exceptions handled via the
        # xfail marker are emitted bare and need no import). A type a hoisted
        # external import already binds needs no import either.
        exc_import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
        by_module: dict[str, list[str]] = {}
        for exc_type in used_exc_types:
            if (
                exc_type.__module__ == "builtins"
                or external_bindings.get(exc_type.__name__) is exc_type
            ):
                continue
            exc_name = _exception_name(exc_type, external_bindings)
            by_module.setdefault(exc_type.__module__, []).append(
                exc_type.__name__
                if exc_name == exc_type.__name__
                else f"{exc_type.__name__} as {exc_name}"
            )
        for mod in sorted(by_module):
            names = ", ".join(sorted(set(by_module[mod])))
            exc_import_stmts.append(cst.parse_statement(f"from {mod} import {names}\n"))

        # Import the modules referenced by ``isinstance`` assertions under the alias the
        # assertion rendering uses.
        assertion_import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
        for mod in sorted(used_isinstance_modules):
            alias = isinstance_module_aliases[mod]
            assertion_import_stmts.append(cst.parse_statement(f"import {mod} as {alias}\n"))

        # Build the full module: [sys.path preamble +] import(s) + test functions
        if needs_magicmock:
            sut_import_stmts.append(
                cast(
                    "cst.SimpleStatementLine",
                    cst.parse_statement("from unittest.mock import MagicMock\n"),
                )
            )
        if seed is not None:
            needs_pytest = True
            seed_preamble: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [
                cast(
                    "cst.SimpleStatementLine",
                    cst.parse_statement("import random as _pynguin_random\n"),
                ),
                cast("cst.SimpleStatementLine", cst.parse_statement("import pytest\n")),
            ]
            if needs_asyncio:
                seed_preamble.append(
                    cast("cst.SimpleStatementLine", cst.parse_statement("import asyncio\n"))
                )
            patch_nodes = TestSuiteWriter._create_patch_nodes(seed)
            fixtures = TestSuiteWriter._create_seed_fixture(seed)
            module = cst.Module(
                body=[
                    *preamble,
                    *seed_preamble,
                    *patch_nodes,
                    *exc_import_stmts,
                    *sut_import_stmts,
                    *external_import_stmts,
                    *assertion_import_stmts,
                    *fixtures,
                    *functions,
                ]
            )
        else:
            import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
            if needs_pytest:
                import_stmts.append(
                    cast("cst.SimpleStatementLine", cst.parse_statement("import pytest\n"))
                )
            if needs_asyncio:
                import_stmts.append(
                    cast("cst.SimpleStatementLine", cst.parse_statement("import asyncio\n"))
                )
            import_stmts.extend(sut_import_stmts)
            module = cst.Module(
                body=[
                    *preamble,
                    *import_stmts,
                    *exc_import_stmts,
                    *external_import_stmts,
                    *assertion_import_stmts,
                    *functions,
                ]
            )

        output = module.code
        if format_with_black:
            # Import of black might cause problems if it is a SUT dependency, so we
            # only import it if we need it. Importing black must never discard the
            # generated tests: if it fails (e.g. black's module-level code crashes
            # because the SUT on sys.path shadows one of black's own dependencies),
            # fall back to the unformatted -- but still valid -- output.
            try:
                import black  # noqa: PLC0415
                import black.parsing  # noqa: PLC0415
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not import black to format the module '%s': %s", module_name, e
                )
            else:
                try:
                    output = black.format_str(output, mode=black.FileMode())
                except black.parsing.InvalidInput as e:
                    _LOGGER.warning(
                        "Could not format the module '%s' with black: %s", module_name, e
                    )

        if coverage_by_import_only:
            # Mark the SUT import so linters/autofixers don't strip it as unused,
            # and explain why an otherwise-unused import is present.
            pattern = re.compile(rf"^import {re.escape(canonical_name)}\b", re.MULTILINE)
            output = pattern.sub(f"import {canonical_name}  # noqa: F401", output, count=1)
            output = _COVERAGE_BY_IMPORT_COMMENT + output

        out_file.write_text(_LICENSE_HEADER + "\n" + output)
        return out_file
