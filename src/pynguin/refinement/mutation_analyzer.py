#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Mutation-based assertion filtering for refined tests."""

from __future__ import annotations

import ast
import copy
import enum
import logging
import sys
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest

import pynguin.configuration as config
from pynguin.assertion.mutation_analysis.controller import (
    MutationController,
    MutationMetrics,
    compute_reported_mutation_score,
    create_mutation_controller,
)
from pynguin.assertion.mutation_analysis.mutators import FirstOrderMutator
from pynguin.assertion.mutation_analysis.operators import (
    ArithmeticOperatorReplacement,
    ConstantReplacement,
    LogicalOperatorReplacement,
    RelationalOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.refinement.coverage_checker import get_covered_lines
from pynguin.refinement.validator import (
    TestExecution,
    call_test_functions,
    collect_test_functions,
    execute_test,
)
from pynguin.testcase.execution import ModuleProvider
from pynguin.utils.timeout import TestExecutionTimeoutError, resolve_timeout, time_limit

if TYPE_CHECKING:
    import types
    from collections.abc import Callable

    from pynguin.instrumentation.tracer import SubjectProperties

_LOGGER = logging.getLogger(__name__)


def prioritize_mutants(
    all_mutants: list[tuple[types.ModuleType | None, Any]],
    covered_lines: set[int] | None,
    max_mutants: int,
) -> list[tuple[types.ModuleType, Any]]:
    """Prioritize mutants based on test line coverage.

    Selection strategy:
    1. If ``covered_lines`` is empty or None, return the first ``max_mutants`` in AST order.
    2. Otherwise, select at most one mutant per covered line (in AST order).
    3. If more mutants are needed, fill up with remaining mutants on covered lines.
    4. If still needed, fill up with uncovered line mutants.
    """
    valid_mutants: list[tuple[types.ModuleType, Any]] = [
        (item[0], item[1]) for item in all_mutants if item[0] is not None
    ]
    if not covered_lines or max_mutants <= 0:
        return valid_mutants[:max_mutants]

    covered_mutants: list[tuple[int, tuple[types.ModuleType, Any]]] = []
    uncovered_mutants: list[tuple[types.ModuleType, Any]] = []

    for mutant_module, mutations in valid_mutants:
        line: int | None = None
        if mutations and hasattr(mutations[0], "node"):
            line = getattr(mutations[0].node, "lineno", None)

        if line is not None and line in covered_lines:
            covered_mutants.append((line, (mutant_module, mutations)))
        else:
            uncovered_mutants.append((mutant_module, mutations))

    # Group covered mutants by line preserving AST order
    covered_by_line: dict[int, list[tuple[types.ModuleType, Any]]] = {}
    for line, mutant_tuple in covered_mutants:
        covered_by_line.setdefault(line, []).append(mutant_tuple)

    # Phase 1: One mutant per covered line
    selected: list[tuple[types.ModuleType, Any]] = []
    remaining_covered: list[tuple[types.ModuleType, Any]] = []
    for items in covered_by_line.values():
        selected.append(items[0])
        remaining_covered.extend(items[1:])

    if len(selected) >= max_mutants:
        return selected[:max_mutants]

    # Phase 2: Remaining mutants on covered lines
    needed = max_mutants - len(selected)
    selected.extend(remaining_covered[:needed])

    if len(selected) >= max_mutants:
        return selected[:max_mutants]

    # Phase 3: Fill up with uncovered mutants
    needed = max_mutants - len(selected)
    selected.extend(uncovered_mutants[:needed])

    return selected[:max_mutants]


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
        except (SyntaxError, ValueError) as e:
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


def _execute_against(
    test_code: str,
    mutant_module: types.ModuleType,
    module_name: str,
) -> bool | None:
    """Execute *test_code* with *mutant_module* in place of the real module.

    Returns ``True`` if the test raised an exception, ``False`` if it passed, and
    ``None`` if it timed out.
    """
    test_globals: dict[str, Any] = {
        "__builtins__": __builtins__,
        module_name: mutant_module,
        "pytest": pytest,
    }

    # Temporarily patch sys.modules so that `import <module_name> as module_0`
    # inside exec() resolves to the mutant, not the real module.
    old_module = sys.modules.get(module_name)
    sys.modules[module_name] = mutant_module
    try:
        cleaned = textwrap.dedent(test_code.strip())
        compiled = compile(ast.parse(cleaned), "<test>", "exec")
        with time_limit(resolve_timeout(None)):
            exec(compiled, test_globals)  # noqa: S102
        # Run every test function on its own (and under its own time limit),
        # honouring xfail markers, so an expected failure does not count as a kill
        # or hide the other tests.
        call_test_functions(test_globals, collect_test_functions(cleaned))

        return False
    except TestExecutionTimeoutError:
        return None
    except BaseException:  # noqa: BLE001
        return True  # Any exception, incl. pytest.fail
    finally:
        # Restore the original module (or remove if it wasn't there)
        if old_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = old_module


def _run_test_against_mutant(
    test_code: str,
    mutant_module: types.ModuleType,
    module_name: str,
) -> bool:
    """Execute *test_code* with *mutant_module* in place of the real module.

    Returns ``True`` if the mutant was **killed** (test raised an exception),
    ``False`` if the mutant **survived** (test passed, or ran away into a timeout,
    in which case we cannot claim a kill).
    """
    return _execute_against(test_code, mutant_module, module_name) is True


def passes_on_module(test_code: str, module_under_test: types.ModuleType) -> bool:
    """Return whether every test in *test_code* passes on the unmutated module.

    Kills only mean something for code that passes on the clean module: code that
    raises there "kills" every mutant.
    """
    return _execute_against(test_code, module_under_test, module_under_test.__name__) is False


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


def killed_set(
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


def _vacuous_stats(
    inferred: int,
    *,
    mutants_generated: int = 0,
    mutants_killed_total: int = 0,
    assertions_kept: int | None = None,
    assertions_removed: int = 0,
    error: str | None = None,
) -> dict[str, Any]:
    """Build the standard statistics dict for an early/terminal filtering result."""
    stats: dict[str, Any] = {
        "inferred_assertions": inferred,
        "mutants_generated": mutants_generated,
        "mutants_killed_total": mutants_killed_total,
        "assertions_kept": inferred if assertions_kept is None else assertions_kept,
        "assertions_removed": assertions_removed,
    }
    if error is not None:
        stats["error"] = error
    return stats


def create_mutants(
    module_under_test: types.ModuleType,
    max_mutants: int,
    covered_lines: set[int] | None = None,
) -> tuple[list[tuple[types.ModuleType, Any]], str | None]:
    """Generate up to *max_mutants* mutant modules for the SUT.

    If *covered_lines* is provided, mutants lying on those lines are prioritized
    (at most one mutant per line first, then additional mutants on covered lines,
    then uncovered mutants).

    Returns ``(mutants, error)`` where *error* is a non-None message on failure.
    """
    try:
        sut_file = module_under_test.__file__
        if sut_file is None:
            raise FileNotFoundError("Module has no __file__ attribute")
        sut_path = Path(sut_file)
        if not sut_path.exists():
            raise FileNotFoundError(f"SUT file not found: {sut_path}")
        sut_source = sut_path.read_text(encoding="utf-8")
        sut_ast = ParentNodeTransformer.create_ast(sut_source)
    except (OSError, SyntaxError, ValueError) as e:
        return [], str(e)

    mutator = FirstOrderMutator(
        operators=[
            ArithmeticOperatorReplacement,
            RelationalOperatorReplacement,
            LogicalOperatorReplacement,
            ConstantReplacement,
        ]
    )
    controller = MutationController(
        mutant_generator=mutator,
        module_ast=sut_ast,
        module=module_under_test,
    )

    # MutationController.create_mutants() deterministically re-derives the mutant
    # set from the AST, so a fresh controller with the same operators/AST
    # reproduces the set used during Pynguin's assertion-generation phase.
    if not covered_lines:
        mutants: list[tuple[types.ModuleType, Any]] = []
        for mutant_module, mutations in controller.create_mutants():
            if len(mutants) >= max_mutants:
                break
            if mutant_module is not None:
                mutants.append((mutant_module, mutations))
        return mutants, None

    all_mutants = list(controller.create_mutants())
    selected = prioritize_mutants(all_mutants, covered_lines, max_mutants)
    return selected, None


def _index_all_assertions(tree: ast.Module) -> list[str]:
    """Return the unparsed test expression of every ``Assert`` node in DFS order.

    DFS (NodeVisitor) order matches :func:`_remove_assertion_by_index` so that
    assertion indices stay consistent between mapping and removal, including for
    assertions nested inside ``pytest.raises`` / ``try`` / ``if`` blocks.
    """
    found: list[str] = []

    class _AssertIndexer(ast.NodeVisitor):
        def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
            try:
                found.append(ast.unparse(node.test))
            except (ValueError, AttributeError, TypeError):
                found.append("")
            self.generic_visit(node)

    _AssertIndexer().visit(tree)
    return found


def _assertion_removal_lines(tree: ast.Module, remove_set: set[int]) -> tuple[set[int], set[int]]:
    """Return ``(all_lines, start_lines)`` for the asserts whose index is removed."""
    all_lines: set[int] = set()
    start_lines: set[int] = set()
    counter = [0]

    class _LineCollector(ast.NodeVisitor):
        def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
            if counter[0] in remove_set:
                end = node.end_lineno or node.lineno
                all_lines.update(range(node.lineno, end + 1))
                start_lines.add(node.lineno)
            counter[0] += 1
            self.generic_visit(node)

    _LineCollector().visit(tree)
    return all_lines, start_lines


def _build_filtered_test(
    refined_test: str, tree: ast.Module, assertions_to_remove: list[int]
) -> str:
    """Return *refined_test* with the removed assertions replaced by ``pass``."""
    lines_to_remove, start_lines = _assertion_removal_lines(tree, set(assertions_to_remove))
    result_lines: list[str] = []
    for i, line in enumerate(refined_test.split("\n"), 1):
        if i not in lines_to_remove:
            result_lines.append(line)
        elif i in start_lines:
            indent = len(line) - len(line.lstrip())
            result_lines.append(" " * indent + "pass")
        # else: a continuation line of a multi-line assert -> drop it
    return "\n".join(result_lines)


class _AssertionAnalysis(NamedTuple):
    """Aggregated result of per-assertion mutation analysis."""

    to_remove: list[int]
    per_test: dict[int, int]
    suite_level: dict[int, int]
    baseline_killed: set[int]
    suite_baseline_killed: set[int]


def _evaluate_inferred(
    refined_test: str,
    refined_tree: ast.Module,
    inferred_indices: list[int],
    mutants: list[tuple[types.ModuleType, Any]],
    *,
    module_name: str,
    other_tests_in_suite: list[str] | None,
) -> _AssertionAnalysis:
    """Run per-assertion mutation analysis and return the aggregated result."""
    baseline_killed = killed_set(refined_test, mutants, module_name)

    suite_baseline_killed: set[int] = set()
    if other_tests_in_suite:
        for other_test in other_tests_in_suite:
            suite_baseline_killed |= killed_set(other_test, mutants, module_name)

    assertions_to_remove: list[int] = []
    per_test_contributions: dict[int, int] = {}
    suite_level_contributions: dict[int, int] = {}

    for assert_idx in inferred_indices:
        without_tree = _remove_assertion_by_index(refined_tree, assert_idx)
        without_killed = killed_set(ast.unparse(without_tree), mutants, module_name)

        additional_kills = baseline_killed - without_killed
        per_test_contributions[assert_idx] = len(additional_kills)

        if other_tests_in_suite:
            suite_level_contributions[assert_idx] = len(additional_kills - suite_baseline_killed)
        else:
            suite_level_contributions[assert_idx] = len(additional_kills)

        if not additional_kills:
            assertions_to_remove.append(assert_idx)

    return _AssertionAnalysis(
        to_remove=assertions_to_remove,
        per_test=per_test_contributions,
        suite_level=suite_level_contributions,
        baseline_killed=baseline_killed,
        suite_baseline_killed=suite_baseline_killed,
    )


def filter_vacuous_assertions(
    original_test: str,
    refined_test: str,
    module_under_test: types.ModuleType | None,
    max_mutants: int = 10,
    other_tests_in_suite: list[str] | None = None,
    *,
    subject_properties: SubjectProperties | None = None,
    covered_lines: set[int] | None = None,
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
        module_under_test: The module object to mutate.
        max_mutants: Maximum mutants to generate (default: 10).
        other_tests_in_suite: Optional list of other test code strings in the suite
            for computing suite-level redundancy metrics.
        subject_properties: Optional SubjectProperties for native instrumentation coverage.
        covered_lines: Optional pre-computed covered lines in the SUT.

    Returns:
        Tuple of ``(filtered_test_code, statistics_dict)``.
        Statistics include both per_test_contributions and suite_level_contributions.
    """
    # Step 1: Identify inferred (LLM-added) assertions.
    tracker = AssertionTracker(original_test, refined_test)
    inferred = tracker.inferred_assertions
    if not inferred:
        return refined_test, _vacuous_stats(0)

    # Step 2: Parse SUT source and generate mutants.
    if not module_under_test or not hasattr(module_under_test, "__file__"):
        return refined_test, _vacuous_stats(len(inferred), error="module source not available")

    if covered_lines is None:
        try:
            covered_lines = get_covered_lines(
                refined_test, module_under_test, subject_properties
            ) | get_covered_lines(original_test, module_under_test, subject_properties)
        except Exception:  # noqa: BLE001
            covered_lines = None

    mutants, mutant_error = create_mutants(
        module_under_test, max_mutants, covered_lines=covered_lines
    )
    if mutant_error is not None:
        return refined_test, _vacuous_stats(len(inferred), error=mutant_error)
    if not mutants:
        return refined_test, _vacuous_stats(len(inferred))

    return filter_vacuous_assertions_with_mutants(
        original_test,
        refined_test,
        mutants,
        module_under_test.__name__,
        other_tests_in_suite=other_tests_in_suite,
    )


def filter_vacuous_assertions_with_mutants(
    original_test: str,
    refined_test: str,
    mutants: list[tuple[types.ModuleType, Any]],
    module_name: str,
    *,
    other_tests_in_suite: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Filter vacuous assertions against an already generated mutant set.

    Same criterion as :func:`filter_vacuous_assertions`, but the caller supplies
    the mutants (e.g. the surviving mutants a strengthening prompt targeted).

    Args:
        original_test: The test before the assertions were added.
        refined_test: The test with the added assertions.
        mutants: The mutants to analyse against.
        module_name: Name of the module under test.
        other_tests_in_suite: Optional other tests for suite-level metrics.

    Returns:
        Tuple of ``(filtered_test_code, statistics_dict)``.
    """
    inferred = AssertionTracker(original_test, refined_test).inferred_assertions
    if not inferred:
        return refined_test, _vacuous_stats(0, mutants_generated=len(mutants))

    # Step 3: Map inferred assertions to their indices in the refined test.
    try:
        refined_tree = ast.parse(refined_test)
    except SyntaxError as e:
        return refined_test, _vacuous_stats(
            len(inferred), mutants_generated=len(mutants), error=str(e)
        )

    all_asserts = _index_all_assertions(refined_tree)
    inferred_set = set(inferred)
    inferred_indices = [i for i, a in enumerate(all_asserts) if a in inferred_set]
    if not inferred_indices:
        return refined_test, _vacuous_stats(len(inferred), mutants_generated=len(mutants))

    # Step 4: Per-assertion mutation analysis.
    analysis = _evaluate_inferred(
        refined_test,
        refined_tree,
        inferred_indices,
        mutants,
        module_name=module_name,
        other_tests_in_suite=other_tests_in_suite,
    )

    # Step 5: Build the filtered test (text-based to preserve comments).
    filtered_test = (
        _build_filtered_test(refined_test, refined_tree, analysis.to_remove)
        if analysis.to_remove
        else refined_test
    )

    stats: dict[str, Any] = {
        "inferred_assertions": len(inferred),
        "mutants_generated": len(mutants),
        "mutants_killed_total": len(analysis.baseline_killed),
        "assertions_kept": len(inferred_indices) - len(analysis.to_remove),
        "assertions_removed": len(analysis.to_remove),
        "per_test_contributions": analysis.per_test,
        "suite_level_contributions": analysis.suite_level,
        "suite_baseline_size": len(analysis.suite_baseline_killed) if other_tests_in_suite else 0,
    }

    if analysis.per_test:
        stats["avg_per_test_contribution"] = sum(analysis.per_test.values()) / len(
            analysis.per_test
        )
        stats["avg_suite_level_contribution"] = sum(analysis.suite_level.values()) / len(
            analysis.suite_level
        )

    return filtered_test, stats


def get_surviving_mutants(
    test_code: str,
    module_under_test: types.ModuleType | None,
    max_mutants: int = 10,
    *,
    subject_properties: SubjectProperties | None = None,
    covered_lines: set[int] | None = None,
) -> list[tuple[types.ModuleType, Any]]:
    """Return the list of mutants that survived (were not killed by) the test code.

    Returns:
        List of tuples of (mutant_module, mutations) for surviving mutants.
    """
    if not module_under_test or not hasattr(module_under_test, "__file__"):
        return []

    if covered_lines is None:
        try:
            covered_lines = get_covered_lines(test_code, module_under_test, subject_properties)
        except Exception:  # noqa: BLE001
            covered_lines = None

    mutants, mutant_error = create_mutants(
        module_under_test, max_mutants, covered_lines=covered_lines
    )
    if mutant_error is not None or not mutants:
        return []

    module_name = module_under_test.__name__
    killed_indices = killed_set(test_code, mutants, module_name)

    survivors = []
    for idx, mutant in enumerate(mutants):
        mutant_module, _mutations = mutant
        # Mutants that failed to build (``mutant_module is None``) are not real
        # survivors; ``killed_set`` skips them, so exclude them explicitly here.
        if mutant_module is not None and idx not in killed_indices:
            survivors.append(mutant)
    return survivors


class _MutantOutcome(enum.Enum):
    """The result of running the refined suite against one mutant."""

    KILLED = enum.auto()
    SURVIVED = enum.auto()
    TIMED_OUT = enum.auto()
    UNCHECKED = enum.auto()
    """The time budget ran out before every test was run against the mutant."""


def _outcome_signature(execution: TestExecution) -> str | None:
    """Return the type of exception a test raised, or *None* if it completed.

    ``xfail`` markers are deliberately ignored: like the assertion generator, a
    mutant is killed when a test raises differently than on the original module.
    """
    if execution.error is None:
        return None
    error_type = type(execution.error)
    return f"{error_type.__module__}.{error_type.__qualname__}"


def _evaluate_single_mutant(  # noqa: PLR0917
    test_sources: list[str],
    original_signatures: list[str | None],
    module_under_test: types.ModuleType,
    mutant_module: types.ModuleType,
    module_provider: ModuleProvider,
    budget_exceeded: Callable[[], bool],
) -> _MutantOutcome:
    """Evaluate a single mutant against test sources.

    Mirrors the assertion generator's mutation analysis: a mutant that times out
    on any test counts as timed out, otherwise it is killed if any test raises
    differently than on the original module.  A mutant the time budget interrupts
    before every test ran is not counted at all.

    Returns:
        The outcome for the mutant.
    """
    module_name = module_under_test.__name__
    module_provider.clear_mutated_modules()
    module_provider.add_mutated_version(module_name, mutant_module)
    mutant_killed = False
    with module_provider.mutated_modules_installed():
        for idx, (test_source, original) in enumerate(
            zip(test_sources, original_signatures, strict=True)
        ):
            execution = execute_test(test_source, module_under_test)
            if execution.timed_out:
                return _MutantOutcome.TIMED_OUT
            if _outcome_signature(execution) != original:
                mutant_killed = True
            if idx < len(test_sources) - 1 and budget_exceeded():
                return _MutantOutcome.UNCHECKED
    return _MutantOutcome.KILLED if mutant_killed else _MutantOutcome.SURVIVED


def _checked_mutant_outcomes(
    controller: MutationController,
    test_sources: list[str],
    module_under_test: types.ModuleType,
    budget_exceeded: Callable[[], bool],
) -> list[_MutantOutcome]:
    """Run the test sources against each mutant until the time budget runs out.

    Returns:
        The outcome of every fully checked mutant.
    """
    # How each test behaves on the original module; a mutant is killed when a
    # test behaves differently (e.g., an xfail test raising another exception).
    original_signatures = [
        _outcome_signature(execute_test(source, module_under_test)) for source in test_sources
    ]
    module_provider = ModuleProvider()
    outcomes: list[_MutantOutcome] = []
    for mutant_module, _ in controller.create_mutants():
        if budget_exceeded():
            break
        if mutant_module is None:
            continue
        outcome = _evaluate_single_mutant(
            test_sources,
            original_signatures,
            module_under_test,
            mutant_module,
            module_provider,
            budget_exceeded,
        )
        if outcome is _MutantOutcome.UNCHECKED:
            # Like the assertion generator, drop a mutant the budget interrupted
            # instead of scoring it as a survivor.
            break
        outcomes.append(outcome)
    return outcomes


def evaluate_refined_suite_mutations(
    preamble: str,
    refined_tests: list[str],
    module_under_test: types.ModuleType | None,
    *,
    maximum_time: float | None = None,
) -> dict[str, Any]:
    """Run mutation analysis on the final refined test suite.

    Args:
        preamble: Shared imports and preamble for the refined test file.
        refined_tests: List of test function sources.
        module_under_test: The SUT module.
        maximum_time: Optional maximum mutation budget in seconds.

    Returns:
        Dictionary containing post-refinement mutation metrics:
        - post_refinement_mutation_score: float | None
        - post_refinement_killed_mutants: int
        - post_refinement_checked_mutants: int
        - post_refinement_timed_out_mutants: int
        - post_refinement_created_mutants: int
    """
    empty_result = {
        "post_refinement_mutation_score": None,
        "post_refinement_killed_mutants": 0,
        "post_refinement_checked_mutants": 0,
        "post_refinement_timed_out_mutants": 0,
        "post_refinement_created_mutants": 0,
    }
    if not refined_tests or module_under_test is None:
        return empty_result

    try:
        controller = create_mutation_controller(module_under_test)
    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Could not create mutation controller for refined suite: %s", e)
        return empty_result

    num_created = controller.mutant_count()
    if num_created == 0:
        return {
            **empty_result,
            "post_refinement_mutation_score": 1.0,
        }

    test_sources = [f"{preamble}\n{func}" for func in refined_tests]
    start_time = time.monotonic()
    max_time = (
        maximum_time
        if maximum_time is not None
        else config.configuration.test_case_output.maximum_mutation_time
    )

    def budget_exceeded() -> bool:
        return max_time >= 0 and time.monotonic() - start_time >= max_time

    outcomes = _checked_mutant_outcomes(
        controller, test_sources, module_under_test, budget_exceeded
    )
    if budget_exceeded():
        _LOGGER.info(
            "Post-refinement mutation budget of %ss exceeded; checked %i of %i mutant(s).",
            max_time,
            len(outcomes),
            num_created,
        )
    num_checked = len(outcomes)
    killed_mutants = outcomes.count(_MutantOutcome.KILLED)
    timeout_mutants = outcomes.count(_MutantOutcome.TIMED_OUT)

    metrics = MutationMetrics(
        num_created_mutants=num_checked,
        num_killed_mutants=killed_mutants,
        num_timeout_mutants=timeout_mutants,
    )
    score = compute_reported_mutation_score(metrics, num_created)

    return {
        "post_refinement_mutation_score": score,
        "post_refinement_killed_mutants": killed_mutants,
        "post_refinement_checked_mutants": num_checked,
        "post_refinement_timed_out_mutants": timeout_mutants,
        "post_refinement_created_mutants": num_created,
    }
