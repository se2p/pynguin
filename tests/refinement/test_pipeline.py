#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the refinement pipeline orchestrator (pipeline.py)."""

from __future__ import annotations

import ast
import operator
import types
from unittest.mock import MagicMock, patch

import pytest

from pynguin.refinement.pipeline import (
    TestRefiner,
    _remove_failing_inferred_assertion,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SIMPLE_TEST_CODE = """\
import module_0

def test_case_0():
    var_0 = 5
    var_1 = module_0.add(var_0, var_0)
    assert var_1 == 10
"""

SIMPLE_TEST_NO_ASSERT = """\
import module_0

def test_case_0():
    var_0 = 5
    module_0.add(var_0, var_0)
"""

BROKEN_SYNTAX_CODE = """\
import module_0

def test_case_0():
    var_0 = 5
    assert var_0 ==
"""

MULTI_ASSERT_TEST = """\
import module_0

def test_case_0():
    var_0 = 5
    var_1 = module_0.add(var_0, var_0)
    assert var_1 == 10
    assert isinstance(var_1, int)
"""


def _make_module(name: str = "module_0") -> types.ModuleType:
    """Create a dummy module with an ``add`` function."""
    mod = types.ModuleType(name)
    mod.add = operator.add  # type: ignore[attr-defined]
    return mod


@pytest.fixture
def dummy_module() -> types.ModuleType:
    return _make_module()


@pytest.fixture
def refiner(dummy_module: types.ModuleType) -> TestRefiner:
    """Return a ``TestRefiner`` whose ``LLMClient`` is fully mocked."""
    with patch("pynguin.refinement.pipeline.LLMClient") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.generate_code.return_value = SIMPLE_TEST_CODE
        instance.get_usage.return_value = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "time_seconds": 0.0,
        }
        r = TestRefiner(
            api_key="test-key",
            module_under_test=dummy_module,
            project_root="project_root",
            llm_model="gpt-4o-mini",
        )
        # In case the mock was already consumed by __init__, re-attach it
        r.llm_client = instance
        yield r


# ===================================================================
# TestRefiner.__init__
# ===================================================================


def test_init_stores_module_under_test(refiner: TestRefiner, dummy_module):
    assert refiner.module_under_test is dummy_module


def test_init_stores_project_root(refiner: TestRefiner):
    assert refiner.project_root == "project_root"


def test_init_default_project_root(dummy_module):
    """When project_root is None the refiner falls back to a computed default."""
    with patch("pynguin.refinement.pipeline.LLMClient"):
        r = TestRefiner(api_key="k", module_under_test=dummy_module)
    assert r.project_root is not None
    assert len(r.project_root) > 0


def test_init_no_subject_properties(refiner: TestRefiner):
    assert refiner.subject_properties is None


# ===================================================================
# structural_analysis
# ===================================================================


def test_structural_analysis_returns_expected_keys(refiner: TestRefiner):
    result = refiner.structural_analysis(SIMPLE_TEST_CODE)
    expected_keys = {
        "test_name",
        "focal_method_name",
        "focal_line_number",
        "arrange",
        "act",
        "assert",
        "full_code",
    }
    # sut_context is also present when the primary path succeeds
    assert expected_keys.issubset(result.keys())


def test_structural_analysis_test_name(refiner: TestRefiner):
    result = refiner.structural_analysis(SIMPLE_TEST_CODE)
    assert result["test_name"] == "test_case_0"


def test_structural_analysis_full_code_preserved(refiner: TestRefiner):
    result = refiner.structural_analysis(SIMPLE_TEST_CODE)
    assert result["full_code"] == SIMPLE_TEST_CODE


def test_structural_analysis_fallback_on_garbage(refiner: TestRefiner):
    """Non-parseable code triggers the fallback, which raises ValueError."""
    with pytest.raises(ValueError, match="AST Parsing failed"):
        refiner.structural_analysis("this is not python code at all!!!")


def test_structural_analysis_no_function_def(refiner: TestRefiner):
    """Code without a function definition triggers fallback → ValueError."""
    with pytest.raises(ValueError, match="AST Parsing failed"):
        refiner.structural_analysis("x = 1\ny = 2\n")


def test_structural_analysis_no_assert(refiner: TestRefiner):
    """Test without assertions still produces a result (arrange/act only)."""
    result = refiner.structural_analysis(SIMPLE_TEST_NO_ASSERT)
    assert result["test_name"] == "test_case_0"
    # The act section should be non-empty
    assert result["act"] or result["arrange"]


