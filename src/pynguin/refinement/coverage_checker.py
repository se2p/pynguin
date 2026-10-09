#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Coverage preservation check.

This module verifies that refactored tests maintain the same code coverage
as the original tests.  Coverage is measured using Pynguin's own
instrumentation infrastructure: import-time bytecode rewriting via
``InstrumentationTransformer`` that records branch/line coverage through
``ExecutionTracer``.  The configured coverage metric (default: branch
coverage) is used for the comparison.

When Pynguin's ``SubjectProperties`` are available (i.e. when the
refinement pipeline is invoked from within Pynguin after test generation),
we reuse the already-instrumented module and tracer directly.  When
``SubjectProperties`` are not available (e.g. standalone invocation), a
lightweight ``sys.settrace``-based fallback provides line coverage.  The
fallback exists only for standalone/prototype use; in Pynguin-integrated
runs ``SubjectProperties`` is always present, so the fallback is never
exercised.

Key Function:
- check_coverage_preservation(): Compares coverage between original and
  refined test versions using Pynguin's configured metric.

Integration Point: Called during pipeline validation after the repair
loop and mutation filtering succeed.
"""

from __future__ import annotations

import ast
import functools
import logging
import statistics
import sys
import textwrap
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

import pynguin.configuration as config
from pynguin.ga.computations import compute_branch_coverage, compute_line_coverage
from pynguin.refinement.validator import (
    call_test_functions,
    collect_test_functions,
    find_test_function_name,
    preserved_random_seed,
    reseed_random,
)
from pynguin.utils.timeout import resolve_timeout, time_limit

if TYPE_CHECKING:
    import types
    from collections.abc import Callable

    from pynguin.instrumentation.tracer import SubjectProperties

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoverageResult:
    """Result of coverage measurement for a test or test suite.

    Attributes:
        coverage_value: Coverage as a fraction in [0.0, 1.0].
        metric: Which coverage metric was used ('branch', 'line', or 'mean').
        error: Error message if coverage measurement failed.
        branch_coverage: Branch coverage as a fraction in [0.0, 1.0], if computed.
        line_coverage: Line coverage as a fraction in [0.0, 1.0], if computed.
    """

    coverage_value: float = 0.0
    metric: str = "branch"
    error: str | None = None
    branch_coverage: float | None = None
    line_coverage: float | None = None


# ---------------------------------------------------------------------------
# Pynguin-native coverage measurement
# ---------------------------------------------------------------------------


def _measure_coverage_pynguin(
    test_code: str,
    module_under_test: types.ModuleType,
    subject_properties: SubjectProperties,
) -> CoverageResult:
    """Measure coverage using Pynguin's ``ExecutionTracer`` infrastructure.

    The SUT module must already be loaded with instrumented bytecode (which
    is the case when the refinement pipeline is invoked from ``generator.py``
    after test generation).  We:

    1. Initialise a fresh trace (merging the import trace).
    2. Temporarily enable the tracer.
    3. Execute the test code via ``exec()``.
    4. Retrieve the trace and compute coverage using Pynguin's
       ``compute_branch_coverage`` (or ``compute_line_coverage``, depending
       on configuration).

    Args:
        test_code: The test code to execute.
        module_under_test: The instrumented SUT module.
        subject_properties: Pynguin's ``SubjectProperties`` containing the
            tracer and registered code-object / predicate / line metadata.

    Returns:
        CoverageResult with the computed coverage.
    """
    tracer = subject_properties.instrumentation_tracer

    # Determine which coverage metric to compute
    coverage_metrics = set(config.configuration.search_algorithm.coverage_metrics)
    use_branch = config.CoverageMetric.BRANCH in coverage_metrics

    # Prepare a fresh trace (includes import trace)
    tracer.init_trace()

    # Build execution scope
    scope: dict[str, Any] = {
        "__builtins__": __builtins__,
        module_under_test.__name__: module_under_test,
        "pytest": pytest,
    }

    cleaned = textwrap.dedent(test_code.strip())
    func_name = find_test_function_name(cleaned)
    test_funcs = collect_test_functions(cleaned)
    compiled = compile(cleaned, "<test>", "exec")

    # Enable tracer, execute, then disable.
    # We must catch exceptions INSIDE the context manager so that
    # ``temporarily_enable()`` can properly call ``disable()`` on exit.
    # The tracer's thread-identity check requires the current thread to
    # match ``_current_thread_identifier``.  After ``stop()`` is called
    # during test generation, this is ``None``, so we re-register.  The field
    # lives on the wrapped ``ExecutionTracer`` (reached via the proxy's public
    # ``tracer`` property); Pynguin exposes no public setter, so private access
    # is required.
    tracer.tracer._current_thread_identifier = (  # noqa: SLF001
        threading.current_thread().ident
    )
    with tracer.temporarily_enable(), preserved_random_seed():
        try:
            with time_limit(resolve_timeout(None)):
                exec(compiled, scope)  # noqa: S102
            if test_funcs:
                call_test_functions(scope, test_funcs)  # per-test time limits
            elif func_name and func_name in scope and callable(scope[func_name]):
                reseed_random(scope)
                with time_limit(resolve_timeout(None)):
                    scope[func_name]()
        except BaseException as exc:  # noqa: BLE001
            # Catch BaseException because Pynguin's
            # TracingAbortedException inherits from BaseException.
            msg = f"Test execution raised {type(exc).__name__}: {exc}"
            trace = tracer.get_trace()
            if not trace.executed_code_objects and not trace.covered_line_ids:
                return CoverageResult(error=msg)

    # Compute coverage from the trace
    trace = tracer.get_trace()

    branch_cov: float | None = None
    line_cov: float | None = None
    if use_branch:
        coverage = compute_branch_coverage(trace, subject_properties)
        metric_name = "branch"
        branch_cov = coverage
    else:
        coverage = compute_line_coverage(trace, subject_properties)
        metric_name = "line"
        line_cov = coverage

    return CoverageResult(
        coverage_value=coverage,
        metric=metric_name,
        branch_coverage=branch_cov,
        line_coverage=line_cov,
    )


# ---------------------------------------------------------------------------
# Fallback: sys.settrace-based line coverage (standalone mode)
# ---------------------------------------------------------------------------


def _executable_lines(source: str) -> set[int]:
    """Return the set of line numbers that contain executable statements."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, "lineno"):
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom),
            ):
                continue
            lines.add(node.lineno)
    return lines


