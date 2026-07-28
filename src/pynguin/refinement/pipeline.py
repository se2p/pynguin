#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Test refinement pipeline orchestrator."""

import ast
import inspect
import re
from pathlib import Path
from typing import Any

import pynguin.configuration as config
from pynguin.large_language_model.prompts import (
    ModuleReadabilityRefinementPrompt,
    ModuleRefinementPrompt,
    ModuleSemanticAssertionsPrompt,
    MutationStrengthenPrompt,
    ReadabilityRefinementPrompt,
    RepairPrompt,
    SemanticAssertionsPrompt,
)
from pynguin.refinement.aaa_inserter import insert_aaa_markers_simple
from pynguin.refinement.ast_analyzer import FocalMethodAnalyzer
from pynguin.refinement.coverage_checker import check_coverage_preservation
from pynguin.refinement.llm_client import LLM_ERROR_PREFIX, LLMClient
from pynguin.refinement.mutation_analyzer import (
    AssertionTracker,
    filter_vacuous_assertions,
    get_surviving_mutants,
)
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
        module_under_test=None,
        project_root=None,
        subject_properties=None,
    ):
        """Initialize the test refinement pipeline.

        Args:
            module_under_test: Module being tested
            project_root: Project root directory
            subject_properties: Pynguin's SubjectProperties for native coverage
                measurement (optional; enables branch coverage instead of
                line-coverage fallback).
        """
        # Initialize the LLM client (OpenAI).  The model name and API key come
        # from the shared large_language_model configuration.
        self.llm_client = LLMClient()

        self.module_under_test = module_under_test
        self.project_root = project_root or str(Path(__file__).resolve().parent.parent)
        self.sut_inspector = SUTInspector(project_root=self.project_root)
        self.subject_properties = subject_properties
        self.current_dependencies = ""
        self.current_usage_examples = ""

    def structural_analysis(self, test_code: str):  # noqa: C901
        """Structural analysis of a test.

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
            dependencies = ""
            usage_examples = ""
            if focal_info.resolved_module_name:
                focal_object_name = (
                    focal_info.focal_method_name.split(".")[-1]
                    if "." in focal_info.focal_method_name
                    else focal_info.focal_method_name
                )
                inspection_result = self.sut_inspector.inspect_method(
                    focal_info.resolved_module_name,
                    focal_object_name,
                )
                sut_context = self.sut_inspector.format_context_string(inspection_result)

                ref_config = config.configuration.llm_refinement
                if ref_config.enable_dependency_context:
                    dependencies = self.sut_inspector.inspect_dependencies(
                        focal_info.resolved_module_name,
                        focal_object_name,
                        max_deps=ref_config.max_dependencies,
                    )
                    if dependencies:
                        sut_context += f"\n\nDependency Signatures:\n{dependencies}"

                if ref_config.enable_usage_examples:
                    usage_examples = self.sut_inspector.inspect_usage_examples(
                        focal_info.resolved_module_name,
                        focal_object_name,
                        max_examples=ref_config.max_usage_examples,
                    )
                    if usage_examples:
                        sut_context += f"\n\nUsage Examples:\n{usage_examples}"

            self.current_dependencies = dependencies
            self.current_usage_examples = usage_examples

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
        """Improve readability via semantic naming and AAA restructuring.

        Uses the rich SUT context (docstrings, signatures) to guide the LLM
        in generating meaningful variable names and test structure.
        """
        sut_context = analysis.get("sut_context", "Documentation unavailable.")
        focal_method = analysis.get("focal_method_name", "unknown")

        prompt_obj = ReadabilityRefinementPrompt(
            sut_context=sut_context,
            focal_method=focal_method,
            test_code=analysis["full_code"],
        )
        return self.llm_client.generate_from_prompt(prompt_obj)

    def generate_semantic_assertions(
        self,
        test_code: str,
        focal_method: str,
        sut_context: str,
    ) -> str:
        """Generate strong, behavior-based assertions using LLM inference.

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

        prompt_obj = SemanticAssertionsPrompt(
            sut_context=sut_context,
            focal_method=focal_method,
            test_code=test_code,
        )
        try:
            improved_code = self.llm_client.generate_from_prompt(prompt_obj)

            # Verify imports are preserved - if not, fallback to original
            if "import" not in improved_code:
                return test_code

            return improved_code
        except Exception:  # noqa: BLE001
            return test_code

    def refine_readability_module(self, module_code: str, sut_context: str) -> str:
        """Refine readability of a whole test module in a single LLM request.

        Args:
            module_code: The whole test module (imports + all test functions).
            sut_context: Formatted SUT documentation for the module.

        Returns:
            The refined module code, or a ``"# LLM error"`` sentinel on failure.
            The original import block is restored on any non-sentinel output.
        """
        prompt_obj = ModuleReadabilityRefinementPrompt(
            module_test_code=module_code,
            sut_context=sut_context,
        )
        refined = self.llm_client.generate_from_prompt(prompt_obj)
        if isinstance(refined, str) and refined.startswith(LLM_ERROR_PREFIX):
            return refined
        return _restore_import_block(refined, module_code)

    def generate_semantic_assertions_module(self, module_code: str, sut_context: str) -> str:
        """Add semantic assertions to a whole test module in a single LLM request.

        Args:
            module_code: The whole test module (imports + all test functions).
            sut_context: Formatted SUT documentation for the module.

        Returns:
            The module code with assertions, or a ``"# LLM error"`` sentinel on failure.
            The original import block is restored on any non-sentinel output.
        """
        prompt_obj = ModuleSemanticAssertionsPrompt(
            module_test_code=module_code,
            sut_context=sut_context,
        )
        improved = self.llm_client.generate_from_prompt(prompt_obj)
        if isinstance(improved, str) and improved.startswith(LLM_ERROR_PREFIX):
            return improved
        return _restore_import_block(improved, module_code)

    def refine_module_combined(self, module_code: str, sut_context: str) -> str:
        """Refine readability *and* add assertions for a whole module in one LLM request.

        Args:
            module_code: The whole test module (imports + all test functions).
            sut_context: Formatted SUT documentation for the module.

        Returns:
            The refined module code, or a ``"# LLM error"`` sentinel on failure.
            The original import block is restored on any non-sentinel output.
        """
        prompt_obj = ModuleRefinementPrompt(
            module_test_code=module_code,
            sut_context=sut_context,
        )
        refined = self.llm_client.generate_from_prompt(prompt_obj)
        if isinstance(refined, str) and refined.startswith(LLM_ERROR_PREFIX):
            return refined
        return _restore_import_block(refined, module_code)

    def repair_test_code(self, broken_code: str, error_message: str) -> str:
        """Attempt to fix broken test code.

        Uses LLM to analyze the error and generate a corrected version.
        This method handles syntax errors, import errors, and failing assertions.

        Args:
            broken_code: The test code that failed validation
            error_message: The error traceback from run_test

        Returns:
            str: The repaired test code
        """
        prompt_obj = RepairPrompt(
            broken_code=broken_code,
            error_message=error_message,
            dependencies=self.current_dependencies,
            usage_examples=self.current_usage_examples,
        )
        try:
            return self.llm_client.generate_from_prompt(prompt_obj)
        except Exception:  # noqa: BLE001
            return broken_code  # Return original if repair fails

    def _prepare_refined_code(self, original_code: str) -> tuple[str, dict[str, Any], dict | None]:
        """Run structural analysis, readability refinement, and assertion filtering.

        Returns ``(current_code, mutation_stats, error_result)``.  When
        ``error_result`` is not ``None`` the caller should return it directly.
        """
        # Structural analysis
        analysis_result = self.structural_analysis(original_code)

        # Readability refinement
        readable_code = self.refine_readability(analysis_result)
        if isinstance(readable_code, str) and readable_code.startswith("# LLM error"):
            return "", {}, {"success": False, "error": readable_code, "iterations": 0}
        readable_code = _restore_import_block(readable_code, original_code)

        # Semantic assertion generation
        focal_method = analysis_result.get("focal_method_name", "unknown")
        sut_context = analysis_result.get("sut_context", "Documentation unavailable.")
        assertion_code = self.generate_semantic_assertions(readable_code, focal_method, sut_context)
        if isinstance(assertion_code, str) and assertion_code.startswith("# LLM error"):
            assertion_code = readable_code  # fall back to readability output
        assertion_code = _restore_import_block(assertion_code, original_code)

        # Mutation-based assertion filtering (before repair)
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

        ref_config = config.configuration.llm_refinement
        if ref_config.enable_mutation_strengthening:
            current_code = self._run_mutation_strengthening_loop(
                current_code=current_code,
                original_code=original_code,
                focal_method=focal_method,
                max_iterations=ref_config.max_mutation_iterations,
            )

        return current_code, mutation_stats, None

    def build_module_sut_context(self) -> str:
        """Build a module-level SUT context string from the module source code.

        Used by the module-granularity refinement paths, which have no single focal
        method.  Falls back to ``"Documentation unavailable."`` when the source cannot
        be retrieved.  The context is truncated to ``max_context_chars`` to bound token
        usage on large modules.

        Returns:
            The (possibly truncated) SUT module source, or a fallback string.
        """
        try:
            module_source = inspect.getsource(self.module_under_test)
        except Exception:  # noqa: BLE001
            return "Documentation unavailable."
        max_chars = config.configuration.large_language_model.max_context_chars
        if max_chars and len(module_source) > max_chars:
            module_source = module_source[:max_chars]
        return module_source or "Documentation unavailable."

    def finish_refined_test(
        self,
        original_code: str,
        refined_code: str,
        max_retries: int,
    ) -> dict:
        """Run the per-test finish stages on already-refined (module-level) code.

        Given a single test that has already gone through module-level readability and/or
        assertion refinement, this runs the same downstream machinery as the per-test
        path: import restoration, mutation-based vacuous-assertion filtering, optional
        mutation strengthening, and the iterative (per-broken-test) repair loop.

        Args:
            original_code: The original Pynguin-generated test (imports + one function).
            refined_code: The refined single test extracted from the module response.
            max_retries: Maximum number of repair attempts.

        Returns:
            The same result dict shape as :meth:`process_test_end_to_end`.
        """
        try:
            # Structural analysis populates current_dependencies/current_usage_examples
            # (no LLM call) so the per-test repair loop keeps its context quality, and
            # yields the focal method for optional mutation strengthening.
            analysis = self.structural_analysis(original_code)
            focal_method = analysis.get("focal_method_name", "unknown")

            current_code = _restore_import_block(refined_code, original_code)

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

            ref_config = config.configuration.llm_refinement
            if ref_config.enable_mutation_strengthening:
                current_code = self._run_mutation_strengthening_loop(
                    current_code=current_code,
                    original_code=original_code,
                    focal_method=focal_method,
                    max_iterations=ref_config.max_mutation_iterations,
                )

            return self._run_repair_loop(original_code, current_code, mutation_stats, max_retries)
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": f"Pipeline exception: {e!s}", "iterations": 0}

    def _run_mutation_strengthening_loop(  # noqa: C901
        self,
        current_code: str,
        original_code: str,
        focal_method: str,
        max_iterations: int,
    ) -> str:
        """Strengthen assertions by prompting LLM with surviving mutants.

        Args:
            current_code: The current test code with semantic assertions.
            original_code: The original Pynguin test code.
            focal_method: Name of the focal method.
            max_iterations: Maximum number of mutation strengthening iterations.

        Returns:
            The strengthened test code.
        """
        for _ in range(max_iterations):
            # 1. Run mutation analysis to get surviving mutants
            survivors = get_surviving_mutants(
                test_code=current_code,
                module_under_test=self.module_under_test,
                max_mutants=10,
            )
            if not survivors:
                break  # No surviving mutants! Perfect.

            # 2. Format surviving mutants for the prompt
            formatted_mutants = []
            for idx, (_mutant_module, mutations) in enumerate(survivors, 1):
                mut_details = []
                for m in mutations:
                    mut_op = m.operator.__name__
                    try:
                        original_source = ast.unparse(m.node).strip()
                        mutated_source = ast.unparse(m.replacement_node).strip()
                    except Exception:  # noqa: BLE001
                        original_source = "unknown"
                        mutated_source = "unknown"
                    lineno = getattr(m.node, "lineno", "unknown")
                    mut_details.append(
                        f"Line {lineno}: Mutated '{original_source}' to "
                        f"'{mutated_source}' (operator: {mut_op})"
                    )
                formatted_mutants.append(f"{idx}. " + " | ".join(mut_details))

            survivors_str = "\n".join(formatted_mutants)

            # Retrieve SUT module source code
            try:
                module_source = inspect.getsource(self.module_under_test)
            except Exception:  # noqa: BLE001
                module_source = "Source code unavailable."

            # 3. Create the MutationStrengthenPrompt
            prompt_obj = MutationStrengthenPrompt(
                module_code=module_source,
                test_code=current_code,
                surviving_mutants=survivors_str,
                focal_method=focal_method,
            )

            # 4. Generate strengthened test code
            try:
                strengthened = self.llm_client.generate_from_prompt(prompt_obj)
                if strengthened and not strengthened.startswith(LLM_ERROR_PREFIX):
                    # Check that it compiles
                    ast.parse(strengthened)
                    # Verify imports are preserved
                    if "import" in strengthened:
                        # Restore imports
                        strengthened = _restore_import_block(strengthened, original_code)
                        # Check coverage preservation (never drop coverage!)
                        coverage_passed, _ = check_coverage_preservation(
                            original_test=original_code,
                            refined_test=strengthened,
                            module_under_test=self.module_under_test,
                            tolerance=0.0,
                            subject_properties=self.subject_properties,
                        )
                        if coverage_passed:
                            current_code = strengthened
            except Exception:  # noqa: BLE001, S110
                pass  # Ignore failures, continue with previous best current_code

        return current_code

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
        - Structural analysis (focal method detection + SUT context)
        - Readability refinement (semantic naming)
        - Semantic assertion generation (LLM-inferred assertions)
        - Mutation-based assertion filtering (before repair)
        - Iterative repair loop (compilation/functional validation)
        - Coverage preservation check (inside repair success path)
        - Post-repair: AAA marker insertion + final re-validation

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
        # Baseline check that the original test passes
        # (best-effort; refinement proceeds regardless).
        run_test(original_code, self.module_under_test)

        try:
            current_code, mutation_stats, error_result = self._prepare_refined_code(original_code)
            if error_result is not None:
                return error_result
            return self._run_repair_loop(original_code, current_code, mutation_stats, max_retries)
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": f"Pipeline exception: {e!s}", "iterations": 0}
