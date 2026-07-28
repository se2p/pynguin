#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the SUT inspector (sut_inspector.py)."""

from __future__ import annotations

import importlib
import math

import pytest

from pynguin.refinement import sut_inspector
from pynguin.refinement.sut_inspector import (
    InspectionTimeoutError,
    SUTInspectionResult,
    SUTInspector,
    time_limit,
)

# Accessed via the module to avoid importing a private name directly.
_collect_referenced_names = sut_inspector._collect_referenced_names


# ---------------------------------------------------------------------------
# inspect_method
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# object-path traversal / resolution
# ---------------------------------------------------------------------------
def test_traverse_object_path_empty_returns_module():
    inspector = SUTInspector()
    assert inspector._traverse_object_path(math, "") is math


def test_traverse_object_path_resolves_nested_attribute():
    inspector = SUTInspector()
    assert inspector._traverse_object_path(math, "pi") is math.pi


def test_traverse_object_path_missing_returns_none():
    inspector = SUTInspector()
    assert inspector._traverse_object_path(math, "nope") is None


def test_resolve_target_object_falls_back_to_module_when_missing():
    inspector = SUTInspector()
    # An unresolvable path degrades to the module itself.
    assert inspector._resolve_target_object(math, "does_not_exist") is math


def test_resolve_target_object_none_path_returns_module():
    inspector = SUTInspector()
    assert inspector._resolve_target_object(math, None) is math


# ---------------------------------------------------------------------------
# signature / docstring / parent-context extraction
# ---------------------------------------------------------------------------
def test_extract_signature_handles_uninspectable_object():
    inspector = SUTInspector()
    # An int has no inspectable signature -> returns None instead of raising.
    assert inspector._extract_signature(5) is None


def test_extract_signature_for_function():
    inspector = SUTInspector()
    sig = inspector._extract_signature(math.hypot)
    # Builtins may or may not expose a signature; if present it is a string.
    assert sig is None or isinstance(sig, str)


def test_extract_docstring_returns_text():
    inspector = SUTInspector()

    def documented():
        """A short docstring."""

    assert inspector._extract_docstring(documented) == "A short docstring."


def test_extract_docstring_missing_returns_none():
    inspector = SUTInspector()

    def undocumented():
        return None

    assert inspector._extract_docstring(undocumented) is None


def test_extract_parent_context_for_method():
    inspector = SUTInspector()
    result = inspector.inspect_method("json.encoder", "JSONEncoder.encode")
    # ``encode`` is defined on ``JSONEncoder`` so its class docstring is picked up.
    assert result.parent_docstring is not None


def test_extract_parent_context_none_for_plain_function():
    inspector = SUTInspector()

    def free_function():
        return None

    assert inspector._extract_parent_context(free_function) is None


# ---------------------------------------------------------------------------
# format_context_string
# ---------------------------------------------------------------------------
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


def test_format_context_string_module_only():
    inspector = SUTInspector()
    result = inspector.inspect_method("json")
    formatted = inspector.format_context_string(result)
    assert "Focal Module: json" in formatted


# ---------------------------------------------------------------------------
# time limit / safe import
# ---------------------------------------------------------------------------
def test_time_limit_context_manager_yields():
    executed = False
    with time_limit(1):
        executed = True
    assert executed is True


def test_safe_import_returns_module():
    inspector = SUTInspector()
    assert inspector._safe_import("json") is not None


def test_safe_import_missing_module_returns_none():
    inspector = SUTInspector()
    assert inspector._safe_import("this_module_does_not_exist_xyz") is None


def test_safe_import_swallows_timeout(monkeypatch):
    inspector = SUTInspector()

    def _raise_timeout(_name):
        raise InspectionTimeoutError("boom")

    monkeypatch.setattr(importlib, "import_module", _raise_timeout)
    # The timeout guard must be caught and reported as a failed (None) import.
    assert inspector._safe_import("json") is None