def _load_sut_source(
    module_under_test: types.ModuleType,
) -> tuple[Path | None, str | None, str | None]:
    """Return ``(path, source, error)`` for the SUT module's source file."""
    sut_file: str | None = getattr(module_under_test, "__file__", None)
    if not sut_file:
        return None, None, "Module has no __file__ attribute"

    sut_path = Path(sut_file).resolve()
    if not sut_path.exists():
        return None, None, f"SUT file not found: {sut_path}"

    try:
        return sut_path, sut_path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, None, f"Could not read SUT source: {exc}"


def _make_sut_line_tracer(
    sut_path: Path, executed_lines: set[int]
) -> Callable[[types.FrameType, str, Any], Any]:
    """Build a ``sys.settrace`` function that adds executed SUT lines to *executed_lines*.

    Only frames whose code lives in *sut_path* get a local tracer, so line events
    in the test, pytest, or the standard library cost nothing beyond the call.
    """
    sut_file_str = str(sut_path)
    lock = threading.Lock()

    @functools.cache
    def _is_sut(filename: str) -> bool:
        if filename == sut_file_str:
            return True
        try:
            return Path(filename).resolve() == sut_path
        except (OSError, RuntimeError):
            return False

    def _tracer(frame: types.FrameType, event: str, _arg: Any) -> Any:
        if not _is_sut(frame.f_code.co_filename):
            return None
        if event == "line":
            with lock:
                executed_lines.add(frame.f_lineno)
        return _tracer

    return _tracer


def _run_test_safely(func: Callable[[], Any], scope: dict[str, Any]) -> None:
    reseed_random(scope)
    with time_limit(resolve_timeout(None)):
        try:
            func()
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001
            _LOGGER.debug("Test raised during coverage execution: %s", exc)


def _execute_test_code_under_trace(
    compiled: Any,
    scope: dict[str, Any],
    test_funcs: list[tuple[str, bool, bool]],
    func_name: str | None,
    *,
    ignore_test_failures: bool = False,
) -> None:
    with preserved_random_seed():
        with time_limit(resolve_timeout(None)):
            exec(compiled, scope)  # noqa: S102
        if test_funcs:
            if ignore_test_failures:
                for name, _is_xfail, _is_strict in test_funcs:
                    func = scope.get(name)
                    if callable(func):
                        _run_test_safely(func, scope)
            else:
                call_test_functions(scope, test_funcs)
        elif func_name and callable(scope.get(func_name)):
            reseed_random(scope)
            with time_limit(resolve_timeout(None)):
                scope[func_name]()


