#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for module-granularity refinement (pipeline methods + refiner dispatch)."""

from __future__ import annotations

import ast
import types
from unittest.mock import patch

import pytest

from pynguin.configuration import RefinementGranularity
from pynguin.refinement import refiner as refiner_module
from pynguin.refinement.pipeline import TestRefiner
from pynguin.refinement.refiner import (
    _assemble_module_blob,  # noqa: PLC2701
    _generate_module,  # noqa: PLC2701
    _index_refined_functions,  # noqa: PLC2701
    _process_module,  # noqa: PLC2701
    _slice_function_source,  # noqa: PLC2701
    _TestOutcome,  # noqa: PLC2701
)

IMPORT_BLOCK = "import module_0\n"

ORIGINAL_MODULE = (
    "import module_0\n\n"
    "def test_case_0():\n    var_0 = 1\n    assert module_0.f(var_0) == 2\n\n"
    "def test_case_1():\n    var_0 = 2\n    assert module_0.f(var_0) == 3\n"
)

REFINED_MODULE = (
    "import module_0\n\n"
    "def test_case_0():\n"
    "    # Arrange\n    value = 1\n"
    "    # Act\n    result = module_0.f(value)\n"
    "    # Assert\n    assert result == 2\n\n"
    "def test_case_1():\n"
    "    # Arrange\n    value = 2\n"
    "    # Act\n    result = module_0.f(value)\n"
    "    # Assert\n    assert result == 3\n"
)


def _original_functions() -> list[ast.FunctionDef]:
    tree = ast.parse(ORIGINAL_MODULE)
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


# ===================================================================
# Pipeline module-level methods: request counts
# ===================================================================


@pytest.fixture
def pipeline_refiner() -> TestRefiner:
    """A real ``TestRefiner`` with a mocked ``LLMClient`` returning REFINED_MODULE."""
    module = types.ModuleType("dummy_module")
    with patch("pynguin.refinement.pipeline.LLMClient") as mock_cls:
        instance = mock_cls.return_value
        instance.generate_from_prompt.return_value = REFINED_MODULE
        r = TestRefiner(module_under_test=module)
        r.llm_client = instance
        yield r


def test_combined_issues_single_request(pipeline_refiner: TestRefiner):
    result = pipeline_refiner.refine_module_combined(ORIGINAL_MODULE, "ctx")
    assert pipeline_refiner.llm_client.generate_from_prompt.call_count == 1
    assert "def test_case_0():" in result
    assert "import module_0" in result


def test_module_separate_issues_two_requests(pipeline_refiner: TestRefiner):
    readable = pipeline_refiner.refine_readability_module(ORIGINAL_MODULE, "ctx")
    pipeline_refiner.generate_semantic_assertions_module(readable, "ctx")
    assert pipeline_refiner.llm_client.generate_from_prompt.call_count == 2


def test_module_method_propagates_llm_error_sentinel(pipeline_refiner: TestRefiner):
    pipeline_refiner.llm_client.generate_from_prompt.return_value = "# LLM error: boom"
    assert pipeline_refiner.refine_module_combined(ORIGINAL_MODULE, "ctx").startswith("# LLM error")
    assert pipeline_refiner.refine_readability_module(ORIGINAL_MODULE, "ctx").startswith(
        "# LLM error"
    )
    assert pipeline_refiner.generate_semantic_assertions_module(ORIGINAL_MODULE, "ctx").startswith(
        "# LLM error"
    )


# ===================================================================
# Split & map helpers
# ===================================================================


def test_assemble_module_blob_contains_all_functions_and_imports():
    blob = _assemble_module_blob(IMPORT_BLOCK, _original_functions())
    assert "import module_0" in blob
    assert "def test_case_0():" in blob
    assert "def test_case_1():" in blob


def test_index_refined_functions_maps_by_name():
    index = _index_refined_functions(REFINED_MODULE)
    assert index is not None
    assert set(index) == {"test_case_0", "test_case_1"}


def test_index_refined_functions_returns_none_on_unparseable():
    assert _index_refined_functions("def broken(: pass") is None


def test_slice_function_source_preserves_comments():
    index = _index_refined_functions(REFINED_MODULE)
    sliced = _slice_function_source(REFINED_MODULE, index["test_case_0"])
    assert sliced.startswith("def test_case_0():")
    assert "# Arrange" in sliced
    assert "test_case_1" not in sliced


# ===================================================================
# _generate_module dispatch (request counts per mode)
# ===================================================================