def test_safe_import_swallows_arbitrary_import_side_effects(tmp_path, monkeypatch):
    # Importing a SUT module runs its top-level code, which may raise; the
    # inspector must degrade to ``None`` rather than propagating the error.
    module_file = tmp_path / "exploding_mod.py"
    module_file.write_text("raise RuntimeError('top-level boom')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    inspector = SUTInspector()
    assert inspector._safe_import("exploding_mod") is None


# ---------------------------------------------------------------------------
# referenced-name collection
# ---------------------------------------------------------------------------
def test_collect_referenced_names_finds_calls():
    source = (
        "import math\ndef target():\n    return math.sqrt(helper())\ndef helper():\n    return 1\n"
    )
    names = _collect_referenced_names(source, "target")
    assert "helper" in names
    assert "math.sqrt" in names


def test_collect_referenced_names_unparsable_source_returns_empty():
    assert _collect_referenced_names("def broken(:\n", "target") == []


def test_collect_referenced_names_unknown_path_scans_module():
    source = "def other():\n    return spam()\n"
    # A non-existent path falls back to the whole module tree.
    names = _collect_referenced_names(source, "missing")
    assert "spam" in names


# ---------------------------------------------------------------------------
# dependency inspection
# ---------------------------------------------------------------------------
def test_inspect_dependencies():
    inspector = SUTInspector()
    deps = inspector.inspect_dependencies("json", "dumps")
    assert isinstance(deps, str)


def test_inspect_dependencies_unimportable_returns_empty():
    inspector = SUTInspector()
    assert not inspector.inspect_dependencies("this_module_does_not_exist_xyz")


def test_inspect_dependencies_surfaces_callable(tmp_path, monkeypatch):
    module_src = "def helper(x):\n    return x\ndef target():\n    return helper(1)\n"
    module_file = tmp_path / "deps_mod.py"
    module_file.write_text(module_src, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    inspector = SUTInspector()
    deps = inspector.inspect_dependencies("deps_mod", "target")
    assert "helper" in deps
    assert "### Function: helper" in deps


def test_inspect_dependencies_respects_max_deps(tmp_path, monkeypatch):
    module_src = (
        "def a():\n    return 1\n"
        "def b():\n    return 1\n"
        "def c():\n    return 1\n"
        "def target():\n    return a() + b() + c()\n"
    )
    module_file = tmp_path / "many_deps_mod.py"
    module_file.write_text(module_src, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    inspector = SUTInspector()
    deps = inspector.inspect_dependencies("many_deps_mod", "target", max_deps=1)
    # Only a single dependency block should remain.
    assert deps.count("### Function:") == 1


def test_inspect_dependencies_handles_unhashable_module_constants(tmp_path, monkeypatch):
    # Regression: a module-level dict/list constant referenced by the SUT must
    # not raise ``TypeError: unhashable type`` while filtering dependencies.
    module_src = (
        "CONFIG = {'a': 1}\n"
        "ITEMS = [1, 2, 3]\n"
        "def helper(x):\n"
        "    return x\n"
        "def target():\n"
        "    return helper(CONFIG) or ITEMS\n"
    )
    module_file = tmp_path / "unhashable_deps_mod.py"
    module_file.write_text(module_src, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    inspector = SUTInspector()
    # Must not raise, and should still surface the callable dependency.
    deps = inspector.inspect_dependencies("unhashable_deps_mod", "target")
    assert isinstance(deps, str)
    assert "helper" in deps


# ---------------------------------------------------------------------------
# dependency-helper units
# ---------------------------------------------------------------------------
def test_is_valid_dependency_rejects_builtins_and_none():
    assert SUTInspector._is_valid_dependency(None) is False
    assert SUTInspector._is_valid_dependency(str) is False
    assert SUTInspector._is_valid_dependency(len) is False


def test_is_valid_dependency_accepts_user_function():
    def helper():
        return None

    assert SUTInspector._is_valid_dependency(helper) is True


def test_resolve_named_object_plain_and_dotted():
    inspector = SUTInspector()
    assert inspector._resolve_named_object(math, "pi") is math.pi
    assert inspector._resolve_named_object(math, "missing") is None
    assert inspector._resolve_named_object(math, "missing.attr") is None


def test_extract_dependency_signature_fallback_for_uninspectable():
    assert SUTInspector._extract_dependency_signature(5) == "(...)"


def test_extract_dependency_signature_for_function():
    def helper(alpha, beta):
        return {"alpha": alpha, "beta": beta}

    assert SUTInspector._extract_dependency_signature(helper) == "(alpha, beta)"


def test_extract_dependency_description_first_line_only():
    def helper():
        """First line.

        Second line.
        """

    assert SUTInspector._extract_dependency_description(helper) == "First line."


def test_extract_dependency_description_default_when_missing():
    def helper():
        return None

    assert SUTInspector._extract_dependency_description(helper) == "No description available."


def test_read_module_source_reads_file(tmp_path, monkeypatch):
    module_file = tmp_path / "readable_mod.py"
    module_file.write_text("X = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    inspector = SUTInspector()
    module = importlib.import_module("readable_mod")
    source = inspector._read_module_source(module)
    assert source is not None
    assert "X = 1" in source


# ---------------------------------------------------------------------------
# usage-example inspection
# ---------------------------------------------------------------------------
def test_inspect_usage_examples():
    inspector = SUTInspector(project_root=".")
    examples = inspector.inspect_usage_examples("json", "dumps")
    assert isinstance(examples, str)


def test_inspect_usage_examples_no_project_root_returns_empty():
    inspector = SUTInspector()
    assert not inspector.inspect_usage_examples("json", "dumps")


def test_inspect_usage_examples_finds_call_site(tmp_path):
    (tmp_path / "usage.py").write_text(
        "from mymod import my_target\ndef use_it():\n    return my_target(1, 2)\n",
        encoding="utf-8",
    )
    inspector = SUTInspector(project_root=str(tmp_path))
    examples = inspector.inspect_usage_examples("mymod", "my_target")
    assert "my_target" in examples
    assert "### Example 1" in examples


def test_inspect_usage_examples_respects_max(tmp_path):
    (tmp_path / "usage.py").write_text(
        "def a():\n    return my_target(1)\n"
        "def b():\n    return my_target(2)\n"
        "def c():\n    return my_target(3)\n",
        encoding="utf-8",
    )
    inspector = SUTInspector(project_root=str(tmp_path))
    examples = inspector.inspect_usage_examples("mymod", "my_target", max_examples=2)
    assert examples.count("### Example") == 2


def test_resolve_usage_target_name_prefers_object_path():
    inspector = SUTInspector()
    assert inspector._resolve_usage_target_name("pkg.mod", "Cls.method") == "method"
    assert inspector._resolve_usage_target_name("pkg.mod", None) == "mod"


def test_ordered_python_files_puts_non_test_first(tmp_path):
    (tmp_path / "alpha.py").write_text("", encoding="utf-8")
    (tmp_path / "test_alpha.py").write_text("", encoding="utf-8")
    ordered = SUTInspector._ordered_python_files(tmp_path)
    names = [p.name for p in ordered]
    assert names.index("alpha.py") < names.index("test_alpha.py")


def test_extract_examples_from_file_skips_missing_name(tmp_path):
    file_path = tmp_path / "no_match.py"
    file_path.write_text("def foo():\n    return 1\n", encoding="utf-8")
    inspector = SUTInspector()
    assert inspector._extract_examples_from_file(file_path, "my_target") == []


def test_extract_examples_from_file_skips_giant_function(tmp_path):
    body = "\n".join(f"    x{i} = {i}" for i in range(30))
    file_path = tmp_path / "big.py"
    file_path.write_text(
        f"def huge():\n    my_target()\n{body}\n",
        encoding="utf-8",
    )
    inspector = SUTInspector()
    # The enclosing function exceeds the line cap and is dropped.
    assert inspector._extract_examples_from_file(file_path, "my_target") == []


def test_format_usage_examples_empty_returns_empty():
    assert not SUTInspector._format_usage_examples([])


def test_format_usage_examples_numbers_examples():
    formatted = SUTInspector._format_usage_examples(["a()", "b()"])
    assert "### Example 1" in formatted
    assert "### Example 2" in formatted


# ---------------------------------------------------------------------------
# module surface
# ---------------------------------------------------------------------------
def test_public_api_is_exposed():
    for attr in ("SUTInspector", "SUTInspectionResult", "InspectionTimeoutError"):
        assert hasattr(sut_inspector, attr)


def test_inspection_timeout_error_is_exception():
    with pytest.raises(InspectionTimeoutError):
        raise InspectionTimeoutError("x")
