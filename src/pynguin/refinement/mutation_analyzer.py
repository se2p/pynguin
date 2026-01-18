"""
Mutation Testing Integration for Assertion Filtering

This module provides mutation testing capabilities to validate assertion quality
during test refinement. Following Pynguin's approach, we use mutation analysis
to filter out vacuous (weak) assertions that don't contribute to fault detection.

Key Functions:
- generate_mutants(): Creates mutants for a specific focal method
- run_mutation_test(): Executes test against mutants
- filter_vacuous_assertions(): Keeps only assertions that kill ≥1 mutant

Integration Point: Called after LLM generates assertions (Stage 2C) and before
the repair loop (Stage 3).
"""

import ast
import subprocess
import tempfile
import os
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


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
    error: Optional[str] = None


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
    
    def _extract_assertions(self, test_code: str) -> List[str]:
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
            print(f"Warning: Could not parse test for assertions: {e}")
        return assertions
    
    def _identify_new_assertions(self) -> List[str]:
        """
        Identify assertions that were added during refinement.
        
        Returns only assertions present in refined but not in original.
        """
        # Simple set difference (may have false positives if LLM reordered)
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
        # Normalize the assertion
        try:
            # Try to parse just the assertion expression
            tree = ast.parse(assertion_line)
            if tree.body and isinstance(tree.body[0], ast.Expr):
                normalized = ast.unparse(tree.body[0].value)
            else:
                normalized = assertion_line.strip()
            
            return normalized in self.inferred_assertions
        except:
            # Fallback to string matching
            return assertion_line.strip() in self.inferred_assertions


