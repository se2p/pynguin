#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Writes generated test suites to pytest files."""

from __future__ import annotations

import contextlib
import importlib
import logging
import re
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, cast

import libcst as cst

from pynguin.assertion.assertion_to_ast import assertion_to_cst
from pynguin.testcase.execution import OutputSuppressionContext, _suppress_logging
from pynguin.utils.exceptions import TracingAbortedException
from pynguin.utils.fs_isolation import FilesystemIsolation
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
from pynguin.utils.naming import canonical_module_name, get_module_alias

if TYPE_CHECKING:
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
                _suppress_logging(),
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
    ) -> list[type[BaseException] | None]:
        """Execute each statement individually; return per-statement exception types.

        Args:
            tc: The test case whose statements are executed.
            module_name: The module under test.
            project_path: Optional path prepended to ``sys.path``.
            subject_properties: Optional subject properties used to disable tracing.

        Returns:
            A list with one entry per statement: the exception type raised by that
            statement, or ``None`` if it executed without error.
        """
        effective_path = project_path if project_path is not None else ""
        if effective_path and effective_path not in sys.path:
            sys.path.insert(0, effective_path)

        module_alias = get_module_alias(module_name)

        try:
            module = importlib.import_module(module_name)
        except Exception:  # noqa: BLE001
            return [None] * tc.size()

        import pytest  # noqa: PLC0415

        namespace: dict = {
            module_alias: module,
            "__builtins__": __builtins__,
            "pytest": pytest,
        }
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
                                args=[cst.Arg(value=cst.Name(exc_type.__name__))],
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
                cst_node = assertion_to_cst(assertion)
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
            "if not getattr(random.Random.seed, '__pynguin_patched__', False):\n"
            "    _pynguin_orig_seed = random.Random.seed\n"
            "    _pynguin_tracked = _pynguin_weakref.WeakSet()\n"
            "    def _pynguin_deterministic_seed(self, x=None):\n"
            "        if x is None:\n"
            f"            x = {seed}\n"
            "        elif type(x).__hash__ is object.__hash__:\n"
            "            x = f'{type(x).__module__}.{type(x).__name__}'\n"
            "        _pynguin_orig_seed(self, x)\n"
            "        _pynguin_tracked.add(self)\n"
            "    _pynguin_deterministic_seed.__pynguin_patched__ = True\n"
            "    _pynguin_deterministic_seed.__pynguin_instances__ = _pynguin_tracked\n"
            "    random.Random.seed = _pynguin_deterministic_seed\n"
        )
        return list(cst.parse_module(patch_source).body)

    @staticmethod
    def _create_seed_fixture(seed: int) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        """Return the autouse pytest fixture that reseeds before each test.

        Args:
            seed: The seed value to embed in the generated fixture.

        Returns:
            The CST statement defining the autouse reseed fixture.
        """
        fixture_source = (
            "@pytest.fixture(autouse=True)\n"
            "def _pynguin_seed_random():\n"
            f"    random.seed({seed})\n"
            "    _pynguin_instances = getattr(random.Random.seed, '__pynguin_instances__', None)\n"
            "    if _pynguin_instances is not None:\n"
            "        for _inst in list(_pynguin_instances):\n"
            f"            _inst.seed({seed})\n"
            "    yield\n"
        )
        return cst.parse_statement(fixture_source)

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

        functions: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
        needs_pytest = False
        used_exc_types: set[type[BaseException]] = set()

        # Build one test function per test case chromosome in the suite
        for idx, individual in enumerate(suite.test_case_chromosomes):
            tc = individual.test_case
            tc.remove_unused_variables()
            exc_types = self._per_statement_exceptions(
                tc, module_name, project_path, subject_properties
            )
            if any(e is not None for e in exc_types):
                needs_pytest = True
            func, func_used_exc_types = self._build_test_function(idx, tc, exc_types)
            used_exc_types.update(func_used_exc_types)
            functions.append(func)

        # An empty suite still imports the SUT below, so coverage-by-import keeps
        # working; mark the file so the emitted import gets a coverage comment and
        # a `# noqa: F401` (nothing in the file otherwise references the import).
        coverage_by_import_only = not functions
        if coverage_by_import_only:
            functions = [cst.parse_statement("def test_empty():\n    pass\n")]

        preamble: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []

        # Build exception imports for non-builtin exception types that are still
        # referenced by a pytest.raises(...) call (exceptions handled via the
        # xfail marker are emitted bare and need no import).
        exc_import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
        by_module: dict[str, list[str]] = {}
        for exc_type in used_exc_types:
            if exc_type.__module__ != "builtins":
                by_module.setdefault(exc_type.__module__, []).append(exc_type.__name__)
        for mod in sorted(by_module):
            names = ", ".join(sorted(set(by_module[mod])))
            exc_import_stmts.append(cst.parse_statement(f"from {mod} import {names}\n"))

        # Build the full module: [sys.path preamble +] import(s) + test functions
        # Use explicit import of all public names instead of `import *` so that
        # names excluded from __all__ (e.g. AbstractConstraint, error submodule)
        # are still available in the generated test namespace.
        try:
            sut_mod = importlib.import_module(module_name)
            # Exclude any name that equals module_alias to avoid shadowing
            # e.g. `from first import first` would overwrite `import first as first`
            public_names = sorted(
                n for n in dir(sut_mod) if not n.startswith("_") and n != module_alias
            )
        except Exception:  # noqa: BLE001
            public_names = []
        if public_names:
            names_str = ", ".join(public_names)
            star_stmt = cst.parse_statement(f"from {canonical_name} import {names_str}\n")
        else:
            star_stmt = None
        sut_import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [
            cst.parse_statement("import sys\n"),
        ]
        module_alias = get_module_alias(module_name)
        sut_import_stmts.extend([
            cst.parse_statement(f"import {canonical_name}\n"),
            cst.parse_statement(f"{module_alias} = sys.modules['{canonical_name}']\n"),
        ])
        if star_stmt is not None:
            sut_import_stmts.append(star_stmt)
        if seed is not None:
            needs_pytest = True
            seed_preamble: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = [
                cast("cst.SimpleStatementLine", cst.parse_statement("import random\n")),
                cast("cst.SimpleStatementLine", cst.parse_statement("import pytest\n")),
            ]
            patch_nodes = TestSuiteWriter._create_patch_nodes(seed)
            fixture = TestSuiteWriter._create_seed_fixture(seed)
            module = cst.Module(
                body=[
                    *preamble,
                    *seed_preamble,
                    *patch_nodes,
                    *exc_import_stmts,
                    *sut_import_stmts,
                    fixture,
                    *functions,
                ]
            )
        else:
            import_stmts: list[cst.SimpleStatementLine | cst.BaseCompoundStatement] = []
            if needs_pytest:
                import_stmts.append(
                    cast("cst.SimpleStatementLine", cst.parse_statement("import pytest\n"))
                )
            import_stmts.extend(sut_import_stmts)
            module = cst.Module(body=[*preamble, *import_stmts, *exc_import_stmts, *functions])

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
