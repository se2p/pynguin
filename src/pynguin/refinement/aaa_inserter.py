"""
Insert AAA (Arrange-Act-Assert) markers programmatically into refined test code.

This module provides functionality to insert # Arrange, # Act, and # Assert
comment markers into test code based on the focal method line number identified
by the AST analyzer. This ensures AAA structure is guaranteed in the output
regardless of whether the LLM included the markers.
"""

import ast
from typing import Optional, Tuple


def insert_aaa_markers(
    test_code: str,
    focal_line_number: int,
    verbose: bool = True
) -> str:
    """
    Insert AAA structure markers (# Arrange, # Act, # Assert) into test code.
    
    Uses the focal method line number to determine where to place markers:
    - # Arrange: Before the focal method call
    - # Act: At the focal method call
    - # Assert: At the first assertion after focal method
    
    Args:
        test_code: The refined test code (may already have LLM-added markers)
        focal_line_number: Line number of the focal method call (from AST analyzer)
        verbose: Whether to print debug information
        
    Returns:
        Test code with AAA markers inserted (cleaned of duplicates if LLM already added them)
    """
    
    try:
        lines = test_code.split('\n')
        
        if verbose:
            print(f"[AAA-INSERT] Processing test with focal method at line {focal_line_number}")
            print(f"[AAA-INSERT] Total lines: {len(lines)}")
        
        # Find the test function definition
        func_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith('def test_'):
                func_start = i
                break
        
        if func_start is None:
            print("[AAA-INSERT] Warning: No test function found. Returning unchanged.")
            return test_code
        
        # Get function body start (first line after def and docstring)
        body_start = func_start + 1
        while body_start < len(lines):
            stripped = lines[body_start].strip()
            # Skip empty lines and docstring
            if stripped and not stripped.startswith('"""') and not stripped.startswith("'''"):
                break
            body_start += 1
        
        # Remove any existing AAA markers to avoid duplication
        lines = [line for line in lines if not line.strip() in ['# Arrange', '# Act', '# Assert']]
        
        # Re-index after removing existing markers
        focal_line_adjusted = focal_line_number
        
        # Identify sections
        arrange_lines = []
        act_line_idx = None
        assert_line_idx = None
        
        # Parse to find AST nodes and their line numbers
        tree = ast.parse(test_code)
        func_def = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                func_def = node
                break
        
        if func_def is None:
            print("[AAA-INSERT] Warning: Could not parse test function. Returning unchanged.")
            return test_code
        
        if verbose:
            print(f"[AAA-INSERT] Found test function: {func_def.name}")
            print(f"[AAA-INSERT] Function has {len(func_def.body)} statements")
        
        # Identify statement types and their indices
        first_assert_idx = None
        focal_call_idx = None
        
        for stmt_idx, stmt in enumerate(func_def.body):
            stmt_line = getattr(stmt, 'lineno', 0)
            
            # Check if this is an assertion
            if isinstance(stmt, ast.Assert):
                if first_assert_idx is None:
                    first_assert_idx = stmt_idx
            
            # Check if this statement contains the focal method call
            # (very approximate - just check if it's near the focal line)
            if abs(stmt_line - focal_line_number) <= 2:  # Within 2 lines of focal
                if not isinstance(stmt, ast.Assert):  # It's not an assertion itself
                    focal_call_idx = stmt_idx
        
        if verbose:
            print(f"[AAA-INSERT] Focal call at statement index: {focal_call_idx}")
            print(f"[AAA-INSERT] First assert at statement index: {first_assert_idx}")
        
        # Build new function body with AAA markers
        new_func_body = []
        
        # Add # Arrange marker before any setup code
        if func_def.body:
            new_func_body.append(("# Arrange", True))  # (line, is_marker)
        
        # Process each statement
        for stmt_idx, stmt in enumerate(func_def.body):
            # Add # Act marker before focal method call
            if stmt_idx == focal_call_idx:
                new_func_body.append(("# Act", True))
            
            # Add # Assert marker before first assertion
            if stmt_idx == first_assert_idx:
                new_func_body.append(("# Assert", True))
            
            # Add the statement itself
            stmt_code = ast.unparse(stmt)
            new_func_body.append((stmt_code, False))
        
        if verbose:
            print(f"[AAA-INSERT] AAA structure: {len(new_func_body)} lines")
        
        # Reconstruct the function
        import_lines = []
        func_start_line = None
        for i, line in enumerate(lines):
            if line.strip().startswith('def test_'):
                func_start_line = i
                break
            import_lines.append(line)
        
        # Build the new test code
        new_code_lines = import_lines.copy()
        
        # Get function signature and docstring
        func_sig = f"def {func_def.name}():"
        if func_def.body and isinstance(func_def.body[0], ast.Expr) and isinstance(func_def.body[0].value, ast.Constant):
            # Has docstring
            docstring = func_def.body[0].value.value
            new_code_lines.append(func_sig)
            new_code_lines.append(f'    """{docstring}"""')
            
            # Add AAA-structured body (skip first node which is docstring)
            for content, is_marker in new_func_body[1:]:  # Skip first "# Arrange"
                if is_marker:
                    new_code_lines.append(f"    {content}")
                else:
                    # Indent the statement properly
                    for line in content.split('\n'):
                        if line.strip():
                            new_code_lines.append(f"    {line}")
        else:
            # No docstring
            new_code_lines.append(func_sig)
            for content, is_marker in new_func_body:
                if is_marker:
                    new_code_lines.append(f"    {content}")
                else:
                    for line in content.split('\n'):
                        if line.strip():
                            new_code_lines.append(f"    {line}")
        
        result = '\n'.join(new_code_lines)
        
        if verbose:
            print(f"[AAA-INSERT] Successfully inserted AAA markers")
        
        return result
        
    except Exception as e:
        print(f"[AAA-INSERT] Error during marker insertion: {e}")
        print(f"[AAA-INSERT] Returning original test code unchanged")
        return test_code


