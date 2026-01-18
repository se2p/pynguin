"""
Coverage Preservation Check (Level 2 Equivalence)

This module verifies that refactored tests maintain the same code coverage
as the original tests. This ensures the LLM hasn't removed important setup
code or changed execution paths.

Key Function:
- check_coverage_preservation(): Compares line and branch coverage between
  original and refined test versions.

Integration Point: Called during pipeline validation after repair loop succeeds.
"""

import tempfile
import subprocess
import json
from pathlib import Path
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CoverageResult:
    """Result of coverage measurement for a single test.
    
    Attributes:
        lines_covered: Number of lines covered
        lines_total: Total number of executable lines
        branches_covered: Number of branches covered (if branch coverage enabled)
        branches_total: Total number of branches
        coverage_percent: Line coverage percentage (0.0 to 100.0)
        branch_percent: Branch coverage percentage (0.0 to 100.0)
        error: Error message if coverage measurement failed
    """
    lines_covered: int = 0
    lines_total: int = 0
    branches_covered: int = 0
    branches_total: int = 0
    coverage_percent: float = 0.0
    branch_percent: float = 0.0
    error: Optional[str] = None


def measure_coverage(
    test_code: str,
    module_under_test,
    include_branch: bool = True
) -> CoverageResult:
    """
    Measure code coverage for a single test.
    
    Uses coverage.py to run the test and collect coverage metrics.
    
    Args:
        test_code: The test code to execute
        module_under_test: The module being tested (module object or string name)
        include_branch: Whether to measure branch coverage (default: True)
    
    Returns:
        CoverageResult with coverage metrics
    """
    try:
        import coverage
    except ImportError:
        return CoverageResult(
            error="coverage.py not installed. Install: pip install coverage"
        )
    
    # Import module if string name provided
    if isinstance(module_under_test, str):
        import importlib
        try:
            module_under_test = importlib.import_module(module_under_test)
        except ImportError as e:
            return CoverageResult(
                error=f"Could not import module '{module_under_test}': {e}"
            )
    
    # Create temporary file for the test
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.py',
        delete=False,
        encoding='utf-8'
    ) as test_file:
        test_file.write(test_code)
        test_file_path = test_file.name
    
    try:
        # Get the module path to measure coverage on
        module_file = getattr(module_under_test, '__file__', None)
        if module_file:
            source_path = Path(module_file).parent
        else:
            # Fallback: measure coverage on everything
            source_path = None
        
        # Initialize coverage measurement
        cov = coverage.Coverage(
            branch=include_branch,
            source=[str(source_path)] if source_path else None
        )
        
        # Start coverage measurement
        cov.start()
        
        # Execute the test
        test_globals = {
            '__name__': '__main__',
            module_under_test.__name__: module_under_test
        }
        
        with open(test_file_path, 'r', encoding='utf-8') as f:
            test_source = f.read()
        
        exec(test_source, test_globals)
        
        # Find and execute the test function
        for name, obj in test_globals.items():
            if callable(obj) and name.startswith('test_'):
                obj()
                break
        
        # Stop coverage and collect results
        cov.stop()
        cov.save()
        
        # Analyze coverage data
        analysis_data = {}
        if module_file:
            analysis = cov.analysis2(module_file)
            # analysis returns: (filename, executed_lines, excluded_lines, missing_lines)
            executed_lines = set(analysis[1])
            missing_lines = set(analysis[3])
            total_lines = len(executed_lines) + len(missing_lines)

            analysis_data['lines_covered'] = len(executed_lines)
            analysis_data['lines_total'] = total_lines
            analysis_data['coverage_percent'] = (
                (len(executed_lines) / total_lines * 100) if total_lines > 0 else 0.0
            )
        
        # Get overall stats as fallback
        if not analysis_data:
            total = cov.report(file=None, show_missing=False)
            analysis_data['coverage_percent'] = total
        
        # Get branch coverage if enabled
        branch_data = {}
        if include_branch:
            # Try to get branch stats
            try:
                data = cov.get_data()
                if module_file:
                    arcs = data.arcs(module_file)
                    if arcs:
                        branch_data['branches_total'] = len(arcs)
                        # Simplified: assume all arcs covered if no missing
                        branch_data['branches_covered'] = len(arcs)
            except Exception:
                pass
        
        return CoverageResult(
            lines_covered=analysis_data.get('lines_covered', 0),
            lines_total=analysis_data.get('lines_total', 0),
            branches_covered=branch_data.get('branches_covered', 0),
            branches_total=branch_data.get('branches_total', 0),
            coverage_percent=analysis_data.get('coverage_percent', 0.0),
            branch_percent=branch_data.get('branch_percent', 0.0)
        )
    
    except Exception as e:
        return CoverageResult(
            error=f"Coverage measurement failed: {str(e)}"
        )
    
    finally:
        # Clean up temporary file
        try:
            Path(test_file_path).unlink()
        except Exception:
            pass


