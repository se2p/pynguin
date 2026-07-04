#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the refinement entry point (refiner.py)."""

from __future__ import annotations

from pynguin.refinement.refiner import (
    _extract_function_text,  # noqa: PLC2701
    refine_generated_tests,
)


def test_extract_function_text_strips_imports():
    code = "import module_0\n\ndef test_x():\n    assert True\n"
    extracted = _extract_function_text(code)
    assert extracted.startswith("def test_x():")
    assert "import module_0" not in extracted


def test_extract_function_text_keeps_decorator():
    code = "@some.decorator\ndef test_x():\n    assert True\n"
    extracted = _extract_function_text(code)
    assert extracted.startswith("@some.decorator")


def test_extract_function_text_preserves_aaa_comments():
    code = (
        "import module_0\n\n"
        "def test_x():\n"
        "    # Arrange\n"
        "    x = 1\n"
        "    # Act\n"
        "    y = module_0.f(x)\n"
        "    # Assert\n"
        "    assert y\n"
    )
    extracted = _extract_function_text(code)
    assert "# Arrange" in extracted
    assert "# Act" in extracted
    assert "# Assert" in extracted


def test_extract_function_text_syntax_error_fallback():
    code = "def broken(:\n    pass\n"
    # Falls back to the line-based scan and still returns from the def.
    assert _extract_function_text(code).startswith("def broken(")


def test_refine_returns_empty_stats_for_unimportable_module(tmp_path):
    test_file = tmp_path / "test_mod.py"
    test_file.write_text("def test_case_0():\n    assert True\n", encoding="utf-8")

    stats = refine_generated_tests(
        test_file_path=test_file,
        module_name="totally_nonexistent_module_xyz",
    )
    assert stats["tests_processed"] == 0
    assert stats["tests_refined"] == 0
    assert "error" not in stats


def test_refine_returns_error_for_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.py"
    stats = refine_generated_tests(
        test_file_path=missing,
        module_name="json",
    )
    assert stats["tests_processed"] == 0
    assert "error" in stats
