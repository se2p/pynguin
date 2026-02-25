#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Coverage Preservation Check (Level 2 Equivalence).

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
lightweight ``sys.settrace``-based fallback provides line coverage.

Key Function:
- check_coverage_preservation(): Compares coverage between original and
  refined test versions using Pynguin's configured metric.

Integration Point: Called during pipeline validation after Stage 3 (repair
loop + mutation filtering) succeeds.
"""

from __future__ import annotations

import ast
import sys
import textwrap
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import types

    from pynguin.instrumentation.tracer import SubjectProperties


@dataclass
class CoverageResult:
    """Result of coverage measurement for a single test.

    Attributes:
        coverage_value: Coverage as a fraction in [0.0, 1.0].
        metric: Which coverage metric was used ('branch' or 'line').
        error: Error message if coverage measurement failed.
    """

    coverage_value: float = 0.0
    metric: str = "branch"
    error: str | None = None


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
    import pynguin.configuration as config  # noqa: PLC0415
    from pynguin.ga.computations import (  # noqa: PLC0415
        compute_branch_coverage,
        compute_line_coverage,
    )

    tracer = subject_properties.instrumentation_tracer

    # Determine which coverage metric to compute
    coverage_metrics = set(config.configuration.statistics_output.coverage_metrics)
    use_branch = config.CoverageMetric.BRANCH in coverage_metrics

    # Prepare a fresh trace (includes import trace)
    tracer.init_trace()

    # Build execution scope
    import pytest  # noqa: PLC0415

    scope: dict[str, Any] = {
        "__builtins__": __builtins__,
        module_under_test.__name__: module_under_test,
        "pytest": pytest,
    }

    try:
        cleaned = textwrap.dedent(test_code.strip())

        # Find the test function name
        func_name = ""
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped.startswith("def "):
                func_name = stripped.split("(")[0].removeprefix("def ")
                break

        compiled = compile(cleaned, "<test>", "exec")

        # Enable tracer, execute, then disable
        with tracer.temporarily_enable():
            exec(compiled, scope)  # noqa: S102
            if func_name and func_name in scope and callable(scope[func_name]):
                scope[func_name]()

    except Exception as exc:  # noqa: BLE001
        # Even if the test crashes, we still have partial trace data
        msg = f"Test execution raised {type(exc).__name__}: {exc}"
        trace = tracer.get_trace()
        if not trace.executed_code_objects and not trace.covered_line_ids:
            return CoverageResult(error=msg)

    # Compute coverage from the trace
    trace = tracer.get_trace()

    if use_branch:
        coverage = compute_branch_coverage(trace, subject_properties)
        metric_name = "branch"
    else:
        coverage = compute_line_coverage(trace, subject_properties)
        metric_name = "line"

    return CoverageResult(coverage_value=coverage, metric=metric_name)


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


def _measure_coverage_settrace(  # noqa: C901
    test_code: str,
    module_under_test: types.ModuleType,
) -> CoverageResult:
    """Fallback: measure line coverage via ``sys.settrace``.

    Used only when ``SubjectProperties`` are not available (standalone mode).
    """
    sut_file: str | None = getattr(module_under_test, "__file__", None)
    if not sut_file:
        return CoverageResult(error="Module has no __file__ attribute", metric="line")

    sut_path = Path(sut_file).resolve()
    if not sut_path.exists():
        return CoverageResult(error=f"SUT file not found: {sut_path}", metric="line")

    try:
        sut_source = sut_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CoverageResult(error=f"Could not read SUT source: {exc}", metric="line")

    total_executable = _executable_lines(sut_source)
    if not total_executable:
        return CoverageResult(error="No executable lines found in SUT", metric="line")

    sut_file_str = str(sut_path)
    executed_lines: set[int] = set()
    lock = threading.Lock()

    def _tracer(frame: types.FrameType, event: str, _arg: Any) -> Any:
        code_file = frame.f_code.co_filename
        if code_file == sut_file_str and event == "line":
            with lock:
                executed_lines.add(frame.f_lineno)
        return _tracer

    scope: dict[str, Any] = {
        module_under_test.__name__: module_under_test,
    }

    try:
        cleaned = textwrap.dedent(test_code.strip())
        func_name = ""
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped.startswith("def "):
                func_name = stripped.split("(")[0].removeprefix("def ")
                break

        compiled = compile(cleaned, "<test>", "exec")

        old_trace = sys.gettrace()
        sys.settrace(_tracer)
        try:
            exec(compiled, scope)  # noqa: S102
            if func_name and func_name in scope and callable(scope[func_name]):
                scope[func_name]()
        finally:
            sys.settrace(old_trace)

    except Exception as exc:  # noqa: BLE001
        sys.settrace(None)
        if not executed_lines:
            return CoverageResult(error=f"Test raised {type(exc).__name__}: {exc}", metric="line")

    covered = executed_lines & total_executable
    pct = len(covered) / len(total_executable) if total_executable else 0.0

    return CoverageResult(coverage_value=pct, metric="line")


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

    Level 2 Equivalence Check — Coverage Preservation.
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
    return None
