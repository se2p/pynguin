#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the focal-method AST analyzer (ast_analyzer.py)."""

from __future__ import annotations

import ast

from pynguin.refinement.ast_analyzer import (
    CallAndAssertCollector,
    FocalMethodAnalyzer,
    FocalMethodInfo,
    ImportMapBuilder,
)

MODULE_TEST = """\
import module_0

def test_case_0():
    var_0 = 5
    var_1 = module_0.add(var_0, var_0)
    assert var_1 == 10
"""


def test_import_map_handles_import_as():
    builder = ImportMapBuilder()
    builder.visit(ast.parse("import foo as bar\n"))
    assert builder.import_map["bar"] == "foo"


def test_import_map_handles_plain_import():
    builder = ImportMapBuilder()
    builder.visit(ast.parse("import foo\n"))
    assert builder.import_map["foo"] == "foo"


def test_import_map_handles_from_import_as():
    builder = ImportMapBuilder()
    builder.visit(ast.parse("from a.b import C as D\n"))
    assert builder.import_map["D"] == "a.b.C"


def test_call_collector_records_first_assert_line():
    collector = CallAndAssertCollector()
    collector.visit(ast.parse(MODULE_TEST))
    assert collector.first_assert_line == 6
    assert len(collector.calls) >= 1


def test_analyze_identifies_focal_method():
    result = FocalMethodAnalyzer(MODULE_TEST).analyze()
    assert isinstance(result, FocalMethodInfo)
    assert result.focal_method_name == "module_0.add"
    assert result.focal_line_number == 5
    assert result.module_alias == "module_0"
    assert result.resolved_module_name == "module_0"


def test_analyze_resolves_aliased_module():
    code = """\
import structlog as sl

def test_case_0():
    result = sl.get_logger()
    assert result is not None
"""
    result = FocalMethodAnalyzer(code).analyze()
    assert result is not None
    assert result.focal_method_name == "sl.get_logger"
    assert result.module_alias == "sl"
    assert result.resolved_module_name == "structlog"


def test_analyze_direct_function_call():
    code = """\
def test_case_0():
    result = make_widget()
    assert result is not None
"""
    result = FocalMethodAnalyzer(code).analyze()
    assert result is not None
    assert result.focal_method_name == "make_widget"
    assert result.module_alias == "make_widget"


def test_analyze_picks_last_call_before_assert():
    code = """\
def test_case_0():
    a = first_call()
    b = second_call()
    assert b == a
"""
    result = FocalMethodAnalyzer(code).analyze()
    assert result is not None
    assert result.focal_method_name == "second_call"


def test_analyze_returns_none_without_calls():
    code = "def test_case_0():\n    x = 5\n    assert x == 5\n"
    assert FocalMethodAnalyzer(code).analyze() is None


def test_analyze_handles_syntax_error():
    assert FocalMethodAnalyzer("def test(:\n    broken").analyze() is None
