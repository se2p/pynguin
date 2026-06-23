#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM-based test refinement for readability and assertion improvement."""

from __future__ import annotations

import ast
import contextlib
import importlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pynguin.refinement.pipeline import TestRefiner
from pynguin.refinement.readability_metrics import compute_all as compute_metrics

if TYPE_CHECKING:
    import types

    from pynguin.instrumentation.tracer import SubjectProperties

_LOGGER = logging.getLogger(__name__)


def _extract_function_text(code: str) -> str:
    """Extract the function definition text from code, preserving comments.

    Uses the AST to find where the first function starts (accounting for
    decorators), then returns the raw text from that point onward so that
    comments such as ``# Arrange`` / ``# Act`` / ``# Assert`` markers are
    kept intact.
    """
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                start = node.lineno - 1  # 0-based
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                return "\n".join(code.split("\n")[start:]).rstrip()
    except SyntaxError:
        pass
    # Fallback: find first def / decorator line
    for i, line in enumerate(code.split("\n")):
        if line.startswith(("def ", "@")):
            return "\n".join(code.split("\n")[i:]).rstrip()
    return code


@dataclass
class _TestOutcome:
    """Result of processing a single generated test function."""

    func_text: str
    processed: bool = False
    refined: bool = False
    failed: bool = False
    iterations: int = 0
    readability_original: float = 0.0
    readability_refined: float = 0.0
    mutation_stats: dict[str, Any] = field(default_factory=dict)


class _MutationAccumulator:
    """Accumulates per-test/suite-level mutation-filtering contribution means."""

    def __init__(self) -> None:
        self._per_test_sum = 0
        self._per_test_count = 0
        self._suite_sum = 0
        self._suite_count = 0

    def add(self, stats: dict[str, Any], mutation_stats: dict[str, Any]) -> None:
        """Fold one test's mutation stats into the running totals."""
        stats["mutation_inferred_total"] += int(mutation_stats.get("inferred_assertions", 0) or 0)
        stats["mutation_removed_total"] += int(mutation_stats.get("assertions_removed", 0) or 0)
        stats["mutation_kept_total"] += int(mutation_stats.get("assertions_kept", 0) or 0)
        stats["mutation_mutants_generated_total"] += int(
            mutation_stats.get("mutants_generated", 0) or 0
        )
        stats["mutation_mutants_killed_total"] += int(
            mutation_stats.get("mutants_killed_total", 0) or 0
        )
        stats["mutation_suite_baseline_size_total"] += int(
            mutation_stats.get("suite_baseline_size", 0) or 0
        )

        per_test = mutation_stats.get("per_test_contributions", {})
        if isinstance(per_test, dict):
            for value in per_test.values():
                self._per_test_sum += int(value or 0)
                self._per_test_count += 1

        suite_level = mutation_stats.get("suite_level_contributions", {})
        if isinstance(suite_level, dict):
            for value in suite_level.values():
                self._suite_sum += int(value or 0)
                self._suite_count += 1

    def finalize(self, stats: dict[str, Any]) -> None:
        """Write the computed contribution means into ``stats``."""
        if self._per_test_count > 0:
            stats["mutation_per_test_contribution_mean"] = self._per_test_sum / self._per_test_count
        if self._suite_count > 0:
            stats["mutation_suite_contribution_mean"] = self._suite_sum / self._suite_count


def _new_stats() -> dict[str, Any]:
    """Return a fresh working statistics dictionary."""
    return {
        "tests_processed": 0,
        "tests_refined": 0,
        "repair_iterations": 0,
        "failed_tests": 0,
        "readability_original": 0.0,
        "readability_refined": 0.0,
        "mutation_inferred_total": 0,
        "mutation_removed_total": 0,
        "mutation_kept_total": 0,
        "mutation_mutants_generated_total": 0,
        "mutation_mutants_killed_total": 0,
        "mutation_suite_baseline_size_total": 0,
        "mutation_per_test_contribution_mean": 0.0,
        "mutation_suite_contribution_mean": 0.0,
    }