# ===================================================================
# _fallback_structural_analysis
# ===================================================================


def test_fallback_structural_analysis_basic(refiner: TestRefiner):
    result = refiner._fallback_structural_analysis(SIMPLE_TEST_CODE)
    assert result["test_name"] == "test_case_0"
    assert result["focal_method_name"] == "unknown"
    assert result["focal_line_number"] == 0
    assert result["sut_context"] == "Documentation unavailable."


def test_fallback_structural_analysis_multi_assert(refiner: TestRefiner):
    result = refiner._fallback_structural_analysis(MULTI_ASSERT_TEST)
    assert result["test_name"] == "test_case_0"
    # Assert section should contain both assertions
    assert "assert" in result["assert"].lower()


def test_fallback_raises_on_invalid_code(refiner: TestRefiner):
    with pytest.raises(ValueError, match="AST Parsing failed"):
        refiner._fallback_structural_analysis("not valid python !!!")


def test_fallback_raises_on_no_function(refiner: TestRefiner):
    with pytest.raises(ValueError, match="No function definition"):
        refiner._fallback_structural_analysis("x = 1\n")


def test_fallback_raises_on_only_asserts(refiner: TestRefiner):
    code = """\
def test_only_asserts():
    assert True
    assert False
"""
    with pytest.raises(ValueError, match="Could not determine"):
        refiner._fallback_structural_analysis(code)


# ===================================================================
# refine_readability
# ===================================================================


def test_refine_readability_calls_llm(refiner: TestRefiner):
    analysis = refiner.structural_analysis(SIMPLE_TEST_CODE)
    result = refiner.refine_readability(analysis)
    refiner.llm_client.generate_code.assert_called_once()
    assert isinstance(result, str)


def test_refine_readability_prompt_contains_sut_context(refiner: TestRefiner):
    analysis = {
        "full_code": SIMPLE_TEST_CODE,
        "sut_context": "def add(a, b): return a + b",
        "focal_method_name": "add",
    }
    refiner.refine_readability(analysis)
    prompt = refiner.llm_client.generate_code.call_args[0][0]
    assert "def add(a, b): return a + b" in prompt


def test_refine_readability_prompt_contains_test_code(refiner: TestRefiner):
    analysis = {
        "full_code": SIMPLE_TEST_CODE,
        "sut_context": "Documentation unavailable.",
        "focal_method_name": "unknown",
    }
    refiner.refine_readability(analysis)
    prompt = refiner.llm_client.generate_code.call_args[0][0]
    assert "test_case_0" in prompt


# ===================================================================
# generate_semantic_assertions
# ===================================================================


def test_generate_semantic_assertions_skips_when_no_docs(refiner: TestRefiner):
    """When sut_context is 'Documentation unavailable.', return code as-is."""
    result = refiner.generate_semantic_assertions(
        SIMPLE_TEST_CODE, "add", "Documentation unavailable."
    )
    assert result == SIMPLE_TEST_CODE
    refiner.llm_client.generate_code.assert_not_called()


def test_generate_semantic_assertions_calls_llm(refiner: TestRefiner):
    refiner.llm_client.generate_code.return_value = (
        "import module_0\n\ndef test_add():\n    assert module_0.add(1,2) == 3\n"
    )
    result = refiner.generate_semantic_assertions(SIMPLE_TEST_CODE, "add", "Adds two numbers.")
    refiner.llm_client.generate_code.assert_called_once()
    assert "import" in result


def test_generate_semantic_assertions_fallback_on_missing_import(refiner: TestRefiner):
    """If LLM response has no import, original code is returned."""
    refiner.llm_client.generate_code.return_value = "def test_add():\n    pass\n"
    result = refiner.generate_semantic_assertions(SIMPLE_TEST_CODE, "add", "Adds two numbers.")
    assert result == SIMPLE_TEST_CODE


def test_generate_semantic_assertions_fallback_on_exception(refiner: TestRefiner):
    refiner.llm_client.generate_code.side_effect = RuntimeError("fail")
    result = refiner.generate_semantic_assertions(SIMPLE_TEST_CODE, "add", "Adds two numbers.")
    assert result == SIMPLE_TEST_CODE


# ===================================================================
# repair_test_code
# ===================================================================