class _RecordingRefiner:
    """A fake refiner recording which module-level generation methods were called."""

    def __init__(self, refined_module: str = REFINED_MODULE):
        self.refined_module = refined_module
        self.calls: list[str] = []

    def build_module_sut_context(self) -> str:
        return "ctx"

    def refine_module_combined(self, _blob: str, _ctx: str) -> str:
        self.calls.append("combined")
        return self.refined_module

    def refine_readability_module(self, _blob: str, _ctx: str) -> str:
        self.calls.append("readability")
        return self.refined_module

    def generate_semantic_assertions_module(self, _blob: str, _ctx: str) -> str:
        self.calls.append("assertions")
        return self.refined_module

    def finish_refined_test(self, *, original_code, refined_code, max_retries) -> dict:
        return {
            "success": True,
            "final_code": refined_code,
            "iterations": 0,
            "mutation_stats": {},
        }


def test_generate_module_combined_calls_combined_once():
    refiner = _RecordingRefiner()
    _generate_module(refiner, "blob", "ctx", RefinementGranularity.COMBINED)
    assert refiner.calls == ["combined"]


def test_generate_module_separate_calls_two_stages_in_order():
    refiner = _RecordingRefiner()
    _generate_module(refiner, "blob", "ctx", RefinementGranularity.MODULE_SEPARATE)
    assert refiner.calls == ["readability", "assertions"]


def test_generate_module_separate_stops_on_readability_error():
    refiner = _RecordingRefiner(refined_module="# LLM error: boom")
    out = _generate_module(refiner, "blob", "ctx", RefinementGranularity.MODULE_SEPARATE)
    # Readability failed → assertion stage is skipped, sentinel propagates.
    assert refiner.calls == ["readability"]
    assert out.startswith("# LLM error")


# ===================================================================
# _process_module: happy path, split/map, and fallback
# ===================================================================


@pytest.fixture
def no_fallback(monkeypatch):
    """Record calls to the per-test fallback path."""
    fallbacks: list[str] = []

    def _fake_process_one_test(_refiner, _import_block, func, _max_iter):
        fallbacks.append(func.name)
        return _TestOutcome(func_text=ast.unparse(func), processed=True, refined=True)

    monkeypatch.setattr(refiner_module, "_process_one_test", _fake_process_one_test)
    return fallbacks


def test_process_module_happy_path_no_fallback(no_fallback):
    refiner = _RecordingRefiner()
    outcomes = _process_module(
        refiner, IMPORT_BLOCK, _original_functions(), RefinementGranularity.COMBINED, 2
    )
    assert len(outcomes) == 2
    assert all(o.refined for o in outcomes)
    assert no_fallback == []  # nothing fell back
    assert refiner.calls == ["combined"]


def test_process_module_missing_test_falls_back(no_fallback):
    # Refined module drops test_case_1 → only test_case_0 is mapped.
    partial = "import module_0\n\ndef test_case_0():\n    # Assert\n    assert module_0.f(1) == 2\n"
    refiner = _RecordingRefiner(refined_module=partial)
    outcomes = _process_module(
        refiner, IMPORT_BLOCK, _original_functions(), RefinementGranularity.COMBINED, 2
    )
    assert len(outcomes) == 2
    assert no_fallback == ["test_case_1"]  # the dropped test fell back to per-test


def test_process_module_truncated_response_falls_back_all(no_fallback):
    refiner = _RecordingRefiner(refined_module="def test_case_0(: truncated")
    outcomes = _process_module(
        refiner, IMPORT_BLOCK, _original_functions(), RefinementGranularity.COMBINED, 2
    )
    assert len(outcomes) == 2
    assert no_fallback == ["test_case_0", "test_case_1"]


def test_process_module_llm_error_falls_back_all(no_fallback):
    refiner = _RecordingRefiner(refined_module="# LLM error: rate limited")
    outcomes = _process_module(
        refiner, IMPORT_BLOCK, _original_functions(), RefinementGranularity.MODULE_SEPARATE, 2
    )
    assert len(outcomes) == 2
    assert no_fallback == ["test_case_0", "test_case_1"]


def test_process_module_finish_exception_falls_back(no_fallback):
    class _ExplodingRefiner(_RecordingRefiner):
        def finish_refined_test(self, *, original_code, refined_code, max_retries):
            raise RuntimeError("finish blew up")

    refiner = _ExplodingRefiner()
    outcomes = _process_module(
        refiner, IMPORT_BLOCK, _original_functions(), RefinementGranularity.COMBINED, 2
    )
    assert len(outcomes) == 2
    assert no_fallback == ["test_case_0", "test_case_1"]