def _failure_stats(error: str | None = None, wall_time: float = 0.0) -> dict[str, Any]:
    """Return an empty statistics dictionary for an early/failed refinement run."""
    stats: dict[str, Any] = {
        "tests_processed": 0,
        "tests_refined": 0,
        "repair_iterations": 0,
        "failed_tests": 0,
        "readability_original": 0.0,
        "readability_refined": 0.0,
        "readability_delta": 0.0,
        "llm_calls": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "wall_time_seconds": wall_time,
    }
    if error is not None:
        stats["error"] = error
    return stats


def _load_test_functions(test_file_path: Path) -> tuple[str, list[ast.FunctionDef]]:
    """Read and parse the generated test file into (import_block, test_functions)."""
    raw_test = Path(test_file_path).read_text(encoding="utf-8")
    tree = ast.parse(raw_test)
    import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    test_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

    if import_nodes:
        module_wrapper = ast.Module(
            body=cast("list[ast.stmt]", import_nodes),
            type_ignores=[],
        )
        import_block = ast.unparse(module_wrapper) + "\n"
    else:
        import_block = ""
    return import_block, test_functions


def _import_module_under_test(module_name: str) -> types.ModuleType | None:
    """Dynamically import the module under test, returning ``None`` on failure."""
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        _LOGGER.error("Failed to import module %s: %s", module_name, e)
        return None
    _LOGGER.info("Successfully imported module: %s", module_name)
    return module


def _process_one_test(
    refiner: TestRefiner,
    import_block: str,
    func: ast.FunctionDef,
    max_repair_iterations: int,
) -> _TestOutcome:
    """Refine a single test function and report the outcome."""
    try:
        original_code = import_block + ast.unparse(func)
        original_metrics = compute_metrics(original_code)

        result = refiner.process_test_end_to_end(
            original_code=original_code, max_retries=max_repair_iterations
        )

        if result["success"]:
            refined_code = result["final_code"]
            refined_metrics = compute_metrics(refined_code)
            _LOGGER.info(
                "Successfully refined %s (iterations: %d)", func.name, result["iterations"]
            )
            return _TestOutcome(
                func_text=_extract_function_text(refined_code),
                processed=True,
                refined=True,
                iterations=result["iterations"],
                readability_original=original_metrics.get("aggregate", 0.0),
                readability_refined=refined_metrics.get("aggregate", 0.0),
                mutation_stats=result.get("mutation_stats", {}) or {},
            )

        _LOGGER.warning("Failed to refine %s: %s", func.name, result.get("error", "Unknown"))
        return _TestOutcome(func_text=ast.unparse(func), processed=True, failed=True)
    except Exception as e:
        _LOGGER.exception("Error refining test %s: %s", func.name, e)
        return _TestOutcome(func_text=ast.unparse(func), failed=True)


def _finalize_readability(stats: dict[str, Any]) -> None:
    """Average the accumulated readability scores over the refined tests."""
    if stats["tests_refined"] > 0:
        stats["readability_original"] /= stats["tests_refined"]
        stats["readability_refined"] /= stats["tests_refined"]
        stats["readability_delta"] = stats["readability_refined"] - stats["readability_original"]


def _maybe_write_refined_file(
    stats: dict[str, Any],
    test_file_path: Path,
    import_block: str,
    refined_tests: list[str],
) -> None:
    """Write the assembled refined test file when at least one test was refined."""
    if stats["tests_refined"] <= 0:
        return
    # Assemble file from text (preserves comments & AAA markers).
    refined_code = import_block.rstrip("\n") + "\n\n\n" + "\n\n\n".join(refined_tests)
    refined_path = test_file_path.parent / f"{test_file_path.stem}_refined.py"
    header = (
        "# Test cases automatically generated by Pynguin"
        " (https://www.pynguin.eu).\n"
        "# Refined using LLM-based test refinement pipeline.\n"
    )
    Path(refined_path).write_text(header + refined_code, encoding="utf-8")
    _LOGGER.info("Saved refined tests to %s", refined_path)