def test_repair_test_code_returns_llm_output(refiner: TestRefiner):
    refiner.llm_client.generate_code.return_value = "import module_0\ndef test_fixed(): pass"
    result = refiner.repair_test_code("broken", "SyntaxError: invalid syntax")
    assert "test_fixed" in result


def test_repair_test_code_returns_original_on_exception(refiner: TestRefiner):
    refiner.llm_client.generate_code.side_effect = RuntimeError("LLM down")
    result = refiner.repair_test_code("original_code", "SyntaxError")
    assert result == "original_code"


def test_repair_test_code_prompt_includes_error(refiner: TestRefiner):
    refiner.llm_client.generate_code.return_value = "fixed"
    refiner.repair_test_code("code", "NameError: name 'x' is not defined")
    prompt = refiner.llm_client.generate_code.call_args[0][0]
    assert "NameError" in prompt
    assert "name 'x' is not defined" in prompt


# ===================================================================
# _remove_failing_inferred_assertion
# ===================================================================


def test_remove_failing_inferred_assertion_removes_new_assertion():
    original = """\
def test_case_0():
    x = 1
    assert x == 1
"""
    refined = """\
def test_case_0():
    x = 1
    assert x == 1
    assert isinstance(x, int)
"""
    modified, removed = _remove_failing_inferred_assertion(refined, original, "AssertionError")
    assert modified is not None
    assert removed is not None
    assert "isinstance" in removed
    # The remaining assertion should still be there
    assert "x == 1" in modified


def test_remove_failing_inferred_assertion_no_inferred():
    """When there are no inferred assertions, returns (None, None)."""
    code = """\
def test_case_0():
    x = 1
    assert x == 1
"""
    modified, removed = _remove_failing_inferred_assertion(code, code, "AssertionError")
    assert modified is None
    assert removed is None


def test_remove_failing_inferred_assertion_syntax_error():
    """Unparseable current_code returns (None, None)."""
    original = "def test(): pass\n"
    modified, removed = _remove_failing_inferred_assertion(
        "this is not python !!!", original, "err"
    )
    assert modified is None
    assert removed is None


def test_remove_failing_inferred_assertion_only_removes_one():
    """Only one inferred assertion is removed per call."""
    original = "def test_case_0():\n    assert True\n"
    refined = """\
def test_case_0():
    assert True
    assert 1 == 1
    assert 2 == 2
"""
    modified, removed = _remove_failing_inferred_assertion(refined, original, "err")
    assert modified is not None
    assert removed is not None
    # Exactly one of the inferred assertions should have been removed
    tree = ast.parse(modified)
    assert_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.Assert))
    # Original had 1, refined had 3, after removal should have 2
    assert assert_count == 2


# ===================================================================
# process_test_end_to_end — success paths
# ===================================================================


def test_process_end_to_end_success(refiner: TestRefiner):
    """Happy path: the refined test passes on first try."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test") as mock_run,
        patch("pynguin.refinement.pipeline.check_coverage_preservation") as mock_cov,
        patch("pynguin.refinement.pipeline.filter_vacuous_assertions") as mock_filter,
    ):
        # Original test passes
        mock_run.return_value = (True, "Test passed.")
        mock_cov.return_value = (
            True,
            {
                "status": "passed",
                "metric": "line",
                "original_coverage": 1.0,
                "refined_coverage": 1.0,
                "coverage_delta": 0.0,
            },
        )
        mock_filter.return_value = (SIMPLE_TEST_CODE, {"assertions_removed": 0})

        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is True
    assert "final_code" in result
    assert result["iterations"] == 0


def test_process_end_to_end_no_repair_needed(refiner: TestRefiner):
    """When the refined code passes immediately, iterations == 0."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, {}),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE)

    assert result["success"] is True
    assert result["iterations"] == 0


# ===================================================================
# process_test_end_to_end — repair loop
# ===================================================================


def test_process_end_to_end_repair_succeeds_after_one_iteration(refiner: TestRefiner):
    """Test fails first, gets repaired, then passes."""
    call_count = 0

    def run_test_side_effect(_code, _module):
        nonlocal call_count
        call_count += 1
        # First call: original baseline (pass)
        # Second call: refined code fails
        # Third call: repaired code passes
        # Fourth call: after-filter validation passes
        if call_count in {1, 3, 4}:
            return True, "Test passed."
        return False, "NameError: name 'x' is not defined"

    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test", side_effect=run_test_side_effect),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, {}),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is True
    assert result["iterations"] == 1


