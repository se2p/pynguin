import ast
import sys
import os

# Add project root to path so we can import the target module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pynguin.refinement.validator import run_test
from pynguin.refinement.llm_client import LLMClient
from pynguin.refinement.ast_analyzer import FocalMethodAnalyzer
from pynguin.refinement.sut_inspector import SUTInspector
from pynguin.refinement.mutation_analyzer import filter_vacuous_assertions
from pynguin.refinement.coverage_checker import check_coverage_preservation

class TestRefiner:
    def __init__(
        self, 
        api_key=None, 
        module_under_test=None, 
        project_root=None, 
        llm_base_url=None, 
        llm_model=None,
        llm_provider="ollama"  # "ollama" or "openai"
    ):
        """Initialize the test refinement pipeline.
        
        Args:
            api_key: OpenAI API key (only needed if llm_provider="openai")
            module_under_test: Module being tested
            project_root: Project root directory
            llm_base_url: Base URL for Ollama (only used if llm_provider="ollama")
            llm_model: Model name (e.g., "codellama:7b" for Ollama, "gpt-4o" for OpenAI)
            llm_provider: LLM provider - "ollama" (default, free) or "openai" (paid)
        """
        # Initialize LLM client with provider selection
        if llm_provider == "openai":
            self.llm_client = LLMClient(
                provider="openai",
                model_name=llm_model or "gpt-4o-mini",  # Default to cheaper model
                api_key=api_key
            )
        else:  # ollama (default)
            self.llm_client = LLMClient(
                provider="ollama",
                base_url=llm_base_url or "http://rhaegal.dimis.fim.uni-passau.de:15343",
                model_name=llm_model or "codellama:7b"
            )
        
        self.module_under_test = module_under_test
        self.project_root = project_root or os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.sut_inspector = SUTInspector(project_root=self.project_root)
    
    

    def structural_analysis(self, test_code: str):
        """
        Stage 1: Structural Analysis using AST-based focal method detection
        and SUT introspection for rich context extraction.
        
        This method:
        1. Uses FocalMethodAnalyzer to identify the focal method (the "Act" phase)
        2. Uses SUTInspector to extract docstrings and signatures
        3. Returns structured analysis with rich SUT context for LLM prompts
        
        Args:
            test_code: The raw test function code to analyze
            
        Returns:
            dict containing:
                - test_name: Name of the test function
                - focal_method_name: The identified focal method
                - focal_line_number: Line number of the focal method
                - sut_context: Formatted string with docstring/signature for LLM
                - arrange/act/assert: Code sections (for backward compatibility)
                - full_code: The complete test code
        """
        try:
            # Step 1: Use FocalMethodAnalyzer to identify the focal method
            analyzer = FocalMethodAnalyzer(test_code, test_code)
            focal_info = analyzer.analyze()
            
            if not focal_info:
                # Fallback to old heuristic if analyzer fails
                return self._fallback_structural_analysis(test_code)
            
            # Step 2: Use SUTInspector to extract SUT documentation
            sut_context = "Documentation unavailable."
            if focal_info.resolved_module_name:
                inspection_result = self.sut_inspector.inspect_method(
                    focal_info.resolved_module_name,
                    focal_info.focal_method_name.split('.')[-1] if '.' in focal_info.focal_method_name else focal_info.focal_method_name
                )
                sut_context = self.sut_inspector.format_context_string(inspection_result)
            
            # Step 3: Parse the test structure for AAA sections
            tree = ast.parse(test_code)
            func_def = next((node for node in tree.body if isinstance(node, ast.FunctionDef)), None)
            if not func_def:
                raise ValueError("No function definition found in the test code.")
            
            # Use focal_line_number to determine AAA boundaries
            focal_line = focal_info.focal_line_number
            
            # Split nodes based on focal method line
            arrange_nodes = []
            act_node = None
            assert_nodes = []
            
            for node in func_def.body:
                node_line = getattr(node, 'lineno', 0)
                if node_line < focal_line:
                    arrange_nodes.append(node)
                elif node_line == focal_line:
                    act_node = node
                else:
                    assert_nodes.append(node)
            
            # If act_node wasn't found on exact line, use the last arrange node
            if act_node is None and arrange_nodes:
                act_node = arrange_nodes.pop()
            
            return {
                "test_name": func_def.name,
                "focal_method_name": focal_info.focal_method_name,
                "focal_line_number": focal_info.focal_line_number,
                "sut_context": sut_context,
                "arrange": ast.unparse(ast.Module(body=arrange_nodes, type_ignores=[])) if arrange_nodes else "",
                "act": ast.unparse(ast.Module(body=[act_node], type_ignores=[])) if act_node else "",
                "assert": ast.unparse(ast.Module(body=assert_nodes, type_ignores=[])) if assert_nodes else "",
                "full_code": test_code
            }
            
        except Exception as e:
            print(f"Warning: Structural analysis failed: {e}")
            print("Falling back to legacy heuristic...")
            return self._fallback_structural_analysis(test_code)
    
    def _fallback_structural_analysis(self, test_code: str):
        """
        Legacy structural analysis using simple heuristic.
        Used as fallback when AST-based analysis fails.
        """
        try:
            tree = ast.parse(test_code)
            func_def = next((node for node in tree.body if isinstance(node, ast.FunctionDef)), None)
            if not func_def:
                raise ValueError("No function definition found in the test code.")

            # Find the 'Act' block (last non-assertion statement)
            act_index = -1
            for i, node in reversed(list(enumerate(func_def.body))):
                if not isinstance(node, ast.Assert):
                    act_index = i
                    break
            
            if act_index == -1:
                raise ValueError("Could not determine the 'Act' part of the test.")
            
            arrange_nodes = func_def.body[:act_index]
            act_node = func_def.body[act_index]
            assert_nodes = func_def.body[act_index+1:]

            return {
                "test_name": func_def.name,
                "focal_method_name": "unknown",
                "focal_line_number": 0,
                "sut_context": "Documentation unavailable.",
                "arrange": ast.unparse(ast.Module(body=arrange_nodes, type_ignores=[])) if arrange_nodes else "",
                "act": ast.unparse(ast.Module(body=[act_node], type_ignores=[])),
                "assert": ast.unparse(ast.Module(body=assert_nodes, type_ignores=[])) if assert_nodes else "",
                "full_code": test_code
            }
        except Exception as e:
            raise ValueError(f"AST Parsing failed: {e}")

    def refine_readability(self, analysis: dict):
        """
        Stage 2 & 3: Semantic Naming and Refactoring with SUT Context
        
        Uses the rich SUT context (docstrings, signatures) to guide the LLM
        in generating meaningful variable names and test structure.
        """
        sut_context = analysis.get('sut_context', 'Documentation unavailable.')
        focal_method = analysis.get('focal_method_name', 'unknown')
        
        prompt = f"""You are refactoring a Python unit test to improve readability while preserving its exact behavior.

**Method Documentation:**
{sut_context}

**Current Test:**
```python
{analysis['full_code']}
```

**Task:** Refactor this test following the Arrange-Act-Assert (AAA) pattern.

**CRITICAL - Preserve ALL import statements exactly as they appear in the original test.**

**Requirements:**
1. **Test Function Name:** Rename the test function to be descriptive of what it tests.If multiple tests exist, ensure each has a distinct name (e.g., test_equilateral_triangle, test_isosceles_with_negative, test_scalene_with_bytes)".
   - Use pattern: test_<behavior_being_tested>
   - Example: test_case_0() → test_triangle_with_equal_sides()
   - Example: test_case_1() → test_basket_adds_item_successfully()

2. **Semantic Naming:** Rename generic variables (bool_0, int_0, str_0) to meaningful names based on the method's purpose
   - Study the docstring to understand what the method does
   - Choose names that reflect the test scenario (e.g., equal_sides, different_sides, invalid_input)

3. **AAA Structure:** Add clear section markers:
   ```python
   # Arrange
   # ... setup code ...
   
   # Act
   # ... call to focal method: {focal_method} ...
   
   # Assert
   # ... verification code ...
   ```

4. **Preserve Behavior:** Keep the exact same logic, assertions, and control flow. Do NOT:
   - Change assertion conditions
   - Add new assertions
   - Remove existing code
   - Modify try/except blocks

5. **Docstring:** Add a brief docstring explaining what this test verifies

**Output Format:**
Return the complete refactored test WITH ALL IMPORT STATEMENTS from the original test.
Include imports at the top, then the test function.
No explanations, no markdown formatting."""
        
        return self.llm_client.generate_code(prompt)
    
    def generate_semantic_assertions(self, test_code: str, focal_method: str, sut_context: str) -> str:
        """
        Stage 2C: Generate strong, behavior-based assertions using LLM inference.
        
        Instead of executing code to capture runtime state (which risks locking in bugs),
        this method uses the LLM to infer expected behavior from the SUT documentation
        and generate semantically meaningful assertions.
        
        Args:
            test_code: The refactored test code with AAA structure
            focal_method: Name of the method being tested
            sut_context: Formatted SUT documentation (docstring + signature)
        
        Returns:
            Updated test code with strengthened assertions
        """
        if sut_context == "Documentation unavailable.":
            print("Warning: No SUT context available, skipping assertion strengthening.")
            return test_code
        
        prompt = f"""You are a test assertion expert. Your task is to add meaningful assertions to a unit test based on the method's documented behavior.

**Method Documentation:**
{sut_context}

**Current Test Code:**
```python
{test_code}
```

**CRITICAL: You MUST preserve ALL import statements from the input test code.**

**Your Task:**
Analyze the method's documentation and add appropriate assertions to verify its behavior.

**Critical Rules:**

1. **Understand the Method's Contract from Documentation:**
   - Read the docstring carefully to understand what the method returns
   - Identify the return type (string, int, dict, list, bool, etc.)
   - Note any special behaviors or edge cases mentioned

2. **Handling Expected Exceptions (Negative Testing):**
   
   **CRITICAL: Analyze the test inputs to determine if the test is a NEGATIVE test (expects failure).**
   
   **Indicators of Negative Tests:**
   - Variable names containing: `invalid_`, `none_`, `negative_`, `bad_`, `wrong_`, `empty_`
   - Values that are clearly invalid: `None`, `-1` (when positive expected), empty strings, mismatched types
   - Multiple `None` values passed as arguments
   - Type mismatches (e.g., passing string where int expected, or boolean where number expected)
   
   **For Negative Tests (expecting exceptions):**
   ```python
   # DO NOT use try/except with pytest.fail()
   # Instead, use pytest.raises() context manager
   
   # If documentation mentions specific exception (e.g., ValueError, TypeError):
   with pytest.raises(ValueError):
       method_under_test(invalid_input)
   
   # If no specific exception documented, use generic Exception:
   with pytest.raises(Exception):
       method_under_test(invalid_input)
   ```
   
   **Example - WRONG approach for negative test:**
   ```python
   # DON'T DO THIS for invalid inputs:
   try:
       triangle(None, None, None)
   except Exception:
       pytest.fail("Unexpected exception")
   ```
   
   **Example - CORRECT approach for negative test:**
   ```python
   # DO THIS instead:
   # Expecting failure due to invalid None inputs
   with pytest.raises(Exception):
       triangle(None, None, None)
   ```
   
   **For Positive Tests (expecting success):**
   - Remove try/except blocks entirely
   - Add proper assertions for the return value
   - Verify the method completes successfully

3. **Generate Appropriate Assertions Based on Return Type:**
   
   **IMPORTANT: Be conservative with assertions. Only assert what you can confidently verify from the documentation.**
   
   **For STRING returns:**
   ```python
   # Always check return type
   assert isinstance(result, str), "Should return a string"
   # Only add specific checks if the documentation clearly states them
   assert len(result) > 0, "Result should not be empty"
   # Avoid asserting exact values unless they are clearly documented
   ```
   
   **For INTEGER/FLOAT returns:**
   ```python
   assert isinstance(result, int), "Should return an integer"
   # Only add range checks if documented
   # assert result > 0, "Should be positive"  # only if doc explicitly says this
   ```
   
   **For BOOLEAN returns:**
   ```python
   assert isinstance(result, bool), "Should return a boolean"
   # assert result is True  # or False based on input
   ```
   
   **For DICT/LIST returns:**
   ```python
   assert isinstance(result, dict)
   assert "key" in result  # check documented keys
   assert len(result) == expected_size
   ```

4. **For the focal method '{focal_method}':**
   - Look at each call to this method in the test
   - Determine if it's a positive or negative test based on inputs
   - For positive tests: Store result and add assertions
   - For negative tests: Wrap in pytest.raises()

5. **Preserve ALL existing code:**
   - Keep the Arrange section unchanged
   - Keep the Act section unchanged (unless converting try/except to pytest.raises)
   - Keep variable names unchanged
   - Only add/modify assertions in the Assert section

**Example Transformation for POSITIVE Test:**

BEFORE:
```python
def test_triangle_valid():
    # Arrange
    side_a = 5
    side_b = 5
    side_c = 5
    
    # Act
    try:
        module_0.triangle(side_a, side_b, side_c)
    except Exception:
        pytest.fail("Unexpected exception")
```

AFTER (if docstring says "returns string describing triangle type"):
```python
def test_triangle_valid():
    # Arrange
    side_a = 5
    side_b = 5
    side_c = 5
    
    # Act
    result = module_0.triangle(side_a, side_b, side_c)
    
    # Assert
    assert isinstance(result, str), "Should return a string"
    assert "triangle" in result.lower(), "Result should mention triangle type"
```

**Example Transformation for NEGATIVE Test:**

BEFORE:
```python
def test_triangle_invalid():
    # Arrange
    invalid_side = None
    another_invalid = None
    
    # Act
    try:
        module_0.triangle(invalid_side, invalid_side, another_invalid)
    except Exception:
        pytest.fail("Unexpected exception")
```

AFTER:
```python
def test_triangle_invalid():
    # Arrange
    invalid_side = None
    another_invalid = None
    
    # Act & Assert
    # Expecting exception due to invalid None inputs
    with pytest.raises(Exception):
        module_0.triangle(invalid_side, invalid_side, another_invalid)
```

**Output Format:**
Return the complete test function with ALL import statements and ALL original code preserved.
Start with import statements, then the test function.
ONLY modify the Act/Assert sections to add proper assertions or pytest.raises() blocks.
Do NOT change function names, variable names, or the Arrange section.
No explanations, no markdown code blocks."""
        
        try:
            improved_code = self.llm_client.generate_code(prompt)
            
            # Verify imports are preserved - if not, fallback to original
            if 'import' not in improved_code:
                print("Warning: Generated code missing imports. Using original test.")
                return test_code
            
            return improved_code
        except Exception as e:
            print(f"Warning: Assertion generation failed: {e}")
            print("Returning original test code.")
            return test_code

    def repair_test_code(self, broken_code: str, error_message: str) -> str:
        """
        Stage 3: Repair Loop - Attempts to fix broken test code.
        
        Uses LLM to analyze the error and generate a corrected version.
        This method handles syntax errors, import errors, and failing assertions.
        
        Args:
            broken_code: The test code that failed validation
            error_message: The error traceback from run_test
            
        Returns:
            str: The repaired test code
        """
        prompt = f"""You are a Python test repair expert. A test has failed and needs to be fixed.

**Broken Test Code:**
```python
{broken_code}
```

**Error Traceback:**
```
{error_message}
```

**Your Task:**
Fix the test code to resolve the error. Common fixes include:
1. **Syntax Errors:** Fix indentation, parentheses, quotes, or invalid syntax
2. **Import Errors:** Add missing imports (e.g., `import pytest`, `from module import ...`)
3. **Name Errors:** Fix undefined variables or incorrect variable names
4. **Assertion Errors:** Replace vacuous assertions (e.g., `pytest.fail()`) with meaningful checks
5. **Type Errors:** Ensure correct types are passed to functions

**Requirements:**
- Output ONLY the corrected Python test function code
- Keep the same test function name
- Preserve the test's intent and behavior
- Fix ONLY what's broken - don't change working parts
- Do NOT include explanations, just the fixed code

**Corrected Test Code:**
```python"""

        try:
            repaired_code = self.llm_client.generate_code(prompt)
            return repaired_code
        except Exception as e:
            print(f"⚠️ Warning: Repair attempt failed: {e}")
            return broken_code  # Return original if repair fails

    def process_test_end_to_end(self, original_code: str, max_retries: int = 3) -> dict:
        """
        Complete end-to-end test refinement pipeline with iterative repair loop.
        
        This method implements the full 3-stage process:
        - Stage 1: Structural Analysis (focal method detection + SUT context)
        - Stage 2: Readability Refinement (AAA structure + semantic naming + function renaming)
        - Stage 3: Repair Loop (iterative fixing until test passes or max retries)
        
        Args:
            original_code: The raw test code to refine
            max_retries: Maximum number of repair attempts (default: 3)
            
        Returns:
            dict with keys:
                - success (bool): Whether refinement succeeded
                - final_code (str): The refined test code (if successful)
                - iterations (int): Number of repair iterations needed
                - error (str): Error message (if failed)
        """
        print("\n" + "="*80)
        print("[START] STARTING END-TO-END TEST REFINEMENT PIPELINE")
        print("="*80)
        
        # Level 1 Check: Verify Original Test Baseline
        print("\n[CHECK] Level 1 Check: Verifying Original Test Baseline")
        orig_passed, orig_msg = run_test(original_code, self.module_under_test)
        if not orig_passed:
            print(f"[WARNING] Original test failed. Refinement starting from unstable baseline.")
            print(f"Error: {orig_msg.splitlines()[0]}...") # Print first line of error
        else:
            print("[PASS] Original test passes. Baseline established.")

        try:
            # Stage 1: Structural Analysis
            print("\n[1] Stage 1: Structural Analysis")
            analysis_result = self.structural_analysis(original_code)
            print(f"[OK] Identified focal method: {analysis_result.get('focal_method_name', 'N/A')}")
            
            # Stage 2: Readability Refinement
            print("\n[2] Stage 2: Readability Refinement")
            readable_code = self.refine_readability(analysis_result)
            print("[OK] Applied AAA structure and semantic naming")
            
            print("\n[2.5] Stage 2.5: Semantic Assertion Generation")
            focal_method = analysis_result.get('focal_method_name', 'unknown')
            sut_context = analysis_result.get('sut_context', 'Documentation unavailable.')
            assertion_code = self.generate_semantic_assertions(readable_code, focal_method, sut_context)
            print("[OK] Generated semantic assertions")
            
            # Stage 2.6: Mutation-Based Assertion Filtering (Pynguin-Inspired)
            print("\n[2.6] Stage 2.6: Mutation-Based Assertion Filtering")
            try:
                # Get module path for mutation testing
                module_path = "unknown"
                if self.module_under_test:
                    module_path = getattr(self.module_under_test, '__file__', 'unknown')
                
                current_code, mutation_stats = filter_vacuous_assertions(
                    original_test=readable_code,  # Test before assertion generation
                    refined_test=assertion_code,   # Test after assertion generation
                    focal_method=focal_method,
                    module_under_test=self.module_under_test,
                    module_path=module_path,
                    max_mutants_per_assertion=10
                )
                
                if mutation_stats['assertions_removed'] > 0:
                    print(f"[FILTER] Removed {mutation_stats['assertions_removed']} vacuous assertions")
                else:
                    print(f"[OK] All {mutation_stats['assertions_kept']} assertions are non-vacuous")
            except Exception as e:
                print(f"[WARNING] Mutation filtering failed: {e}")
                print("[FALLBACK] Using assertions without mutation validation")
                current_code = assertion_code
                mutation_stats = {'error': str(e)}
            
            # Stage 3: Repair Loop
            print("\n[3] Stage 3: Iterative Repair Loop")
            for iteration in range(max_retries + 1):
                if iteration == 0:
                    print(f"[INIT] Initial validation attempt...")
                else:
                    print(f"[RETRY] Repair attempt {iteration}/{max_retries}...")
                
                # Validate current code
                passed, error_msg = run_test(current_code, self.module_under_test)
                
                if passed:
                    print(f"[PASS] Test PASSED after {iteration} repair iteration(s)")
                    
                    # Level 2: Coverage Preservation Check
                    coverage_passed, coverage_details = check_coverage_preservation(
                        original_test=original_code,  # Original Pynguin test
                        refined_test=current_code,  # Final refined test
                        module_under_test=self.module_under_test,
                        tolerance=0.0  # No coverage decrease allowed
                    )
                    
                    if not coverage_passed:
                        print("[COVERAGE] ✗ Coverage preservation failed - reverting to original")
                        print("="*80)
                        return {
                            'success': False,
                            'error': 'Coverage preservation check failed',
                            'coverage_details': coverage_details,
                            'iterations': iteration
                        }
                    
                    print("="*80)
                    return {
                        'success': True,
                        'final_code': current_code,
                        'iterations': iteration,
                        'mutation_stats': mutation_stats if 'mutation_stats' in locals() else {},
                        'coverage_details': coverage_details
                    }
                else:
                    # Test failed - determine error type
                    error_type = "Unknown Error"
                    if "SyntaxError" in error_msg:
                        error_type = "SyntaxError"
                    elif "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
                        error_type = "Import Error"
                    elif "NameError" in error_msg:
                        error_type = "Name Error"
                    elif "AssertionError" in error_msg:
                        error_type = "Assertion Error"
                    elif "TypeError" in error_msg:
                        error_type = "Type Error"
                    
                    print(f"[FAIL] Test FAILED: {error_type}")
                    
                    # If we have retries remaining, attempt repair
                    if iteration < max_retries:
                        print(f"[RETRY] Attempting repair ({iteration + 1}/{max_retries})...")
                        current_code = self.repair_test_code(current_code, error_msg)
                    else:
                        # Out of retries
                        print(f"[STOP] Max retries ({max_retries}) exhausted. Repair failed.")
                        print("="*80)
                        return {
                            'success': False,
                            'error': f"Failed after {max_retries} repair attempts. Last error: {error_type}",
                            'last_error_msg': error_msg,
                            'iterations': iteration
                        }
            
            # Should not reach here, but handle edge case
            return {
                'success': False,
                'error': 'Unexpected loop termination',
                'iterations': max_retries + 1
            }
            
        except Exception as e:
            print(f"[ERROR] Pipeline failed with exception: {e}")
            print("="*80)
            return {
                'success': False,
                'error': f"Pipeline exception: {str(e)}",
                'iterations': 0
            }
