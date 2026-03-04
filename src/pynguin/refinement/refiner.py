#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM-based test refinement for readability and assertion improvement."""

from __future__ import annotations

import ast
import contextlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pynguin.refinement.pipeline import TestRefiner
from pynguin.refinement.readability_metrics import compute_all as compute_metrics

if TYPE_CHECKING:
    from pynguin.instrumentation.tracer import SubjectProperties

_LOGGER = logging.getLogger(__name__)


def refine_generated_tests(  # noqa: PLR0917, PLR0915, PLR0914, C901
    test_file_path: Path,
    module_name: str,
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

    try:  # noqa: PLR1702
        # Read generated test file
        raw_test = Path(test_file_path).read_text(encoding="utf-8")

        # Parse test functions
        tree = ast.parse(raw_test)
        import_nodes = [
            node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        test_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

        if import_nodes:
            module_wrapper = ast.Module(
                body=cast("list[ast.stmt]", import_nodes),
                type_ignores=[],
            )
            import_block = ast.unparse(module_wrapper) + "\n"
        else:
            import_block = ""

        # Import the module under test dynamically
        try:
            test_target_module = __import__(module_name)
            _LOGGER.info("Successfully imported module: %s", module_name)
        except ImportError as e:
            _LOGGER.error("Failed to import module %s: %s", module_name, e)
            # Return empty stats if module can't be imported
            return {
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
                "wall_time_seconds": 0.0,
            }

        # Initialize refiner
        refiner = TestRefiner(
            api_key=llm_api_key,
            module_under_test=test_target_module,
            project_root=None,
            llm_model=llm_model,
            subject_properties=subject_properties,
        )

        # Ensure usage is per-refinement-run, not per-process.
        with contextlib.suppress(Exception):
            refiner.llm_client.reset_usage()

        # Track statistics
        stats = {
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

        mutation_per_test_sum = 0
        mutation_per_test_count = 0
        mutation_suite_sum = 0
        mutation_suite_count = 0

        refined_tests = []

        # Process each test function (up to max_tests)
        limit = max_tests if max_tests is not None else len(test_functions)
        for idx, func in enumerate(test_functions[:limit], 1):
            _LOGGER.info("Processing test %d/%d: %s", idx, len(test_functions), func.name)

            try:
                # Extract original code
                original_code = import_block + ast.unparse(func)

                # Compute original readability
                original_metrics = compute_metrics(original_code)
                stats["readability_original"] += original_metrics.get("aggregate", 0.0)

                # Run end-to-end refinement with repair loop
                result = refiner.process_test_end_to_end(
                    original_code=original_code, max_retries=max_repair_iterations
                )

                stats["tests_processed"] += 1

                if result["success"]:
                    refined_code = result["final_code"]

                    # Compute refined readability
                    refined_metrics = compute_metrics(refined_code)
                    stats["readability_refined"] += refined_metrics.get("aggregate", 0.0)

                    # Extract just the function (remove imports)
                    refined_tree = ast.parse(refined_code)
                    refined_func = next(
                        n for n in refined_tree.body if isinstance(n, ast.FunctionDef)
                    )
                    refined_tests.append(refined_func)

                    stats["tests_refined"] += 1
                    stats["repair_iterations"] += result["iterations"]

                    mutation_stats = result.get("mutation_stats", {}) or {}
                    stats["mutation_inferred_total"] += int(
                        mutation_stats.get("inferred_assertions", 0) or 0
                    )
                    stats["mutation_removed_total"] += int(
                        mutation_stats.get("assertions_removed", 0) or 0
                    )
                    stats["mutation_kept_total"] += int(
                        mutation_stats.get("assertions_kept", 0) or 0
                    )
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
                            mutation_per_test_sum += int(value or 0)
                            mutation_per_test_count += 1

                    suite_level = mutation_stats.get("suite_level_contributions", {})
                    if isinstance(suite_level, dict):
                        for value in suite_level.values():
                            mutation_suite_sum += int(value or 0)
                            mutation_suite_count += 1

                    _LOGGER.info(
                        "Successfully refined %s (iterations: %d)",
                        func.name,
                        result["iterations"],
                    )
                else:
                    # Keep original if refinement failed
                    refined_tests.append(func)
                    stats["failed_tests"] += 1
                    _LOGGER.warning(
                        "Failed to refine %s: %s",
                        func.name,
                        result.get("error", "Unknown"),
                    )

            except Exception as e:
                _LOGGER.exception("Error refining test %s: %s", func.name, e)
                refined_tests.append(func)  # Keep original
                stats["failed_tests"] += 1

        # Calculate average readability scores
        if stats["tests_processed"] > 0:
            stats["readability_original"] /= stats["tests_processed"]
            stats["readability_refined"] /= max(stats["tests_refined"], 1)
            stats["readability_delta"] = (
                stats["readability_refined"] - stats["readability_original"]
            )

        if mutation_per_test_count > 0:
            stats["mutation_per_test_contribution_mean"] = (
                mutation_per_test_sum / mutation_per_test_count
            )
        if mutation_suite_count > 0:
            stats["mutation_suite_contribution_mean"] = mutation_suite_sum / mutation_suite_count

        # Save refined test file
        if stats["tests_refined"] > 0:
            # Create new AST module with refined tests
            refined_body = cast("list[ast.stmt]", import_nodes) + cast(
                "list[ast.stmt]", refined_tests
            )
            refined_module = ast.Module(body=refined_body, type_ignores=[])
            refined_code = ast.unparse(ast.fix_missing_locations(refined_module))

            # Save to file (overwrite original or save as _refined)
            refined_path = test_file_path.parent / f"{test_file_path.stem}_refined.py"
            header = (
                "# Test cases automatically generated by Pynguin"
                " (https://www.pynguin.eu).\n"
                "# Refined using LLM-based test refinement pipeline.\n"
            )
            Path(refined_path).write_text(header + refined_code, encoding="utf-8")

            _LOGGER.info("Saved refined tests to %s", refined_path)

        _LOGGER.info("Refinement complete: %s", stats)

        try:
            usage = refiner.llm_client.get_usage()
        except Exception:  # noqa: BLE001
            usage = {}

        stats["llm_calls"] = int(usage.get("calls", 0) or 0)
        stats["llm_input_tokens"] = int(usage.get("input_tokens", 0) or 0)
        stats["llm_output_tokens"] = int(usage.get("output_tokens", 0) or 0)
        stats["wall_time_seconds"] = float(time.perf_counter() - start_wall)
        return stats

    except Exception as e:
        _LOGGER.exception("Test refinement failed: %s", e)
        return {
            "tests_processed": 0,
            "tests_refined": 0,
            "repair_iterations": 0,
            "failed_tests": 0,
            "error": str(e),
            "llm_calls": 0,
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "wall_time_seconds": float(time.perf_counter() - start_wall),
        }