def test_process_end_to_end_fails_after_max_retries(refiner: TestRefiner):
    """All repair attempts fail → result records failure."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with patch(
        "pynguin.refinement.pipeline.run_test",
        return_value=(False, "SyntaxError: invalid syntax"),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=2)

    assert result["success"] is False
    assert "Failed after 2 repair attempts" in result["error"]
    assert result["iterations"] == 2


# ===================================================================
# process_test_end_to_end — assertion discard policy
# ===================================================================


def test_process_end_to_end_assertion_error_discards_inferred(refiner: TestRefiner):
    """AssertionError on inferred assertion triggers automatic discard."""
    call_count = 0

    def run_test_side_effect(_code, _module):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return True, "Test passed."  # baseline
        if call_count == 2:
            return False, "AssertionError: assert isinstance(x, int)"
        return True, "Test passed."

    refiner.llm_client.generate_code.return_value = MULTI_ASSERT_TEST

    with (
        patch("pynguin.refinement.pipeline.run_test", side_effect=run_test_side_effect),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, {}),
        ),
        patch(
            "pynguin.refinement.pipeline._remove_failing_inferred_assertion",
            return_value=(SIMPLE_TEST_CODE, "isinstance(var_1, int)"),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is True


# ===================================================================
# process_test_end_to_end — coverage failure
# ===================================================================


def test_process_end_to_end_coverage_failure_reverts(refiner: TestRefiner):
    """When coverage check fails the pipeline reports failure."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(False, {"status": "failed", "reason": "Coverage decreased by 20.0%"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, {}),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is False
    assert "Coverage preservation" in result["error"]


# ===================================================================
# process_test_end_to_end — mutation filtering
# ===================================================================


def test_process_end_to_end_mutation_filtering_removes_assertions(refiner: TestRefiner):
    """Mutation filtering that removes assertions is reflected in stats."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    mutation_stats = {
        "assertions_removed": 1,
        "total_inferred": 2,
        "retained": 1,
    }

    with (
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, mutation_stats),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is True
    assert result["mutation_stats"]["assertions_removed"] == 1


def test_process_end_to_end_mutation_filter_exception_graceful(refiner: TestRefiner):
    """If mutation filtering raises, the pipeline continues with error stats."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            side_effect=RuntimeError("mutant generation failed"),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is True
    assert "error" in result["mutation_stats"]


def test_process_end_to_end_post_filter_validation_fails(refiner: TestRefiner):
    """If the test fails after mutation filtering, we fall back to pre-filter code."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE
    call_count = 0

    def run_test_side_effect(_code, _module):
        nonlocal call_count
        call_count += 1
        # baseline passes, repair-loop passes, post-filter fails, ...
        if call_count <= 2:
            return True, "Test passed."
        if call_count == 3:
            return False, "AssertionError: broken after filter"
        return True, "Test passed."

    with (
        patch("pynguin.refinement.pipeline.run_test", side_effect=run_test_side_effect),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=("broken code", {}),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    # Pipeline should still succeed (fell back to pre-filter code)
    assert result["success"] is True


# ===================================================================
# process_test_end_to_end — AAA marker insertion
# ===================================================================


def test_process_end_to_end_aaa_markers_inserted(refiner: TestRefiner):
    """Verify AAA marker insertion is attempted in the post-repair phase."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, {}),
        ),
        patch("pynguin.refinement.pipeline.FocalMethodAnalyzer") as mock_analyzer_cls,
        patch(
            "pynguin.refinement.aaa_inserter.insert_aaa_markers_simple",
            return_value="# Arrange\n# Act\n# Assert\n" + SIMPLE_TEST_CODE,
        ),
    ):
        focal_mock = MagicMock()
        focal_mock.focal_line_number = 5
        mock_analyzer_cls.return_value.analyze.return_value = focal_mock

        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=3)

    assert result["success"] is True


# ===================================================================
# process_test_end_to_end — pipeline-level exception
# ===================================================================


def test_process_end_to_end_pipeline_exception(refiner: TestRefiner):
    """An unexpected exception in the pipeline is caught and reported."""
    refiner.llm_client.generate_code.side_effect = RuntimeError("unexpected crash")

    with patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=1)

    assert result["success"] is False
    assert "Pipeline exception" in result["error"]
    assert result["iterations"] == 0