def _trace_sut_lines(
    test_code: str,
    module_under_test: types.ModuleType,
    sut_path: Path,
    *,
    ignore_test_failures: bool = False,
) -> tuple[set[int], BaseException | None]:
    """Execute *test_code* and record the SUT lines it runs via ``sys.settrace``.

    Returns:
        ``(executed_lines, exception)`` where *exception* is whatever the test
        raised (including a ``SyntaxError`` on compilation), or ``None``.
    """
    executed_lines: set[int] = set()
    tracer = _make_sut_line_tracer(sut_path, executed_lines)

    scope: dict[str, Any] = {
        module_under_test.__name__: module_under_test,
        "pytest": pytest,
    }
    cleaned = textwrap.dedent(test_code.strip())
    func_name = find_test_function_name(cleaned)
    test_funcs = collect_test_functions(cleaned)

    old_module = sys.modules.get(module_under_test.__name__)
    sys.modules[module_under_test.__name__] = module_under_test
    old_trace = sys.gettrace()
    try:
        compiled = compile(cleaned, "<test>", "exec")
        sys.settrace(tracer)
        _execute_test_code_under_trace(
            compiled,
            scope,
            test_funcs,
            func_name,
            ignore_test_failures=ignore_test_failures,
        )
    except BaseException as exc:  # noqa: BLE001
        # Executing generated test code may raise anything; degrade gracefully.
        return executed_lines, exc
    finally:
        sys.settrace(old_trace)
        if old_module is None:
            sys.modules.pop(module_under_test.__name__, None)
        else:
            sys.modules[module_under_test.__name__] = old_module
    return executed_lines, None


def _measure_coverage_settrace(
    test_code: str,
    module_under_test: types.ModuleType,
    *,
    ignore_test_failures: bool = False,
) -> CoverageResult:
    """Fallback: measure line coverage via ``sys.settrace``.

    Used only when ``SubjectProperties`` are not available (standalone mode).
    """
    sut_path, sut_source, error = _load_sut_source(module_under_test)
    if error is not None or sut_path is None or sut_source is None:
        return CoverageResult(error=error, metric="line")

    total_executable = _executable_lines(sut_source)
    if not total_executable:
        return CoverageResult(error="No executable lines found in SUT", metric="line")

    executed_lines, exc = _trace_sut_lines(
        test_code, module_under_test, sut_path, ignore_test_failures=ignore_test_failures
    )
    if exc is not None and not executed_lines:
        return CoverageResult(error=f"Test raised {type(exc).__name__}: {exc}", metric="line")

    covered = executed_lines & total_executable
    pct = len(covered) / len(total_executable)

    return CoverageResult(coverage_value=pct, metric="line", line_coverage=pct)


def _compute_suite_coverage_result(
    trace: Any,
    subject_properties: SubjectProperties,
    coverage_metrics: set[config.CoverageMetric],
) -> CoverageResult:
    cov_values: list[float] = []
    branch_cov: float | None = None
    line_cov: float | None = None

    if config.CoverageMetric.BRANCH in coverage_metrics:
        branch_cov = compute_branch_coverage(trace, subject_properties)
        cov_values.append(branch_cov)
    if config.CoverageMetric.LINE in coverage_metrics:
        line_cov = compute_line_coverage(trace, subject_properties)
        cov_values.append(line_cov)

    if not cov_values:
        branch_cov = compute_branch_coverage(trace, subject_properties)
        cov_values.append(branch_cov)

    overall = statistics.mean(cov_values)
    metric_name = (
        "branch"
        if config.CoverageMetric.BRANCH in coverage_metrics
        and config.CoverageMetric.LINE not in coverage_metrics
        else (
            "line"
            if config.CoverageMetric.LINE in coverage_metrics
            and config.CoverageMetric.BRANCH not in coverage_metrics
            else "mean"
        )
    )

    return CoverageResult(
        coverage_value=overall,
        metric=metric_name,
        branch_coverage=branch_cov,
        line_coverage=line_cov,
    )


def _measure_suite_coverage_pynguin(
    test_code: str,
    module_under_test: types.ModuleType,
    subject_properties: SubjectProperties,
) -> CoverageResult:
    """Measure coverage of an entire test suite using Pynguin's tracer."""
    tracer = subject_properties.instrumentation_tracer
    coverage_metrics = set(config.configuration.search_algorithm.coverage_metrics)

    # Prepare a fresh trace (includes import trace)
    tracer.init_trace()

    scope: dict[str, Any] = {
        "__builtins__": __builtins__,
        module_under_test.__name__: module_under_test,
        "pytest": pytest,
    }

    cleaned = textwrap.dedent(test_code.strip())
    test_funcs = collect_test_functions(cleaned)
    try:
        compiled = compile(cleaned, "<test>", "exec")
    except SyntaxError as e:
        return CoverageResult(error=f"SyntaxError in test suite: {e}")

    tracer.tracer._current_thread_identifier = (  # noqa: SLF001
        threading.current_thread().ident
    )
    with tracer.temporarily_enable(), preserved_random_seed():
        try:
            with time_limit(resolve_timeout(None)):
                exec(compiled, scope)  # noqa: S102
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            msg = f"Suite preamble raised {type(exc).__name__}: {exc}"
            trace = tracer.get_trace()
            if not trace.executed_code_objects and not trace.covered_line_ids:
                return CoverageResult(error=msg)

        for name, _is_xfail, _is_strict in test_funcs:
            func = scope.get(name)
            if callable(func):
                _run_test_safely(func, scope)

    trace = tracer.get_trace()
    return _compute_suite_coverage_result(trace, subject_properties, coverage_metrics)


