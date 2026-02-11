"""
Mutation Testing Integration for Assertion Filtering

This module provides mutation testing capabilities to validate assertion quality
during test refinement.  It uses Pynguin's MutationController to generate
actual mutants of the SUT, runs the test against each mutant, and keeps only
assertions that successfully kill at least 30 % of mutants.

Key Functions:
- filter_vacuous_assertions(): Main entry point for assertion filtering

Integration Point: Called after LLM generates assertions (Stage 2C) and before
the repair loop (Stage 3).
"""

from __future__ import annotations

import ast
import logging
import types
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


@dataclass
class MutationResult:
    """Result of running a test against mutants.
    
    Attributes:
        mutants_killed: Number of mutants detected by the test
        mutants_survived: Number of mutants that passed undetected
        mutants_total: Total number of mutants generated
        mutation_score: Percentage of mutants killed (0.0 to 1.0)
        timeout: Whether mutation testing timed out
        error: Error message if mutation testing failed
    """
    mutants_killed: int = 0
    mutants_survived: int = 0
    mutants_total: int = 0
    mutation_score: float = 0.0
    timeout: bool = False
    error: str | None = None


class AssertionTracker:
    """
    Tracks which assertions were added by the LLM vs. present in original test.
    
    This is critical for filtering: we only want to validate NEW assertions,
    not the original Pynguin-generated ones.
    """
    
    def __init__(self, original_test: str, refined_test: str):
        """
        Initialize tracker by parsing both test versions.
        
        Args:
            original_test: Original Pynguin-generated test code
            refined_test: Test code after LLM refinement
        """
        self.original_assertions = self._extract_assertions(original_test)
        self.refined_assertions = self._extract_assertions(refined_test)
        self.inferred_assertions = self._identify_new_assertions()
    
    def _extract_assertions(self, test_code: str) -> list[str]:
        """
        Extract all assertion statements from test code.
        
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
        except Exception as e:
            _LOGGER.warning("Could not parse test for assertions: %s", e)
        return assertions
    
    def _identify_new_assertions(self) -> list[str]:
        """
        Identify assertions that were added during refinement.
        
        Returns only assertions present in refined but not in original.
        """
        original_set = set(self.original_assertions)
        refined_set = set(self.refined_assertions)
        new_assertions = refined_set - original_set
        return list(new_assertions)
    
    def is_inferred_assertion(self, assertion_line: str) -> bool:
        """
        Check if a specific assertion was added by the LLM.
        
        Args:
            assertion_line: The assertion statement to check
            
        Returns:
            True if this is a new assertion, False if it was in original
        """
        try:
            tree = ast.parse(assertion_line)
            if tree.body and isinstance(tree.body[0], ast.Expr):
                normalized = ast.unparse(tree.body[0].value)
            else:
                normalized = assertion_line.strip()
            
            return normalized in self.inferred_assertions
        except Exception:
            return assertion_line.strip() in self.inferred_assertions


def filter_vacuous_assertions(
    original_test: str,
    refined_test: str,
    focal_method: str,
    module_under_test: types.ModuleType | None,
    module_path: str,
    max_mutants: int = 10
) -> tuple[str, dict[str, Any]]:
    """
    Filter vacuous assertions using real mutation execution.
    
    Uses Pynguin's MutationController to generate actual mutants of the SUT,
    runs the test against each mutant, and keeps only assertions that
    successfully kill at least 30 % of mutants.
    
    Args:
        original_test: Original Pynguin-generated test
        refined_test: Test after LLM assertion generation
        focal_method: Name of the method being tested
        module_under_test: The module object to mutate
        module_path: Path to the module source file
        max_mutants: Maximum mutants to generate (default: 10)
    
    Returns:
        Tuple of (filtered_test_code, statistics_dict)
    """
    print("\n[MUTATION-FILTER] Starting mutation-based assertion filtering...")
    print("[MUTATION-FILTER] Using Pynguin's MutationController for mutation execution")
    
    # Import Pynguin's mutation infrastructure
    try:
        from pynguin.assertion.mutation_analysis.controller import MutationController
        from pynguin.assertion.mutation_analysis.mutators import FirstOrderMutator
        from pynguin.assertion.mutation_analysis.operators import (
            ArithmeticOperatorReplacement,
            RelationalOperatorReplacement,
            LogicalOperatorReplacement,
            ConstantReplacement,
        )
        from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
    except ImportError as e:
        print(f"[MUTATION-FILTER] ERROR: Could not import Pynguin mutation infrastructure: {e}")
        print("[MUTATION-FILTER] Keeping all assertions (mutation infrastructure unavailable)")
        return refined_test, {
            "inferred_assertions": 0,
            "mutants_generated": 0,
            "mutants_killed": 0,
            "mutation_score": 0.0,
            "assertions_kept": 0,
            "assertions_removed": 0,
            "error": str(e),
        }
    
    # Step 1: Track which assertions are new
    tracker = AssertionTracker(original_test, refined_test)
    
    if not tracker.inferred_assertions:
        print("[MUTATION-FILTER] No new assertions detected. Returning original.")
        return refined_test, {
            "inferred_assertions": 0,
            "mutants_generated": 0,
            "mutants_killed": 0,
            "mutation_score": 0.0,
            "assertions_kept": 0,
            "assertions_removed": 0
        }
    
    print(f"[MUTATION-FILTER] Found {len(tracker.inferred_assertions)} new assertions to validate")
    
    # Step 2: Read and parse SUT source code
    if not module_under_test or not hasattr(module_under_test, '__file__'):
        print("[MUTATION-FILTER] WARNING: Module source not available. Keeping all assertions.")
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "mutants_killed": 0,
            "mutation_score": 0.0,
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
        print(f"[MUTATION-FILTER] Parsed SUT source: {sut_path.name}")
    except Exception as e:
        print(f"[MUTATION-FILTER] ERROR: Could not read SUT source: {e}")
        print("[MUTATION-FILTER] Keeping all assertions (SUT source unavailable)")
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "mutants_killed": 0,
            "mutation_score": 0.0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0,
            "error": str(e),
        }
    
    # Step 3: Create mutants using Pynguin's MutationController
    # Use a subset of operators for speed (comparison, arithmetic, boolean)
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
        module=module_under_test
    )
    
    # Count available mutants (don't generate more than max_mutants)
    total_mutants = min(controller.mutant_count(), max_mutants)
    
    if total_mutants == 0:
        print("[MUTATION-FILTER] No mutants could be generated. Keeping all assertions.")
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "mutants_killed": 0,
            "mutation_score": 0.0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0
        }
    
    print(f"[MUTATION-FILTER] Generated {total_mutants} mutants for SUT")
    
    # Step 4: Run test against mutants
    killed = 0
    tested = 0
    
    for mutant_module, mutations in controller.create_mutants():
        if tested >= max_mutants:
            break
        
        if mutant_module is None:
            continue
        
        tested += 1
        
        # Execute test against mutant
        try:
            # Create isolated namespace with mutant module
            test_globals = {
                "__builtins__": __builtins__,
                module_under_test.__name__: mutant_module,
            }
            
            # Add common test imports
            import pytest
            test_globals["pytest"] = pytest
            
            # Execute test
            exec(compile(ast.parse(refined_test), "<test>", "exec"), test_globals)
            
            # If we reach here, test passed = mutant survived
            _LOGGER.debug("Mutant %d survived (test passed)", tested)
            
        except AssertionError:
            # Test failed = mutant killed
            killed += 1
            _LOGGER.debug("Mutant %d killed (assertion failed)", tested)
        except Exception:
            # Other exceptions = mutant killed (test detected the fault)
            killed += 1
            _LOGGER.debug("Mutant %d killed (exception)", tested)
    
    # Step 5: Calculate mutation score and decide
    mutation_score = killed / tested if tested > 0 else 0.0
    
    print(f"[MUTATION-FILTER] Mutation testing complete: {killed}/{tested} killed ({mutation_score:.1%})")
    
    if mutation_score >= 0.3:  # Keep if killing ≥30% of mutants
        print(f"[MUTATION-FILTER] PASS: Assertions kill {mutation_score:.1%} of mutants")
        filtered_test = refined_test
        kept = len(tracker.inferred_assertions)
        removed = 0
    else:
        print(f"[MUTATION-FILTER] FAIL: Assertions only kill {mutation_score:.1%} of mutants")
        print("[MUTATION-FILTER] Reverting to original test")
        filtered_test = original_test
        kept = 0
        removed = len(tracker.inferred_assertions)
    
    stats = {
        "inferred_assertions": len(tracker.inferred_assertions),
        "mutants_generated": tested,
        "mutants_killed": killed,
        "mutation_score": mutation_score,
        "assertions_kept": kept,
        "assertions_removed": removed
    }
    
    print(f"[MUTATION-FILTER] Complete: kept {kept}, removed {removed} assertions")
    
    return filtered_test, stats