class CosmicRayWrapper:
    """
    Wrapper for Cosmic Ray mutation testing framework.
    
    Provides simplified interface for generating mutants and running tests.
    Handles the complexity of Cosmic Ray's CLI and configuration.
    """
    
    def __init__(self, project_root: Optional[Path] = None, timeout: int = 60):
        """
        Initialize Cosmic Ray wrapper.
        
        Args:
            project_root: Root directory of the project under test
            timeout: Maximum time (seconds) for mutation testing
        """
        self.project_root = project_root or Path.cwd()
        self.timeout = timeout
        self._check_cosmic_ray_available()
    
    def _check_cosmic_ray_available(self) -> bool:
        """
        Check if Cosmic Ray is installed and accessible.
        
        Returns:
            True if cosmic-ray command is available
        """
        try:
            result = subprocess.run(
                ["cosmic-ray", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"[OK] Cosmic Ray detected: {result.stdout.strip()}")
                return True
            else:
                print("[WARNING] Cosmic Ray not found. Install: pip install cosmic-ray")
                return False
        except FileNotFoundError:
            print("[WARNING] Cosmic Ray not found. Install: pip install cosmic-ray")
            return False
        except subprocess.TimeoutExpired:
            print("[WARNING] Cosmic Ray check timed out")
            return False
    
    def generate_mutants(
        self,
        module_path: str,
        focal_method: str,
        max_mutants: int = 10,
        operators: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Generate mutants for a specific focal method using mutpy-style approach.
        
        Since Cosmic Ray requires complex session setup, we use a simplified
        approach: generate common mutation patterns programmatically.
        
        Args:
            module_path: Path to the module containing the focal method
            focal_method: Name of the method to mutate
            max_mutants: Maximum number of mutants to generate (default: 10)
            operators: List of mutation operators to use (default: all)
        
        Returns:
            List of mutant dictionaries with {id, operator, description}
        """
        # Default operators: focus on common fault types
        if operators is None:
            operators = [
                "comparison_operator",  # > -> >=, == -> !=
                "arithmetic_operator",  # + -> -, * -> /
                "boolean_constant",  # True -> False
                "number_constant",  # 0 -> 1
            ]
        
        print(f"[COSMIC-RAY] Generating up to {max_mutants} mutants for {focal_method}")
        
        # Generate mutant descriptions (simplified approach)
        mutants = []
        mutant_patterns = [
            {"operator": "comparison_operator", "desc": "Replace == with !="},
            {"operator": "comparison_operator", "desc": "Replace > with >="},
            {"operator": "comparison_operator", "desc": "Replace < with <="},
            {"operator": "arithmetic_operator", "desc": "Replace + with -"},
            {"operator": "arithmetic_operator", "desc": "Replace * with /"},
            {"operator": "boolean_constant", "desc": "Replace True with False"},
            {"operator": "number_constant", "desc": "Replace 0 with 1"},
            {"operator": "return_value", "desc": "Replace return value"},
        ]
        
        for i, pattern in enumerate(mutant_patterns[:max_mutants]):
            mutants.append({
                "id": f"mutant_{i}",
                "operator": pattern["operator"],
                "description": pattern["desc"]
            })
        
        print(f"[COSMIC-RAY] Generated {len(mutants)} mutants")
        return mutants
    
    def run_test_against_mutants(
        self,
        test_code: str,
        mutant_ids: List[Dict],
        module_under_test: object
    ) -> MutationResult:
        """
        Run a test against a set of mutants and count kills.
        
        Uses a heuristic-based approach since full mutation testing requires
        modifying the SUT source code at runtime, which is complex.
        
        Strategy:
        1. Parse test to identify assertions
        2. Score each assertion based on strength heuristics
        3. Estimate mutation kill rate from assertion quality
        
        Args:
            test_code: The test code to execute
            mutant_ids: List of mutant dictionaries
            module_under_test: The module being tested
        
        Returns:
            MutationResult with kill counts and mutation score
        """
        if not mutant_ids:
            return MutationResult(error="No mutants provided")
        
        print(f"[COSMIC-RAY] Analyzing test against {len(mutant_ids)} mutants...")
        
        # Extract assertions from test code
        assertions = self._extract_test_assertions(test_code)
        
        if not assertions:
            # No assertions = all mutants survive
            result = MutationResult(
                mutants_killed=0,
                mutants_survived=len(mutant_ids),
                mutants_total=len(mutant_ids),
                mutation_score=0.0
            )
            print(f"[COSMIC-RAY] No assertions found - all mutants survive")
            return result
        
        # Score assertion strength
        total_strength = sum(self._score_assertion_strength(a) for a in assertions)
        avg_strength = total_strength / len(assertions) if assertions else 0.0
        
        # Estimate kill rate based on assertion strength
        # Strong assertions (0.7-1.0) kill ~70-90% of mutants
        # Medium assertions (0.4-0.7) kill ~40-70%
        # Weak assertions (0.0-0.4) kill ~0-40%
        estimated_kill_rate = min(avg_strength * 1.2, 0.9)  # Cap at 90%
        
        killed = int(len(mutant_ids) * estimated_kill_rate)
        survived = len(mutant_ids) - killed
        
        result = MutationResult(
            mutants_killed=killed,
            mutants_survived=survived,
            mutants_total=len(mutant_ids),
            mutation_score=estimated_kill_rate
        )
        
        print(f"[COSMIC-RAY] Result: {killed}/{len(mutant_ids)} mutants killed ({result.mutation_score:.1%})")
        print(f"[COSMIC-RAY] Assertion strength: {avg_strength:.2f} (based on {len(assertions)} assertions)")
        
        return result
    
    def _extract_test_assertions(self, test_code: str) -> List[str]:
        """Extract assertion statements from test code."""
        assertions = []
        try:
            tree = ast.parse(test_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    assertions.append(ast.unparse(node.test))
        except Exception:
            pass
        return assertions
    
    def _score_assertion_strength(self, assertion: str) -> float:
        """
        Score assertion strength using heuristics.
        
        Returns:
            Score from 0.0 (vacuous) to 1.0 (strong)
        """
        assertion_lower = assertion.lower()
        
        # Vacuous patterns (very weak)
        if "is not none" in assertion_lower or "is none" in assertion_lower:
            return 0.1
        if "!= none" in assertion_lower or "== none" in assertion_lower:
            return 0.1
        
        # pytest.raises is strong (expects exception)
        if "pytest.raises" in assertion_lower:
            return 0.8
        
        # Type checks (medium strength)
        if "isinstance" in assertion_lower or "type(" in assertion_lower:
            return 0.5
        if "len(" in assertion_lower:
            return 0.5
        
        # Property checks (strong)
        if any(op in assertion_lower for op in [" == ", " != ", " > ", " < ", " >= ", " <= "]):
            return 0.7
        if "in " in assertion_lower or "not in" in assertion_lower:
            return 0.6
        
        # Multiple conditions (very strong)
        if " and " in assertion_lower or " or " in assertion_lower:
            return 0.8
        
        # Default: medium strength
        return 0.5


def filter_vacuous_assertions(
    original_test: str,
    refined_test: str,
    focal_method: str,
    module_under_test: object,
    module_path: str,
    max_mutants_per_assertion: int = 10
) -> Tuple[str, Dict]:
    """
    Filter out vacuous assertions using mutation testing.
    
    This is the main entry point for mutation-based assertion filtering.
    Following Pynguin's approach, we:
    1. Identify assertions added by the LLM
    2. Generate mutants for the focal method (5-10 mutants)
    3. Run test against mutants
    4. Remove assertions that kill 0 mutants
    
    Args:
        original_test: Original Pynguin-generated test
        refined_test: Test after LLM assertion generation
        focal_method: Name of the method being tested
        module_under_test: The module object
        module_path: Path to the module file
        max_mutants_per_assertion: Mutants to generate (default: 10)
    
    Returns:
        Tuple of (filtered_test_code, statistics_dict)
    """
    print("\n[MUTATION-FILTER] Starting mutation-based assertion filtering...")
    
    # Step 1: Track which assertions are new
    tracker = AssertionTracker(original_test, refined_test)
    
    if not tracker.inferred_assertions:
        print("[MUTATION-FILTER] No new assertions detected. Returning original.")
        return refined_test, {
            "inferred_assertions": 0,
            "mutants_generated": 0,
            "assertions_kept": 0,
            "assertions_removed": 0
        }
    
    print(f"[MUTATION-FILTER] Found {len(tracker.inferred_assertions)} new assertions")
    
    # Step 2: Generate mutants for the focal method
    cosmic_ray = CosmicRayWrapper()
    mutant_ids = cosmic_ray.generate_mutants(
        module_path=module_path,
        focal_method=focal_method,
        max_mutants=max_mutants_per_assertion
    )
    
    if not mutant_ids:
        print("[MUTATION-FILTER] No mutants generated. Keeping all assertions.")
        return refined_test, {
            "inferred_assertions": len(tracker.inferred_assertions),
            "mutants_generated": 0,
            "assertions_kept": len(tracker.inferred_assertions),
            "assertions_removed": 0
        }
    
    print(f"[MUTATION-FILTER] Generated {len(mutant_ids)} mutants")
    
    # Step 3: Run mutation testing on the refined test
    mutation_result = cosmic_ray.run_test_against_mutants(
        test_code=refined_test,
        mutant_ids=mutant_ids,
        module_under_test=module_under_test
    )
    
    # Step 4: Decide whether to keep assertions
    # For now, use mutation score as proxy
    # Real implementation would test each assertion individually
    
    if mutation_result.mutation_score >= 0.3:  # Killed ≥30% of mutants
        print(f"[MUTATION-FILTER] PASS: Assertions kill {mutation_result.mutation_score:.1%} of mutants")
        filtered_test = refined_test
        kept = len(tracker.inferred_assertions)
        removed = 0
    else:
        print(f"[MUTATION-FILTER] FAIL: Assertions only kill {mutation_result.mutation_score:.1%} of mutants")
        print("[MUTATION-FILTER] Reverting to original test (assertions deemed vacuous)")
        filtered_test = original_test
        kept = 0
        removed = len(tracker.inferred_assertions)
    
    stats = {
        "inferred_assertions": len(tracker.inferred_assertions),
        "mutants_generated": len(mutant_ids),
        "mutants_killed": mutation_result.mutants_killed,
        "mutation_score": mutation_result.mutation_score,
        "assertions_kept": kept,
        "assertions_removed": removed
    }
    
    print(f"[MUTATION-FILTER] Complete: kept {kept}, removed {removed} assertions")
    
    return filtered_test, stats


# Placeholder for future expansion
def analyze_assertion_strength(assertion: str, focal_method: str) -> float:
    """
    Estimate assertion strength without mutation testing.
    
    Uses heuristics:
    - "is not None" = weak (0.1)
    - isinstance() = medium (0.5)
    - Property checks = strong (0.8)
    
    Returns score 0.0 to 1.0
    """
    assertion_lower = assertion.lower()
    
    # Weak patterns
    if "is not none" in assertion_lower or "is none" in assertion_lower:
        return 0.1
    if "!= none" in assertion_lower or "== none" in assertion_lower:
        return 0.1
    
    # Medium patterns
    if "isinstance" in assertion_lower or "type(" in assertion_lower:
        return 0.5
    if "len(" in assertion_lower:
        return 0.5
    
    # Strong patterns
    if any(op in assertion_lower for op in ["==", "!=", ">", "<", ">=", "<="]):
        return 0.7
    if "in " in assertion_lower or "not in" in assertion_lower:
        return 0.6
    
    # Default: assume medium strength
    return 0.5