def measure_suite_coverage(
    test_code: str,
    module_under_test: types.ModuleType,
    subject_properties: SubjectProperties | None = None,
) -> CoverageResult:
    """Measure the coverage of a full test suite against the module under test.

    Uses Pynguin's instrumentation infrastructure when ``subject_properties`` is
    provided and valid, falling back to ``sys.settrace`` line coverage otherwise.

    Args:
        test_code: The complete test suite code (preamble + test functions).
        module_under_test: The SUT module.
        subject_properties: Optional SubjectProperties with instrumentation tracer.

    Returns:
        CoverageResult with the overall coverage value and per-metric details.
    """
    if subject_properties is not None and getattr(
        subject_properties, "instrumentation_tracer", None
    ):
        res = _measure_suite_coverage_pynguin(test_code, module_under_test, subject_properties)
        if res.error is None:
            return res
        _LOGGER.warning(
            "Pynguin instrumentation coverage measurement failed: %s; falling back to settrace",
            res.error,
        )

    return _measure_coverage_settrace(test_code, module_under_test, ignore_test_failures=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_coverage_preservation(
    original_test: str,
    refined_test: str,
    module_under_test: types.ModuleType | Any,
    tolerance: float = 0.0,
    subject_properties: SubjectProperties | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Check if the refined test preserves coverage of the original test.

    Requirement: ``refined_coverage >= original_coverage`` (within *tolerance*).

    When ``subject_properties`` is provided, Pynguin's own instrumentation
    tracer is used with the configured coverage metric (default: branch
    coverage).  Otherwise, a ``sys.settrace`` fallback provides line coverage.

    Args:
        original_test: Original test code.
        refined_test: Refined test code.
        module_under_test: Module being tested.
        tolerance: Acceptable coverage decrease (0.0 = no decrease allowed).
        subject_properties: Pynguin's SubjectProperties (optional; enables
            native instrumentation-based coverage).

    Returns:
        Tuple of ``(passed, details_dict)``.
    """
    use_pynguin = subject_properties is not None
    metric_label = "branch" if use_pynguin else "line"

    # Choose measurement function
    def _measure(test_code: str) -> CoverageResult:
        if use_pynguin:
            assert subject_properties is not None
            return _measure_coverage_pynguin(test_code, module_under_test, subject_properties)
        return _measure_coverage_settrace(test_code, module_under_test)

    # Measure original
    original_cov = _measure(original_test)

    if original_cov.error:
        return True, {
            "status": "skipped",
            "reason": original_cov.error,
            "metric": metric_label,
            "original_coverage": 0.0,
            "refined_coverage": 0.0,
        }

    # Measure refined
    refined_cov = _measure(refined_test)

    if refined_cov.error:
        return True, {
            "status": "skipped",
            "reason": refined_cov.error,
            "metric": metric_label,
            "original_coverage": original_cov.coverage_value,
            "refined_coverage": 0.0,
        }

    # Compare (both values are in [0.0, 1.0])
    delta = refined_cov.coverage_value - original_cov.coverage_value

    details: dict[str, Any] = {
        "metric": refined_cov.metric,
        "original_coverage": original_cov.coverage_value,
        "refined_coverage": refined_cov.coverage_value,
        "coverage_delta": delta,
    }

    if delta >= -tolerance:
        details["status"] = "passed"
        return True, details
    details["status"] = "failed"
    details["reason"] = f"Coverage decreased by {abs(delta) * 100:.1f}%"
    return False, details


def get_covered_lines(
    test_code: str,
    module_under_test: types.ModuleType,
) -> set[int]:
    """Return the executable SUT line numbers that *test_code* runs.

    Always uses ``sys.settrace``: Pynguin's own tracer only records line numbers
    when line-coverage instrumentation is active (not the case for the default
    branch metric), and its trace includes the module's import-time lines.

    Args:
        test_code: The test code to execute.
        module_under_test: The module being tested.

    Returns:
        Set of line numbers covered in the SUT, empty if they cannot be determined.
    """
    sut_path, sut_source, error = _load_sut_source(module_under_test)
    if error is not None or sut_path is None or sut_source is None:
        return set()
    executed_lines, _ = _trace_sut_lines(test_code, module_under_test, sut_path)
    return executed_lines & _executable_lines(sut_source)
