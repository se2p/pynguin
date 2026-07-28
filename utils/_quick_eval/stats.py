# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""The result model and ``statistics.csv`` parsing for quick_eval."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import _LOG

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ModuleResult:
    """Coverage (and optional mutation/LLM) result for one Pynguin run."""

    project: str
    module: str
    branch_coverage: float | None
    line_coverage: float | None
    duration_s: float
    exit_code: int
    error: str | None = None
    mutation_score: float | None = None
    mutation_killed: int | None = None
    mutation_total: int | None = None
    llm_calls: int | None = None
    llm_input_tokens: int | None = None
    llm_output_tokens: int | None = None
    llm_query_time_s: float | None = None
    llm_parsed_stmts: int | None = None
    # Externally-measured coverage: the exported test suite run under coverage.py +
    # pytest, restricted to the module under test. Independent of Pynguin's own
    # statistics.csv number above — a gap between them flags a broken/optimistic suite.
    suite_coverage: float | None = None
    suite_tests: int | None = None
    suite_error: str | None = None


@dataclass(frozen=True)
class _StatSpec:
    """Maps a :class:`ModuleResult` field to its ``statistics.csv`` column(s)."""

    field: str
    columns: tuple[str, ...]
    convert: Callable[[str], float | int]


def _ns_to_s(raw: str) -> float:
    """Convert a nanosecond string to seconds."""
    return float(raw) / 1e9


# Declarative mapping from statistics.csv columns to ModuleResult fields. Adding a
# new metric is a one-line entry here — no branching in the parser.
_STAT_SPECS: tuple[_StatSpec, ...] = (
    _StatSpec("branch_coverage", ("BranchCoverage", "Coverage"), float),
    _StatSpec("line_coverage", ("LineCoverage",), float),
    _StatSpec("mutation_score", ("MutationScore",), float),
    _StatSpec("mutation_killed", ("NumberOfKilledMutants",), int),
    _StatSpec("mutation_total", ("NumberOfCreatedMutants",), int),
    _StatSpec("llm_calls", ("TotalLLMCalls",), int),
    _StatSpec("llm_input_tokens", ("TotalLLMInputTokens",), int),
    _StatSpec("llm_output_tokens", ("TotalLLMOutputTokens",), int),
    _StatSpec("llm_query_time_s", ("LLMQueryTime",), _ns_to_s),
    _StatSpec("llm_parsed_stmts", ("LLMAdmitted",), int),
)


def parse_statistics_csv(report_dir: str) -> dict[str, float | int | None]:
    """Return statistics from ``statistics.csv`` as a dictionary keyed by result field."""
    res: dict[str, float | int | None] = {spec.field: None for spec in _STAT_SPECS}
    csv_path = Path(report_dir) / "statistics.csv"
    if not csv_path.exists():
        return res
    try:
        with csv_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for spec in _STAT_SPECS:
                    raw = next((row[c] for c in spec.columns if row.get(c)), None)
                    if raw:
                        res[spec.field] = spec.convert(raw)
    except Exception as exc:  # noqa: BLE001
        _LOG.debug("Failed to parse statistics CSV in %s: %s", report_dir, exc)
    return res