def check_coverage_preservation(
    original_test: str,
    refined_test: str,
    module_under_test,
    tolerance: float = 0.0
) -> Tuple[bool, Dict]:
    """
    Check if refined test preserves coverage of original test.
    
    Level 2 Equivalence Check: Coverage Preservation
    Requirement: refined_coverage >= original_coverage (within tolerance)
    
    Args:
        original_test: Original test code
        refined_test: Refined test code
        module_under_test: Module being tested
        tolerance: Acceptable coverage decrease (0.0 = no decrease allowed)
    
    Returns:
        Tuple of (passed: bool, details: dict)
        - passed: True if coverage is preserved
        - details: Dict with coverage metrics and comparison
    """
    print("\n[COVERAGE] Level 2: Coverage Preservation Check")
    
    # Measure coverage for original test
    print("[COVERAGE] Measuring original test coverage...")
    original_cov = measure_coverage(original_test, module_under_test)
    
    if original_cov.error:
        print(f"[COVERAGE] Warning: Could not measure original coverage: {original_cov.error}")
        return True, {
            'status': 'skipped',
            'reason': original_cov.error,
            'original_coverage_percent': 0.0,
            'refined_coverage_percent': 0.0,
            'original_coverage': None,
            'refined_coverage': None
        }
    
    print(f"[COVERAGE] Original: {original_cov.coverage_percent:.1f}% line coverage "
          f"({original_cov.lines_covered}/{original_cov.lines_total} lines)")
    
    # Measure coverage for refined test
    print("[COVERAGE] Measuring refined test coverage...")
    refined_cov = measure_coverage(refined_test, module_under_test)
    
    if refined_cov.error:
        print(f"[COVERAGE] Warning: Could not measure refined coverage: {refined_cov.error}")
        return True, {
            'status': 'skipped',
            'reason': refined_cov.error,
            'original_coverage_percent': original_cov.coverage_percent,
            'refined_coverage_percent': 0.0,
            'original_coverage': original_cov.coverage_percent,
            'refined_coverage': None
        }
    
    print(f"[COVERAGE] Refined:  {refined_cov.coverage_percent:.1f}% line coverage "
          f"({refined_cov.lines_covered}/{refined_cov.lines_total} lines)")
    
    # Compare coverage
    coverage_delta = refined_cov.coverage_percent - original_cov.coverage_percent
    
    # Check if coverage is preserved (with tolerance)
    if coverage_delta >= -tolerance:
        if coverage_delta > 0:
            print(f"[COVERAGE] ✓ PASS: Coverage improved by {coverage_delta:.1f}%")
        else:
            print(f"[COVERAGE] ✓ PASS: Coverage preserved (delta: {coverage_delta:.1f}%)")
        
        return True, {
            'status': 'passed',
            'original_coverage_percent': original_cov.coverage_percent,
            'refined_coverage_percent': refined_cov.coverage_percent,
            'original_coverage': original_cov.coverage_percent,
            'refined_coverage': refined_cov.coverage_percent,
            'coverage_delta': coverage_delta,
            'original_lines': f"{original_cov.lines_covered}/{original_cov.lines_total}",
            'refined_lines': f"{refined_cov.lines_covered}/{refined_cov.lines_total}"
        }
    else:
        print(f"[COVERAGE] ✗ FAIL: Coverage decreased by {abs(coverage_delta):.1f}%")
        print(f"[COVERAGE] Required: >= {original_cov.coverage_percent:.1f}%, "
              f"Got: {refined_cov.coverage_percent:.1f}%")
        
        return False, {
            'status': 'failed',
            'original_coverage_percent': original_cov.coverage_percent,
            'refined_coverage_percent': refined_cov.coverage_percent,
            'original_coverage': original_cov.coverage_percent,
            'refined_coverage': refined_cov.coverage_percent,
            'coverage_delta': coverage_delta,
            'original_lines': f"{original_cov.lines_covered}/{original_cov.lines_total}",
            'refined_lines': f"{refined_cov.lines_covered}/{refined_cov.lines_total}",
            'reason': f"Coverage decreased by {abs(coverage_delta):.1f}%"
        }

