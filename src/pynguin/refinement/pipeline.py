#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Test refinement pipeline orchestrator."""

import ast
import re
from pathlib import Path
from typing import Any

from pynguin.refinement.aaa_inserter import insert_aaa_markers_simple
from pynguin.refinement.ast_analyzer import FocalMethodAnalyzer
from pynguin.refinement.coverage_checker import check_coverage_preservation
from pynguin.refinement.llm_client import LLMClient
from pynguin.refinement.mutation_analyzer import AssertionTracker, filter_vacuous_assertions
from pynguin.refinement.sut_inspector import SUTInspector
from pynguin.refinement.validator import run_test


def _restore_import_block(llm_code: str, original_code: str) -> str:
    """Replace LLM-generated imports with the original import block.

    The LLM often changes ``import test_subject.foo as module_0`` to
    ``from test_subject.foo import func_a, func_b`` and then uses bare
    ``func_a()`` calls.  If we let those modified imports through to
    ``run_test``, the bare calls pass validation — but ``refiner.py``
    later discards the LLM's imports and re-attaches the originals,
    producing a broken file where ``module_0.`` prefixes are missing.

    By restoring the original import block *before* validation, any
    bare-call errors are caught in the repair loop.

    This implementation preserves comments (including AAA markers) and
    formatting in the non-import portion of the LLM output by only
    removing top-level import *lines* identified via the AST while
    keeping the rest of the text intact.
    """
    try:
        orig_tree = ast.parse(original_code)
        llm_tree = ast.parse(llm_code)
    except SyntaxError:
        return llm_code  # can't parse → leave as-is for repair loop

    # Build the original import text
    orig_imports = [n for n in orig_tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not orig_imports:
        return llm_code

    orig_import_mod = ast.Module(body=list(orig_imports), type_ignores=[])
    orig_import_text = ast.unparse(orig_import_mod)

    # Find line numbers occupied by top-level imports in the LLM output
    import_lines: set[int] = set()
    for node in llm_tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

    if not import_lines:
        return llm_code  # no imports to replace

    # Keep every non-import line (preserves comments, AAA markers, etc.)
    llm_lines = llm_code.split("\n")
    remaining = [line for i, line in enumerate(llm_lines, 1) if i not in import_lines]

    # Trim leading blank lines
    while remaining and not remaining[0].strip():
        remaining.pop(0)

    if not remaining:
        return llm_code  # nothing useful from LLM

    return orig_import_text + "\n" + "\n".join(remaining)


def _safe_unparse(node: ast.expr) -> str | None:
    """Unparse an AST expression, returning ``None`` if it cannot be rendered."""
    try:
        return ast.unparse(node)
    except (ValueError, AttributeError, TypeError):
        return None


def _locate_inferred_assertion(
    tree: ast.Module, inferred_set: set[str], failing_line: int | None
) -> ast.Assert | None:
    """Find the inferred assertion to remove.

    Prefers the assertion at ``failing_line``; otherwise falls back to the
    first inferred assertion encountered.
    """
    first_inferred: ast.Assert | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        assertion_str = _safe_unparse(node.test)
        if assertion_str is None or assertion_str not in inferred_set:
            continue
        if first_inferred is None:
            first_inferred = node
        if failing_line is not None and node.lineno == failing_line:
            return node
    return first_inferred


def _remove_failing_inferred_assertion(
    current_code: str, original_code: str, error_msg: str
) -> tuple[str | None, str | None]:
    """Remove a failing inferred assertion from the test code.

    This implements the assertion-failure policy: if an LLM-inferred assertion
    fails, we discard it rather than asking the LLM to "fix" it (which could
    make the test vacuous).

    Uses the traceback in error_msg to identify the specific failing assertion
    by line number.  Falls back to the first inferred assertion if the line
    number cannot be matched.

    Args:
        current_code: The current test code with the failing assertion
        original_code: The original Pynguin-generated test (before LLM refinement)
        error_msg: The assertion error message / traceback from run_test

    Returns:
        Tuple of (modified_code, removed_assertion) or (None, None) if no
        inferred assertion could be identified/removed
    """
    tracker = AssertionTracker(original_code, current_code)

    if not tracker.inferred_assertions:
        return None, None

    try:
        tree = ast.parse(current_code)
    except SyntaxError:
        return None, None

    inferred_set = set(tracker.inferred_assertions)

    # Try to extract the failing line number from the traceback.
    # exec() uses "<string>" as the filename, so lines look like:
    #   File "<string>", line N, in test_func_name
    failing_line: int | None = None
    for m in re.finditer(r'File "<string>", line (\d+)', error_msg):
        failing_line = int(m.group(1))  # keep the last (innermost) match

    target_node = _locate_inferred_assertion(tree, inferred_set, failing_line)
    if target_node is None:
        return None, None

    assertion_str = _safe_unparse(target_node.test)
    if assertion_str is None:
        return None, None

    start_line = target_node.lineno  # 1-based
    end_line = target_node.end_lineno or target_node.lineno
    lines = current_code.split("\n")
    indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
    new_lines = [
        *lines[: start_line - 1],
        " " * indent + "pass",
        *lines[end_line:],
    ]
    return "\n".join(new_lines), assertion_str


def _classify_error(error_msg: str) -> str:
    """Classify a validation error message into a coarse error type."""
    if "SyntaxError" in error_msg:
        return "SyntaxError"
    if "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
        return "Import Error"
    if "NameError" in error_msg:
        return "Name Error"
    if "AssertionError" in error_msg:
        return "Assertion Error"
    if "TypeError" in error_msg:
        return "Type Error"
    return "Unknown Error"


class TestRefiner:
    """Orchestrates the end-to-end test refinement pipeline."""

    def __init__(
        self,
        api_key=None,
        module_under_test=None,
        project_root=None,
        llm_model=None,
        subject_properties=None,
    ):
        """Initialize the test refinement pipeline.

        Args:
            api_key: OpenAI API key (required; can also use OPENAI_API_KEY)
            module_under_test: Module being tested
            project_root: Project root directory
            llm_model: Model name (e.g., "gpt-4o-mini", "gpt-4o")
            subject_properties: Pynguin's SubjectProperties for native coverage
                measurement (optional; enables branch coverage instead of
                line-coverage fallback).
        """
        # Initialize LLM client (OpenAI only)
        self.llm_client = LLMClient(
            model_name=llm_model or "gpt-4o-mini",
            api_key=api_key,
        )

        self.module_under_test = module_under_test
        self.project_root = project_root or str(Path(__file__).resolve().parent.parent)
        self.sut_inspector = SUTInspector(project_root=self.project_root)
        self.subject_properties = subject_properties

    def structural_analysis(self, test_code: str):
        """Stage 1: Structural Analysis.

        Uses AST-based focal method detection and SUT introspection
        for rich context extraction.

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
                    focal_info.focal_method_name.split(".")[-1]
                    if "." in focal_info.focal_method_name
                    else focal_info.focal_method_name,
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
                node_line = getattr(node, "lineno", 0)
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
                "arrange": (
                    ast.unparse(ast.Module(body=arrange_nodes, type_ignores=[]))
                    if arrange_nodes
                    else ""
                ),
                "act": (
                    ast.unparse(ast.Module(body=[act_node], type_ignores=[])) if act_node else ""
                ),
                "assert": (
                    ast.unparse(ast.Module(body=assert_nodes, type_ignores=[]))
                    if assert_nodes
                    else ""
                ),
                "full_code": test_code,
            }

        except Exception:  # noqa: BLE001
            return self._fallback_structural_analysis(test_code)

    def _fallback_structural_analysis(self, test_code: str):
        """Legacy structural analysis using simple heuristic.

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
            assert_nodes = func_def.body[act_index + 1 :]

            return {
                "test_name": func_def.name,
                "focal_method_name": "unknown",
                "focal_line_number": 0,
                "sut_context": "Documentation unavailable.",
                "arrange": (
                    ast.unparse(ast.Module(body=arrange_nodes, type_ignores=[]))
                    if arrange_nodes
                    else ""
                ),
                "act": ast.unparse(ast.Module(body=[act_node], type_ignores=[])),
                "assert": (
                    ast.unparse(ast.Module(body=assert_nodes, type_ignores=[]))
                    if assert_nodes
                    else ""
                ),
                "full_code": test_code,
            }
        except Exception as e:
            raise ValueError(f"AST Parsing failed: {e}") from e

    def refine_readability(self, analysis: dict):
        """Stage 2 & 3: Semantic Naming and Refactoring with SUT Context.

        Uses the rich SUT context (docstrings, signatures) to guide the LLM
        in generating meaningful variable names and test structure.
        """
        sut_context = analysis.get("sut_context", "Documentation unavailable.")
        focal_method = analysis.get("focal_method_name", "unknown")

        prompt = f"""You are refactoring a Python unit test
to improve readability while preserving its exact behavior.

**Method Documentation:**
{sut_context}

**Current Test:**
```python
{analysis["full_code"]}
```

**Task:** Refactor this test following the Arrange-Act-Assert (AAA) pattern.

**CRITICAL - Preserve ALL import statements exactly as they appear in the original test.**
**CRITICAL - Preserve ALL module prefixes in function calls (e.g., `module_0.function_name()`).**
**The test uses `import ... as module_0` style imports, and ALL SUT function/method calls**
**MUST keep the `module_0.` prefix. Do NOT convert `module_0.func()` to bare `func()`**
**— that will cause NameError.**

**Requirements:**
1. **Test Function Name:** Rename the test function
   to be descriptive of what it tests.If multiple
   tests exist, ensure each has a distinct name
   (e.g., test_equilateral_triangle,
   test_isosceles_with_negative,
   test_scalene_with_bytes)".
   - Use pattern: test_<behavior_being_tested>
   - Example: test_case_0() → test_triangle_with_equal_sides()
   - Example: test_case_1() → test_basket_adds_item_successfully()

2. **Semantic Naming:** Rename generic variables
   (bool_0, int_0, str_0) to meaningful names
   based on the method's purpose
   - Study the docstring to understand what the method does
   - Choose names that reflect the test scenario (e.g., equal_sides, different_sides, invalid_input)

3. **AAA Structure:** CRITICAL - Preserve the
   Arrange-Act-Assert structure with clear
   section markers:
   ```python
   # Arrange
   # ... setup code ...

   # Act
   # ... call to focal method: {focal_method} ...

   # Assert
   # ... verification code ...
   ```
   - Each section must be clearly marked with its comment (# Arrange, # Act, # Assert)
   - Do NOT skip sections even if they are empty
   - Maintain logical separation between setup, execution, and verification

4. **Preserve Behavior:** Keep the exact same logic, assertions, and control flow. Do NOT:
   - Change assertion conditions
   - Add new assertions
   - Remove existing code
   - Modify try/except blocks

5. **Docstring:** Add a brief (1-2 line) docstring
   explaining what this test verifies. Do NOT add
   excessive comments within the test body.

**Output Format:**
Return the complete refactored test WITH ALL IMPORT STATEMENTS from the original test.
Include imports at the top, then the test function.
No explanations, no markdown formatting."""

        return self.llm_client.generate_code(prompt)

    def generate_semantic_assertions(
        self,
        test_code: str,
        focal_method: str,
        sut_context: str,
    ) -> str:
        """Stage 2C: Generate strong, behavior-based assertions using LLM inference.

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
            return test_code

        prompt = f"""You are a test assertion expert.
Your task is to add meaningful assertions to a
unit test based on the method's documented behavior.

**Method Documentation:**
{sut_context}

**Current Test Code:**
```python
{test_code}
```

**CRITICAL: You MUST preserve ALL import statements from the input test code.**
**CRITICAL: Preserve ALL module prefixes in function calls (e.g., `module_0.function_name()`).**
**Do NOT remove the `module_0.` prefix — that will cause NameError.**

**Your Task:**
Analyze the method's documentation and add appropriate assertions to verify its behavior.

**Critical Rules:**

1. **Understand the Method's Contract from Documentation:**
   - Read the docstring carefully to understand what the method returns
   - Identify the return type (string, int, dict, list, bool, etc.)
   - Note any special behaviors or edge cases mentioned

2. **Handling Expected Exceptions (Negative Testing):**

   **CRITICAL: Analyze the test inputs to determine
   if the test is a NEGATIVE test
   (expects failure).**

   **Indicators of Negative Tests:**
   - Variable names containing: `invalid_`, `none_`, `negative_`, `bad_`, `wrong_`, `empty_`
   - Values that are clearly invalid: `None`, `-1`
     (when positive expected), empty strings,
     mismatched types
   - Multiple `None` values passed as arguments
   - Type mismatches (e.g., passing string where int expected, or boolean where number expected)

   **For Negative Tests (expecting exceptions):**
   ```python
   # Use pytest.raises() context manager for negative tests
   with pytest.raises(Exception):
       method_under_test(invalid_input)
   ```

   **For Positive Tests (expecting success):**
   - Remove try/except blocks entirely
   - Add proper assertions for the return value
   - Verify the method completes successfully

3. **Generate Appropriate Assertions Based on Return Type:**

   **IMPORTANT: Be conservative with assertions.
   Only assert what you can confidently verify
   from the documentation.**

   **For STRING returns:**
   ```python
   assert isinstance(result, str), "Should return a string"
   assert len(result) > 0
   ```

   **For INTEGER/FLOAT returns:**
   ```python
   assert isinstance(result, int), "Should return an integer"
   ```

   **For BOOLEAN returns:**
   ```python
   assert isinstance(result, bool), "Should return a boolean"
   ```

   **For DICT/LIST returns:**
   ```python
   assert isinstance(result, dict)
   assert len(result) > 0
   ```

4. **For the focal method '{focal_method}':**
   - Look at each call to this method in the test
   - Determine if it's a positive or negative test based on inputs
   - For positive tests: Store result and add assertions
   - For negative tests: Wrap in pytest.raises()

5. **Preserve ALL existing code and AAA Structure:**
   - Keep the # Arrange section unchanged
   - Keep the # Act section unchanged (unless converting try/except to pytest.raises)
   - Keep variable names unchanged
   - Only add/modify assertions in the # Assert section
   - Never remove the AAA comment markers

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

AFTER:
```python
def test_triangle_valid():
    # Arrange
    side_a = 5
    side_b = 5
    side_c = 5

    # Act
    result = module_0.triangle(side_a, side_b, side_c)

    # Assert
    assert isinstance(result, str)
    assert len(result) > 0
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
    with pytest.raises(Exception):
        module_0.triangle(invalid_side, invalid_side, another_invalid)
```

**Output Format:**
Return the complete test function with ALL import statements and ALL original code preserved.
Start with import statements, then the test function.
ONLY modify the Act/Assert sections to add proper assertions or pytest.raises() blocks.
Do NOT change function names, variable names, or the Arrange section.
Do NOT add inline comments or docstring with assertion explanations.
No explanations, no markdown code blocks."""

        try:
            improved_code = self.llm_client.generate_code(prompt)

            # Verify imports are preserved - if not, fallback to original
            if "import" not in improved_code:
                return test_code

            return improved_code
        except Exception:  # noqa: BLE001
            return test_code

    def repair_test_code(self, broken_code: str, error_message: str) -> str:
        """Stage 3: Repair Loop - Attempts to fix broken test code.

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
- Preserve ALL module prefixes (e.g., `module_0.func()`) — do NOT convert to bare `func()` calls
- Do NOT include explanations, just the fixed code

**Corrected Test Code:**
```python"""

        try:
            return self.llm_client.generate_code(prompt)
        except Exception:  # noqa: BLE001
            return broken_code  # Return original if repair fails

    def _prepare_refined_code(self, original_code: str) -> tuple[str, dict[str, Any], dict | None]:
        """Run Stages 1-2.6 of the pipeline.

        Returns ``(current_code, mutation_stats, error_result)``.  When
        ``error_result`` is not ``None`` the caller should return it directly.
        """
        # Stage 1: Structural Analysis
        analysis_result = self.structural_analysis(original_code)

        # Stage 2: Readability Refinement
        readable_code = self.refine_readability(analysis_result)
        if isinstance(readable_code, str) and readable_code.startswith("# LLM error"):
            return "", {}, {"success": False, "error": readable_code, "iterations": 0}
        readable_code = _restore_import_block(readable_code, original_code)

        # Stage 2C: Semantic Assertion Generation
        focal_method = analysis_result.get("focal_method_name", "unknown")
        sut_context = analysis_result.get("sut_context", "Documentation unavailable.")
        assertion_code = self.generate_semantic_assertions(readable_code, focal_method, sut_context)
        if isinstance(assertion_code, str) and assertion_code.startswith("# LLM error"):
            assertion_code = readable_code  # fall back to Stage 2 output
        assertion_code = _restore_import_block(assertion_code, original_code)

        # Stage 2.6: Mutation-Based Assertion Filtering (BEFORE repair)
        current_code = assertion_code
        mutation_stats: dict[str, Any] = {}
        try:
            current_code, mutation_stats = filter_vacuous_assertions(
                original_test=original_code,
                refined_test=current_code,
                module_under_test=self.module_under_test,
                max_mutants=10,
            )
        except Exception as e:  # noqa: BLE001
            mutation_stats = {"error": str(e)}

        return current_code, mutation_stats, None

    def _apply_aaa_markers(self, current_code: str) -> str:
        """Insert AAA markers (best-effort), keeping them only if the test still passes."""
        try:
            final_focal_info = FocalMethodAnalyzer(current_code, current_code).analyze()
            # Re-analysis may fail; fall back to 0 rather than a stale Stage-1
            # line number (which referred to the original pre-LLM code).
            focal_line = (
                final_focal_info.focal_line_number
                if final_focal_info and final_focal_info.focal_line_number > 0
                else 0
            )
            marked_code = insert_aaa_markers_simple(current_code, focal_line)
            aaa_passed, _ = run_test(marked_code, self.module_under_test)
            if aaa_passed:
                return marked_code
        except Exception:  # noqa: S110, BLE001
            pass  # AAA insertion is best-effort
        return current_code

    def _finalize_on_pass(
        self,
        original_code: str,
        current_code: str,
        repair_iterations: int,
        mutation_stats: dict[str, Any],
    ) -> dict:
        """Run the coverage check and AAA insertion after a passing test."""
        coverage_passed, coverage_details = check_coverage_preservation(
            original_test=original_code,
            refined_test=current_code,
            module_under_test=self.module_under_test,
            tolerance=0.0,
            subject_properties=self.subject_properties,
        )

        if not coverage_passed:
            return {
                "success": False,
                "error": "Coverage preservation check failed",
                "coverage_details": coverage_details,
                "iterations": repair_iterations,
            }

        current_code = self._apply_aaa_markers(current_code)

        return {
            "success": True,
            "final_code": current_code,
            "iterations": repair_iterations,
            "mutation_stats": mutation_stats,
            "coverage_details": coverage_details,
        }

    def _run_repair_loop(
        self,
        original_code: str,
        current_code: str,
        mutation_stats: dict[str, Any],
        max_retries: int,
    ) -> dict:
        """Iteratively validate and repair ``current_code``."""
        for iteration in range(max_retries + 1):
            passed, error_msg = run_test(current_code, self.module_under_test)

            if passed:
                return self._finalize_on_pass(
                    original_code, current_code, iteration, mutation_stats
                )

            error_type = _classify_error(error_msg)

            if iteration >= max_retries:
                return {
                    "success": False,
                    "error": (
                        f"Failed after {max_retries} repair attempts. Last error: {error_type}"
                    ),
                    "last_error_msg": error_msg,
                    "iterations": iteration,
                }

            # Assertion-failure policy: discard the inferred assertion rather
            # than asking the LLM to "fix" it (which could make it vacuous).
            if error_type == "Assertion Error":
                modified_code, removed_assertion = _remove_failing_inferred_assertion(
                    current_code, original_code, error_msg
                )
                if modified_code and removed_assertion:
                    current_code = modified_code
                    continue  # Don't count this as a repair iteration

            current_code = self.repair_test_code(current_code, error_msg)
            current_code = _restore_import_block(current_code, original_code)

        # Loop completed without returning (shouldn't happen, but handle).
        return {
            "success": False,
            "error": "Unexpected loop termination",
            "iterations": max_retries + 1,
        }

    def process_test_end_to_end(self, original_code: str, max_retries: int = 3) -> dict:
        """Complete end-to-end test refinement pipeline with iterative repair loop.

        This method implements the full pipeline (order matters!):
        - Stage 1: Structural Analysis (focal method detection + SUT context)
        - Stage 2: Readability Refinement (semantic naming)
        - Stage 2C: Semantic Assertion Generation (LLM-inferred assertions)
        - Stage 2.6: Mutation-Based Assertion Filtering (BEFORE repair)
        - Stage 3: Iterative Repair Loop (compilation/functional validation)
        - Level 2: Coverage Preservation Check (inside repair success path)
        - Post-repair: AAA Marker Insertion + final re-validation

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
        # Level 1 baseline check (best-effort; refinement proceeds regardless).
        run_test(original_code, self.module_under_test)

        try:
            current_code, mutation_stats, error_result = self._prepare_refined_code(original_code)
            if error_result is not None:
                return error_result
            return self._run_repair_loop(original_code, current_code, mutation_stats, max_retries)
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": f"Pipeline exception: {e!s}", "iterations": 0}
