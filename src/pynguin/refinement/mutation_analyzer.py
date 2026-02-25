#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Mutation-based assertion filtering for refined tests."""

from __future__ import annotations

import ast
import copy
import logging
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import types

_LOGGER = logging.getLogger(__name__)


class AssertionTracker:
    """Tracks which assertions were added by the LLM vs. present in original test.

    This is critical for filtering: we only want to validate NEW assertions,
    not the original Pynguin-generated ones.
    """

    def __init__(self, original_test: str, refined_test: str):
        """Initialize tracker by parsing both test versions.

        Args:
            original_test: Original Pynguin-generated test code
            refined_test: Test code after LLM refinement
        """
        self.original_assertions = self._extract_assertions(original_test)
        self.refined_assertions = self._extract_assertions(refined_test)
        self.inferred_assertions = self._identify_new_assertions()

    def _extract_assertions(self, test_code: str) -> list[str]:
        """Extract all assertion statements from test code.

        Returns list of assertion expressions (normalized).
        """
        assertions = []
        try:
            tree = ast.parse(test_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    # Normalize the assertion by unparsing it
                    assertion_str = ast.unparse(node.test)
                    assertions.append(assertion_str)
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Could not parse test for assertions: %s", e)
        return assertions

    def _identify_new_assertions(self) -> list[str]:
        """Identify assertions that were added during refinement.

        Returns only assertions present in refined but not in original.
        """
        original_set = set(self.original_assertions)
        refined_set = set(self.refined_assertions)
        new_assertions = refined_set - original_set
        return list(new_assertions)


def _run_test_against_mutant(
    test_code: str,
    mutant_module: types.ModuleType,
    module_name: str,
) -> bool:
    """Execute *test_code* with *mutant_module* in place of the real module.

    Returns ``True`` if the mutant was **killed** (test raised an exception),
    ``False`` if the mutant **survived** (test passed).
    """
    import pytest  # noqa: PLC0415

    test_globals: dict[str, Any] = {
        "__builtins__": __builtins__,
        module_name: mutant_module,
        "pytest": pytest,
    }

    try:
        cleaned = textwrap.dedent(test_code.strip())
        compiled = compile(ast.parse(cleaned), "<test>", "exec")
        exec(compiled, test_globals)  # noqa: S102

        # Find and call the test function
        for name, obj in test_globals.items():
            if callable(obj) and name.startswith("test_"):
                obj()
                break

        return False  # Test passed → mutant survived
    except Exception:  # noqa: BLE001
        return True  # Any exception → mutant killed


def _remove_assertion_by_index(tree: ast.Module, target_idx: int) -> ast.Module:
    """Return a copy of *tree* with one ``Assert`` node replaced by ``pass``.

    The *target_idx*-th ``Assert`` node is replaced to keep line numbers stable.
    """
    new_tree = copy.deepcopy(tree)
    counter = 0

    class _Replacer(ast.NodeTransformer):
        def visit_Assert(self, node: ast.Assert) -> ast.AST:  # noqa: N802
            nonlocal counter
            if counter == target_idx:
                counter += 1
                return ast.Pass()
            counter += 1
            return node

    _Replacer().visit(new_tree)
    ast.fix_missing_locations(new_tree)
    return new_tree


def _killed_set(
    test_code: str,
    mutants: list[tuple[types.ModuleType, Any]],
    module_name: str,
) -> set[int]:
    """Return the set of mutant indices killed by *test_code*."""
    killed: set[int] = set()
    for idx, (mutant_module, _mutations) in enumerate(mutants):
        if mutant_module is None:
            continue
        if _run_test_against_mutant(test_code, mutant_module, module_name):
            killed.add(idx)
    return killed


def filter_vacuous_assertions(  # noqa: C901, PLR0915, PLR0914
    original_test: str,
    refined_test: str,
    _focal_method: str,
    module_under_test: types.ModuleType | None,
    _module_path: str,
    max_mutants: int = 10,
    other_tests_in_suite: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Filter vacuous assertions using per-assertion mutation analysis.

    For each LLM-inferred assertion the test is run **with** and **without**
    that assertion against the mutant set.  An assertion is retained only if
    it kills **at least one additional mutant** that the remaining assertions
    do not already kill (per-test criterion).

    Additionally, when other_tests_in_suite is provided, we compute **suite-level**
    contribution: how many mutants does this assertion kill that are NOT already
    killed by other tests in the suite? This metric is reported for analysis but
    does NOT affect filtering decisions.

    Args:
        original_test: Original Pynguin-generated test.
        refined_test: Test after LLM assertion generation.
        focal_method: Name of the method being tested.
        module_under_test: The module object to mutate.
        module_path: Path to the module source file.
        max_mutants: Maximum mutants to generate (default: 10).
        other_tests_in_suite: Optional list of other test code strings in the suite
            for computing suite-level redundancy metrics.

    Returns:
        Tuple of ``(filtered_test_code, statistics_dict)``.
        Statistics include both per_test_contributions and suite_level_contributions.
    """
    # ------------------------------------------------------------------
    # Import Pynguin's mutation infrastructure
    # ------------------------------------------------------------------
    try:
        from pynguin.assertion.mutation_analysis.controller import (  # noqa: PLC0415
            MutationController,
        )
        from pynguin.assertion.mutation_analysis.mutators import (  # noqa: PLC0415
            FirstOrderMutator,
        )
        from pynguin.assertion.mutation_analysis.operators import (  # noqa: PLC0415
            ArithmeticOperatorReplacement,
            ConstantReplacement,
            LogicalOperatorReplacement,
            RelationalOperatorReplacement,
        )
        from pynguin.assertion.mutation_analysis.transformer import (  # noqa: PLC0415
            ParentNodeTransformer,
        )
    except ImportError as e:
        return refined_test, {
            "inferred_assertions": 0,
            "mutants_generated": 0,
            "mutants_killed_total": 0,
            "assertions_kept": 0,
            "assertions_removed": 0,
            "error": str(e),
        }

    # ------------------------------------------------------------------
    # Step 1: Identify inferred (LLM-added) assertions
    # ------------------------------------------------------------------
    tracker = AssertionTracker(original_test, refined_test)

    if not tracker.inferred_assertions:
        return refined_test, {
            "inferred_assertions": 0,
            "mutants_generated": 0,
            "mutants_killed_total": 0,
            "assertions_kept": 0,
            "assertions_removed": 0,
        }

    # ------------------------------------------------------------------
    # Step 2: Parse SUT source and generate mutants
    # ------------------------------------------------------------------
    if not module_under_test or not hasattr(module_under_test, "__file__"):
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "mutants_killed_total": 0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0,
            "error": "module source not available",
        }

    try:
        sut_file = module_under_test.__file__
        if sut_file is None:
            raise FileNotFoundError("Module has no __file__ attribute")
        sut_path = Path(sut_file)
        if not sut_path.exists():
            raise FileNotFoundError(f"SUT file not found: {sut_path}")

        sut_source = sut_path.read_text(encoding="utf-8")
        sut_ast = ParentNodeTransformer.create_ast(sut_source)
    except Exception as e:  # noqa: BLE001
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "mutants_killed_total": 0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0,
            "error": str(e),
        }

    selected_operators = [
        ArithmeticOperatorReplacement,
        RelationalOperatorReplacement,
        LogicalOperatorReplacement,
        ConstantReplacement,
    ]

    mutator = FirstOrderMutator(operators=selected_operators)
    controller = MutationController(
        mutant_generator=mutator,
        module_ast=sut_ast,
        module=module_under_test,
    )

    # Materialise mutants so we can re-run them per assertion.
    # NOTE: The proposal says "reuse mutants from Pynguin's assertion-
    # generation phase".  Pynguin's MutationController does not cache
    # mutants — create_mutants() is a deterministic generator that
    # re-derives mutants from the AST each call.  Constructing a fresh
    # controller with the *same* operators and module AST therefore
    # produces the identical mutant set, making this functionally
    # equivalent to reuse without requiring cross-phase plumbing.
    mutants: list[tuple[types.ModuleType, Any]] = []
    for mutant_module, mutations in controller.create_mutants():
        if len(mutants) >= max_mutants:
            break
        if mutant_module is not None:
            mutants.append((mutant_module, mutations))

    if not mutants:
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "mutants_killed_total": 0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0,
        }

    # ------------------------------------------------------------------
    # Step 3: Per-assertion filtering
    # ------------------------------------------------------------------
    module_name = module_under_test.__name__

    # Parse the refined test AST once
    try:
        refined_tree = ast.parse(refined_test)
    except SyntaxError as e:
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": len(mutants),
            "mutants_killed_total": 0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0,
            "error": str(e),
        }

    # Map assertion index → assertion string for all Assert nodes
    all_asserts: list[str] = [
        ast.unparse(node.test) for node in ast.walk(refined_tree) if isinstance(node, ast.Assert)
    ]

    # Identify which indices correspond to inferred assertions
    inferred_set = set(tracker.inferred_assertions)
    inferred_indices: list[int] = [i for i, a in enumerate(all_asserts) if a in inferred_set]

    if not inferred_indices:
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": len(mutants),
            "mutants_killed_total": 0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0,
        }

    # Baseline: killed set with ALL assertions present
    baseline_killed = _killed_set(refined_test, mutants, module_name)

    # Compute suite-level baseline if other tests provided
    suite_baseline_killed: set[int] = set()
    if other_tests_in_suite:
        for other_test in other_tests_in_suite:
            suite_baseline_killed |= _killed_set(other_test, mutants, module_name)

    # For each inferred assertion, check if removing it changes the killed set
    assertions_to_remove: list[int] = []
    per_test_contributions: dict[int, int] = {}  # assert_idx -> num additional mutants killed
    suite_level_contributions: dict[int, int] = {}  # assert_idx -> num unique kills vs suite

    for assert_idx in inferred_indices:
        # Build test code WITHOUT this assertion
        without_tree = _remove_assertion_by_index(refined_tree, assert_idx)
        without_code = ast.unparse(without_tree)
        without_killed = _killed_set(without_code, mutants, module_name)

        # Per-test contribution: mutants killed by THIS test only
        additional_kills = baseline_killed - without_killed
        per_test_contributions[assert_idx] = len(additional_kills)

        # Suite-level contribution: unique kills not covered by other tests
        if other_tests_in_suite:
            # Mutants killed by this assertion that NO other test kills
            unique_to_assertion = additional_kills - suite_baseline_killed
            suite_level_contributions[assert_idx] = len(unique_to_assertion)
        else:
            suite_level_contributions[assert_idx] = len(additional_kills)  # fallback to per-test

        all_asserts[assert_idx][:60]

        # Filtering decision: use per-test criterion (current behavior)
        if len(additional_kills) == 0:
            # This assertion kills zero additional mutants in this test → vacuous
            (
                f" (suite-level: {suite_level_contributions[assert_idx]})"
                if other_tests_in_suite
                else ""
            )
            assertions_to_remove.append(assert_idx)
        else:
            (
                f", suite-level: {suite_level_contributions[assert_idx]}"
                if other_tests_in_suite
                else ""
            )

    # ------------------------------------------------------------------
    # Step 4: Build filtered test
    # ------------------------------------------------------------------
    if assertions_to_remove:
        filtered_tree = copy.deepcopy(refined_tree)
        remove_set = set(assertions_to_remove)
        counter = 0

        class _BulkRemover(ast.NodeTransformer):
            def visit_Assert(self, node: ast.Assert) -> ast.AST:  # noqa: N802
                nonlocal counter
                current = counter
                counter += 1
                if current in remove_set:
                    return ast.Pass()
                return node

        _BulkRemover().visit(filtered_tree)
        ast.fix_missing_locations(filtered_tree)
        filtered_test = ast.unparse(filtered_tree)
    else:
        filtered_test = refined_test

    kept = len(inferred_indices) - len(assertions_to_remove)
    removed = len(assertions_to_remove)

    stats: dict[str, Any] = {
        "inferred_assertions": len(tracker.inferred_assertions),
        "mutants_generated": len(mutants),
        "mutants_killed_total": len(baseline_killed),
        "assertions_kept": kept,
        "assertions_removed": removed,
        "per_test_contributions": per_test_contributions,  # dict[assert_idx -> num kills]
        "suite_level_contributions": suite_level_contributions,  # dict[assert_idx -> unique kills]
        "suite_baseline_size": len(suite_baseline_killed) if other_tests_in_suite else 0,
    }

    # Compute summary metrics
    if per_test_contributions:
        avg_per_test = sum(per_test_contributions.values()) / len(per_test_contributions)
        avg_suite_level = sum(suite_level_contributions.values()) / len(suite_level_contributions)
        stats["avg_per_test_contribution"] = avg_per_test
        stats["avg_suite_level_contribution"] = avg_suite_level

    if other_tests_in_suite and per_test_contributions:
        pass

    return filtered_test, stats