# ===================================================================
# process_test_end_to_end — error type classification
# ===================================================================


@pytest.mark.parametrize(
    "error_msg, expected_fragment",
    [
        ("SyntaxError: invalid syntax", "SyntaxError"),
        ("ImportError: No module named 'foo'", "Import Error"),
        ("ModuleNotFoundError: No module named 'bar'", "Import Error"),
        ("NameError: name 'x' is not defined", "Name Error"),
        ("TypeError: expected str, got int", "Type Error"),
    ],
)
def test_process_end_to_end_error_classification(
    refiner: TestRefiner,
    error_msg: str,
    expected_fragment: str,
):
    """Verify that the repair loop classifies errors correctly and reports them."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with patch(
        "pynguin.refinement.pipeline.run_test",
        return_value=(False, error_msg),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=0)

    assert result["success"] is False
    assert expected_fragment in result["error"]


# ===================================================================
# structural_analysis — edge cases
# ===================================================================


def test_structural_analysis_with_try_except(refiner: TestRefiner):
    """Test code wrapped in try/except should still be analyzable."""
    code = """\
import module_0

def test_case_0():
    try:
        var_0 = module_0.add(1, 2)
    except Exception:
        pass
"""
    result = refiner.structural_analysis(code)
    assert result["test_name"] == "test_case_0"


def test_structural_analysis_with_pytest_raises(refiner: TestRefiner):
    code = """\
import pytest
import module_0

def test_case_0():
    with pytest.raises(ValueError):
        module_0.add(None, None)
"""
    result = refiner.structural_analysis(code)
    assert result["test_name"] == "test_case_0"


def test_structural_analysis_multiple_functions(refiner: TestRefiner):
    """Only the first function definition should be used."""
    code = """\
import module_0

def helper():
    return 42

def test_case_0():
    assert helper() == 42
"""
    result = refiner.structural_analysis(code)
    # Will pick up "helper" or "test_case_0" depending on path
    assert "test_name" in result


# ===================================================================
# Integration-style tests (still mocked LLM, but less patching)
# ===================================================================


def test_refine_readability_then_semantic_assertions(refiner: TestRefiner):
    """Chain Stage 2 → Stage 2C and verify both LLM calls happen."""
    # Stage 2 output
    stage2_output = """\
import module_0

def test_addition_of_equal_numbers():
    # Arrange
    first_number = 5

    # Act
    result = module_0.add(first_number, first_number)

    # Assert
    assert result == 10
"""
    # Stage 2C output
    stage2c_output = """\
import module_0

def test_addition_of_equal_numbers():
    # Arrange
    first_number = 5

    # Act
    result = module_0.add(first_number, first_number)

    # Assert
    assert result == 10
    assert isinstance(result, int)
"""
    refiner.llm_client.generate_code.side_effect = [stage2_output, stage2c_output]

    analysis = refiner.structural_analysis(SIMPLE_TEST_CODE)
    readable = refiner.refine_readability(analysis)
    assertions = refiner.generate_semantic_assertions(readable, "add", "Adds two numbers.")

    assert refiner.llm_client.generate_code.call_count == 2
    assert "isinstance" in assertions


# ===================================================================
# process_test_end_to_end — result keys
# ===================================================================


def test_process_end_to_end_success_result_keys(refiner: TestRefiner):
    """On success, the result dict has the expected keys."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with (
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, {"status": "passed"}),
        ),
        patch(
            "pynguin.refinement.pipeline.filter_vacuous_assertions",
            return_value=(SIMPLE_TEST_CODE, {}),
        ),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE)

    assert "success" in result
    assert "final_code" in result
    assert "iterations" in result
    assert "mutation_stats" in result
    assert "coverage_details" in result


def test_process_end_to_end_failure_result_keys(refiner: TestRefiner):
    """On failure, the result dict has error-related keys."""
    refiner.llm_client.generate_code.return_value = SIMPLE_TEST_CODE

    with patch(
        "pynguin.refinement.pipeline.run_test",
        return_value=(False, "SyntaxError: invalid syntax"),
    ):
        result = refiner.process_test_end_to_end(SIMPLE_TEST_CODE, max_retries=0)

    assert result["success"] is False
    assert "error" in result
    assert "iterations" in result
