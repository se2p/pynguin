#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the SUT inspector (sut_inspector.py)."""

from __future__ import annotations

import math

from pynguin.refinement.sut_inspector import SUTInspectionResult, SUTInspector, time_limit


def test_inspect_python_function_succeeds():
    inspector = SUTInspector()
    result = inspector.inspect_method("json", "dumps")
    assert result.success is True
    assert result.docstring is not None
    assert result.signature is not None
    assert result.module_name == "json"
    assert result.object_path == "dumps"


def test_inspect_builtin_without_signature_still_succeeds_on_docstring():
    inspector = SUTInspector()
    result = inspector.inspect_method("math", "sqrt")
    # Built-ins have no inspectable signature but do have a docstring.
    assert result.success is True
    assert result.docstring is not None


def test_inspect_module_itself():
    inspector = SUTInspector()
    result = inspector.inspect_method("json")
    assert result.success is True
    assert result.object_path is None


def test_inspect_unimportable_module_fails():
    inspector = SUTInspector()
    result = inspector.inspect_method("this_module_does_not_exist_xyz")
    assert result.success is False
    assert "Failed to import" in result.error_message


def test_inspect_missing_object_fails():
    inspector = SUTInspector()
    result = inspector.inspect_method("math", "definitely_not_a_real_attribute")
    assert result.success is False
    assert "not found" in result.error_message


def test_traverse_object_path_empty_returns_module():
    inspector = SUTInspector()
    assert inspector._traverse_object_path(math, "") is math


def test_format_context_string_for_failure():
    inspector = SUTInspector()
    failure = SUTInspectionResult(success=False)
    assert inspector.format_context_string(failure) == "Documentation unavailable."


def test_format_context_string_for_success_includes_sections():
    inspector = SUTInspector()
    result = inspector.inspect_method("json", "dumps")
    formatted = inspector.format_context_string(result)
    assert "Focal Method: json.dumps" in formatted
    assert "Signature:" in formatted
    assert "Docstring:" in formatted


def test_time_limit_context_manager_yields():
    executed = False
    with time_limit(1):
        executed = True
    assert executed is True


def test_extract_signature_handles_uninspectable_object():
    inspector = SUTInspector()
    # An int has no inspectable signature -> returns None instead of raising.
    assert inspector._extract_signature(5) is None