def _attach_usage(stats: dict[str, Any], refiner: TestRefiner, start_wall: float) -> None:
    """Attach LLM usage counters and the total wall-clock time to ``stats``."""
    try:
        usage = refiner.llm_client.get_usage()
    except Exception:  # noqa: BLE001
        usage = {}
    stats["llm_calls"] = int(usage.get("calls", 0) or 0)
    stats["llm_input_tokens"] = int(usage.get("input_tokens", 0) or 0)
    stats["llm_output_tokens"] = int(usage.get("output_tokens", 0) or 0)
    stats["wall_time_seconds"] = float(time.perf_counter() - start_wall)


def refine_generated_tests(
    test_file_path: Path,
    module_name: str,
    *,
    llm_model: str = "gpt-4o-mini",
    llm_api_key: str | None = None,
    max_repair_iterations: int = 3,
    max_tests: int | None = 30,
    subject_properties: SubjectProperties | None = None,
) -> dict[str, Any]:
    """Refine generated tests using LLM-based refinement pipeline.

    This is the main entry point called from generator.py after tests are exported.

    Args:
        test_file_path: Path to the generated test file
        module_name: Name of the module under test
        llm_model: Model name to use (default: 'gpt-4o-mini')
        llm_api_key: OpenAI API key (required; can use OPENAI_API_KEY)
        max_repair_iterations: Maximum repair attempts per test
        max_tests: Maximum number of tests to refine
        subject_properties: Optional Pynguin subject properties for coverage checking

    Returns:
        Dict with refinement statistics (tests_processed, tests_refined, repair_iterations, etc.),
        plus aggregated mutation-filtering metrics (inferred/removed/kept assertions,
        mutants generated/killed, and per-test/suite-level contribution means).

    Examples:
        # Using OpenAI
        refine_generated_tests(
            test_file_path=Path("test_module.py"),
            module_name="my_module",
            llm_model="gpt-4o-mini",
            llm_api_key="sk-..."
        )

    """
    _LOGGER.info(
        "Starting LLM-based test refinement for %s (model: %s)",
        module_name,
        llm_model,
    )

    start_wall = time.perf_counter()

    try:
        import_block, test_functions = _load_test_functions(test_file_path)

        module_under_test = _import_module_under_test(module_name)
        if module_under_test is None:
            # Return empty stats if module can't be imported.
            return _failure_stats()

        refiner = TestRefiner(
            api_key=llm_api_key,
            module_under_test=module_under_test,
            project_root=None,
            llm_model=llm_model,
            subject_properties=subject_properties,
        )

        # Ensure usage is per-refinement-run, not per-process.
        with contextlib.suppress(Exception):
            refiner.llm_client.reset_usage()

        stats = _new_stats()
        mutation = _MutationAccumulator()
        refined_tests: list[str] = []

        # Process each test function (up to max_tests).
        limit = max_tests if max_tests is not None else len(test_functions)
        for idx, func in enumerate(test_functions[:limit], 1):
            _LOGGER.info("Processing test %d/%d: %s", idx, len(test_functions), func.name)
            outcome = _process_one_test(refiner, import_block, func, max_repair_iterations)
            refined_tests.append(outcome.func_text)
            if outcome.processed:
                stats["tests_processed"] += 1
            if outcome.refined:
                stats["tests_refined"] += 1
                stats["repair_iterations"] += outcome.iterations
                # Accumulate readability only for successfully refined tests so
                # the delta is a like-for-like comparison.
                stats["readability_original"] += outcome.readability_original
                stats["readability_refined"] += outcome.readability_refined
                mutation.add(stats, outcome.mutation_stats)
            if outcome.failed:
                stats["failed_tests"] += 1

        _finalize_readability(stats)
        mutation.finalize(stats)
        _maybe_write_refined_file(stats, test_file_path, import_block, refined_tests)

        _LOGGER.info("Refinement complete: %s", stats)
        _attach_usage(stats, refiner, start_wall)
        return stats

    except Exception as e:
        _LOGGER.exception("Test refinement failed: %s", e)
        return _failure_stats(error=str(e), wall_time=time.perf_counter() - start_wall)