def insert_aaa_markers_simple(
    test_code: str,
    focal_line_number: int,
    verbose: bool = True
) -> str:
    """
    Simpler version: Just insert AAA comments at appropriate positions.
    
    This version doesn't try to reparse with AST, just inserts comments
    at strategic points based on line numbers.
    
    Args:
        test_code: The refined test code
        focal_line_number: Line number of the focal method call
        verbose: Whether to print debug information
        
    Returns:
        Test code with AAA markers inserted
    """
    
    try:
        lines = test_code.split('\n')
        
        # Remove existing AAA markers first
        lines = [line for line in lines if line.strip() not in ['# Arrange', '# Act', '# Assert']]
        
        # Find function body start
        func_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith('def test_'):
                func_start = i
                break
        
        if func_start is None:
            print("[AAA-SIMPLE] No test function found")
            return test_code
        
        # Find actual body start (after def line)
        body_start = func_start + 1
        while body_start < len(lines) and (not lines[body_start].strip() or lines[body_start].strip().startswith('"""')):
            body_start += 1
        
        if body_start >= len(lines):
            print("[AAA-SIMPLE] Could not find function body")
            return test_code
        
        if verbose:
            print(f"[AAA-SIMPLE] Function starts at line {func_start}")
            print(f"[AAA-SIMPLE] Body starts at line {body_start}")
            print(f"[AAA-SIMPLE] Focal method at line {focal_line_number}")
        
        # Find indices in the modified lines list
        # We need to find where the focal method call is
        focal_idx = None
        first_assert_idx = None
        
        for i in range(body_start, len(lines)):
            line_lower = lines[i].lower()
            
            # Look for assert statements
            if line_lower.strip().startswith('assert'):
                if first_assert_idx is None:
                    first_assert_idx = i
            
            # Approximate: if line is roughly at focal_line_number, mark as focal
            # (This is approximate since we removed markers and counts may shift)
            # For now, use: focal is between arrange and first assert
        
        # If we found an assert, focal should be before it
        if first_assert_idx is not None:
            focal_idx = first_assert_idx - 1
            while focal_idx > body_start and lines[focal_idx].strip() == '':
                focal_idx -= 1
        else:
            # No assertion found - use all lines as act section
            # Find the last meaningful line
            focal_idx = len(lines) - 1
            while focal_idx > body_start and lines[focal_idx].strip() == '':
                focal_idx -= 1
        
        if verbose:
            print(f"[AAA-SIMPLE] Focal call approx. at index {focal_idx}")
            print(f"[AAA-SIMPLE] First assert approx. at index {first_assert_idx}")
        
        # Build new lines with markers
        new_lines = lines[:body_start]  # Imports + function signature + docstring
        
        # Always add arrange marker
        new_lines.append("    # Arrange")
        
        # Add arrange section (everything before focal)
        for i in range(body_start, focal_idx):
            new_lines.append(lines[i])
        
        # Add act marker and focal call
        if focal_idx < len(lines) and focal_idx >= body_start:
            new_lines.append("    # Act")
            new_lines.append(lines[focal_idx])
        
        # Add assert marker and assertions (if any)
        if first_assert_idx is not None and first_assert_idx < len(lines):
            # Only add Assert marker if there are actual assertions
            new_lines.append("    # Assert")
            for i in range(first_assert_idx, len(lines)):
                new_lines.append(lines[i])
        else:
            # No assertions - just add any remaining lines (shouldn't happen normally)
            for i in range(focal_idx + 1, len(lines)):
                if lines[i].strip():
                    new_lines.append(lines[i])
        
        result = '\n'.join(new_lines)
        
        if verbose:
            print(f"[AAA-SIMPLE] Successfully inserted AAA markers")
        
        return result
        
    except Exception as e:
        print(f"[AAA-SIMPLE] Error during marker insertion: {e}")
        return test_code


if __name__ == "__main__":
    # Test with an example
    example_test = '''import pytest
import platform as module_0
import ansible.module_utils.facts.ansible_collector as module_1

def test_ansible_fact_collection_with_machine_info():
    """Verify that the AnsibleFactCollector collects facts using the machine information."""
    machine_info = module_0.machine()
    ansible_fact_collector = module_1.AnsibleFactCollector(machine_info, filter_spec=machine_info)
    collected_facts = {}
    ansible_fact_collector.collect_with_namespace(collected_facts=collected_facts)
    assert isinstance(collected_facts, dict), 'Collected facts should be a dictionary.'
'''
    
    print("=" * 80)
    print("ORIGINAL TEST")
    print("=" * 80)
    print(example_test)
    
    print("\n" + "=" * 80)
    print("WITH AAA MARKERS (SIMPLE VERSION)")
    print("=" * 80)
    
    # Focal method is at line 8 (the .collect_with_namespace call)
    result = insert_aaa_markers_simple(example_test, focal_line_number=8, verbose=True)
    print(result)
    
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    # Check if markers are present
    if "# Arrange" in result:
        print("✅ # Arrange marker present")
    else:
        print("❌ # Arrange marker missing")
    
    if "# Act" in result:
        print("✅ # Act marker present")
    else:
        print("❌ # Act marker missing")
    
    if "# Assert" in result:
        print("✅ # Assert marker present")
    else:
        print("❌ # Assert marker missing")
