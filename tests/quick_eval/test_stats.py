# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Tests for quick_eval's ``statistics.csv`` parsing and output-variable selection.

The quick_eval harness lives in ``utils/_quick_eval`` (outside ``src``); make it
importable the same way the ``utils/quick_eval.py`` entry point does.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_UTILS_DIR = Path(__file__).resolve().parents[2] / "utils"
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

from _quick_eval import console  # noqa: E402, PLC2701
from _quick_eval.report import print_results_table, results_to_json  # noqa: E402, PLC2701
from _quick_eval.runner import _build_output_vars  # noqa: E402, PLC2701
from _quick_eval.stats import ModuleResult, parse_statistics_csv  # noqa: E402, PLC2701


def _write_statistics_csv(report_dir: Path, row: dict[str, str]) -> None:
    csv_path = report_dir / "statistics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def test_build_output_vars_includes_mutation_denominator():
    # NumberOfCheckedMutants/NumberOfTimedOutMutants must be requested so the
    # degenerate all-timed-out case (score reported as N/A) is distinguishable
    # from a genuine perfect score in the collected statistics.
    output_vars = _build_output_vars(include_mutation=True, include_llm=False)
    parts = output_vars.split(",")
    assert "NumberOfCheckedMutants" in parts
    assert "NumberOfTimedOutMutants" in parts


def test_build_output_vars_without_mutation_omits_mutation_vars():
    output_vars = _build_output_vars(include_mutation=False, include_llm=False)
    parts = output_vars.split(",")
    assert "NumberOfCheckedMutants" not in parts
    assert "MutationScore" not in parts


def test_parse_statistics_csv_reads_checked_and_timed_out(tmp_path):
    _write_statistics_csv(
        tmp_path,
        {
            "BranchCoverage": "0.5",
            "MutationScore": "0.2",
            "NumberOfKilledMutants": "1",
            "NumberOfCreatedMutants": "5",
            "NumberOfCheckedMutants": "5",
            "NumberOfTimedOutMutants": "0",
        },
    )
    res = parse_statistics_csv(str(tmp_path))
    assert res["mutation_checked"] == 5
    assert res["mutation_timed_out"] == 0
    assert res["mutation_score"] == 0.2


def test_parse_statistics_csv_treats_none_mutation_score_as_unmeasurable(tmp_path):
    # Pynguin serializes the unmeasurable-score sentinel (every checked mutant
    # timed out) as the literal string "None" in statistics.csv. That must parse
    # as an absent score rather than raising and losing the rest of the row.
    _write_statistics_csv(
        tmp_path,
        {
            "BranchCoverage": "0.9",
            "MutationScore": "None",
            "NumberOfKilledMutants": "0",
            "NumberOfCreatedMutants": "35",
            "NumberOfCheckedMutants": "35",
            "NumberOfTimedOutMutants": "35",
        },
    )
    res = parse_statistics_csv(str(tmp_path))
    assert res["mutation_score"] is None
    assert res["branch_coverage"] == 0.9
    assert res["mutation_checked"] == 35
    assert res["mutation_timed_out"] == 35


def test_parse_statistics_csv_missing_file_returns_all_none(tmp_path):
    res = parse_statistics_csv(str(tmp_path))
    assert res["mutation_score"] is None
    assert res["mutation_checked"] is None


def test_build_output_vars_includes_llm_admitted_breakdown():
    output_vars = _build_output_vars(include_mutation=False, include_llm=True)
    parts = output_vars.split(",")
    for var in (
        "TotalLLMCalls",
        "TotalLLMInputTokens",
        "TotalLLMOutputTokens",
        "LLMQueryTime",
        "LLMAdmitted",
        "LLMAdmittedCompound",
        "LLMAdmittedUnresolvedCall",
        "LLMAdmittedImport",
    ):
        assert var in parts


def test_parse_statistics_csv_sums_llm_admitted_and_records_breakdown(tmp_path):
    _write_statistics_csv(
        tmp_path,
        {
            "BranchCoverage": "0.8",
            "TotalLLMCalls": "3",
            "LLMAdmitted": "10",
            "LLMAdmittedCompound": "3",
            "LLMAdmittedUnresolvedCall": "2",
            "LLMAdmittedImport": "1",
        },
    )
    res = parse_statistics_csv(str(tmp_path))
    assert res["llm_parsed_stmts"] == 16
    assert res["llm_compound"] == 3
    assert res["llm_unresolved"] == 2
    assert res["llm_import"] == 1


def test_parse_statistics_csv_llm_legacy_single_admitted(tmp_path):
    _write_statistics_csv(
        tmp_path,
        {
            "BranchCoverage": "0.8",
            "LLMAdmitted": "7",
        },
    )
    res = parse_statistics_csv(str(tmp_path))
    assert res["llm_parsed_stmts"] == 7
    assert res["llm_compound"] is None
    assert res["llm_unresolved"] is None
    assert res["llm_import"] is None


def test_parse_statistics_csv_llm_with_none_or_partial_columns(tmp_path):
    _write_statistics_csv(
        tmp_path,
        {
            "BranchCoverage": "0.8",
            "LLMAdmitted": "5",
            "LLMAdmittedCompound": "None",
            "LLMAdmittedImport": "2",
        },
    )
    res = parse_statistics_csv(str(tmp_path))
    assert res["llm_parsed_stmts"] == 7
    assert res["llm_compound"] is None
    assert res["llm_unresolved"] is None
    assert res["llm_import"] == 2


def test_report_includes_llm_breakdown(monkeypatch, capsys):
    monkeypatch.setattr(console, "_width", 200)
    monkeypatch.setattr(console, "_height", 50)
    result = ModuleResult(
        project="foo",
        module="bar",
        branch_coverage=0.8,
        line_coverage=0.9,
        duration_s=10.0,
        exit_code=0,
        llm_calls=2,
        llm_input_tokens=100,
        llm_output_tokens=50,
        llm_query_time_s=1.5,
        llm_parsed_stmts=16,
        llm_compound=3,
        llm_unresolved=2,
        llm_import=1,
    )
    # Verify table printing doesn't raise and shows breakdown values
    print_results_table([result])
    captured = capsys.readouterr()
    assert "Compound" in captured.out
    assert "Unresolved" in captured.out
    assert "Import" in captured.out

    # Verify JSON serialization includes the new fields
    data = results_to_json([result], git_ref="test", budget=60, seed=42)
    entry = data["results"][0]
    assert entry["llm_parsed_stmts"] == 16
    assert entry["llm_compound"] == 3
    assert entry["llm_unresolved"] == 2
    assert entry["llm_import"] == 1
