# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Rich table rendering, delta computation and JSON serialisation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich.table import Table

from . import console

if TYPE_CHECKING:
    from .stats import ModuleResult


@dataclass
class _DeltaEntry:
    module: str
    b_bc: float | None
    c_bc: float | None
    b_lc: float | None
    c_lc: float | None
    d_bc: float | None
    b_ms: float | None
    c_ms: float | None
    b_sc: float | None
    c_sc: float | None
    d_sc: float | None
    status: str


def fmt_pct(v: float | None) -> str:
    """Format a coverage fraction as a percentage string."""
    return f"{v * 100:.1f}%" if v is not None else "N/A"


def fmt_delta(b: float | None, c: float | None) -> str:
    """Format the signed delta between two coverage fractions."""
    if b is None or c is None:
        return "N/A"
    d = (c - b) * 100
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.1f}%"


def print_results_table(results: list[ModuleResult]) -> None:
    """Print a Rich table of coverage results."""
    show_mutation = any(r.mutation_score is not None for r in results)
    show_llm = any(r.llm_calls is not None for r in results)
    table = Table(title="Quick Eval Results")
    table.add_column("Project")
    table.add_column("Module")
    table.add_column("Branch Cov", justify="right")
    table.add_column("Line Cov", justify="right")
    table.add_column("Suite Cov", justify="right")
    if show_mutation:
        table.add_column("Mut Score", justify="right")
        table.add_column("Killed/Total", justify="right")
    if show_llm:
        table.add_column("LLM Calls", justify="right")
        table.add_column("LLM Tokens (I/O)", justify="right")
        table.add_column("LLM Time (s)", justify="right")
        table.add_column("Parsed Stmts", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("Exit")
    for r in sorted(results, key=lambda x: x.module):
        suite_cell = (
            fmt_pct(r.suite_coverage) if r.suite_coverage is not None else (r.suite_error or "N/A")
        )
        row = [
            r.project,
            r.module,
            fmt_pct(r.branch_coverage),
            fmt_pct(r.line_coverage),
            suite_cell,
        ]
        if show_mutation:
            row.append(fmt_pct(r.mutation_score))
            killed = r.mutation_killed if r.mutation_killed is not None else "?"
            total = r.mutation_total if r.mutation_total is not None else "?"
            row.append(f"{killed}/{total}")
        if show_llm:
            in_tok = r.llm_input_tokens if r.llm_input_tokens is not None else 0
            out_tok = r.llm_output_tokens if r.llm_output_tokens is not None else 0
            row.extend([
                str(r.llm_calls) if r.llm_calls is not None else "-",
                f"{in_tok}/{out_tok}" if (in_tok or out_tok) else "-",
                f"{r.llm_query_time_s:.1f}" if r.llm_query_time_s is not None else "-",
                str(r.llm_parsed_stmts) if r.llm_parsed_stmts is not None else "-",
            ])
        row += [f"{r.duration_s:.0f}", str(r.exit_code)]
        table.add_row(*row)
    console.print(table)


def _compute_deltas(baseline: list[dict], current: list[dict]) -> list[_DeltaEntry]:  # noqa: PLR0914
    """Compute per-module delta entries from baseline and current result lists."""
    base_by_mod = {r["module"]: r for r in baseline}
    curr_by_mod = {r["module"]: r for r in current}
    entries: list[_DeltaEntry] = []
    for mod in sorted(set(base_by_mod) | set(curr_by_mod)):
        b = base_by_mod.get(mod)
        c = curr_by_mod.get(mod)
        b_bc: float | None = b["branch_coverage"] if b else None
        c_bc: float | None = c["branch_coverage"] if c else None
        b_lc: float | None = b["line_coverage"] if b else None
        c_lc: float | None = c["line_coverage"] if c else None
        b_ms: float | None = b.get("mutation_score") if b else None
        c_ms: float | None = c.get("mutation_score") if c else None
        b_sc: float | None = b.get("suite_coverage") if b else None
        c_sc: float | None = c.get("suite_coverage") if c else None
        d_bc = (c_bc - b_bc) if (b_bc is not None and c_bc is not None) else None
        d_ms = (c_ms - b_ms) if (b_ms is not None and c_ms is not None) else None
        d_sc = (c_sc - b_sc) if (b_sc is not None and c_sc is not None) else None
        deltas = (d_bc, d_ms, d_sc)
        if any(d is not None and d < -0.001 for d in deltas):
            status = "REGRESSED"
        elif any(d is not None and d > 0.001 for d in deltas):
            status = "IMPROVED"
        else:
            status = "unchanged"
        entries.append(
            _DeltaEntry(
                module=mod,
                b_bc=b_bc,
                c_bc=c_bc,
                b_lc=b_lc,
                c_lc=c_lc,
                d_bc=d_bc,
                b_ms=b_ms,
                c_ms=c_ms,
                b_sc=b_sc,
                c_sc=c_sc,
                d_sc=d_sc,
                status=status,
            )
        )
    return entries


def print_delta_table(baseline: list[dict], current: list[dict]) -> int:
    """Print a coverage/mutation delta table and return 1 if any module regressed, else 0."""
    entries = _compute_deltas(baseline, current)
    show_mutation = any(e.b_ms is not None or e.c_ms is not None for e in entries)
    show_suite = any(e.b_sc is not None or e.c_sc is not None for e in entries)
    table = Table(title="Coverage Delta: baseline → current")
    table.add_column("Module")
    table.add_column("Branch (base)", justify="right")
    table.add_column("Branch (new)", justify="right")
    table.add_column("Δ Branch", justify="right")
    table.add_column("Line (base)", justify="right")
    table.add_column("Line (new)", justify="right")
    table.add_column("Δ Line", justify="right")
    if show_suite:
        table.add_column("Suite (base)", justify="right")
        table.add_column("Suite (new)", justify="right")
        table.add_column("Δ Suite", justify="right")
    if show_mutation:
        table.add_column("Mut (base)", justify="right")
        table.add_column("Mut (new)", justify="right")
        table.add_column("Δ Mut", justify="right")
    table.add_column("Status")
    status_markup = {"REGRESSED": "[red]REGRESSED[/red]", "IMPROVED": "[green]IMPROVED[/green]"}
    for e in entries:
        row = [
            e.module,
            fmt_pct(e.b_bc),
            fmt_pct(e.c_bc),
            fmt_delta(e.b_bc, e.c_bc),
            fmt_pct(e.b_lc),
            fmt_pct(e.c_lc),
            fmt_delta(e.b_lc, e.c_lc),
        ]
        if show_suite:
            row += [fmt_pct(e.b_sc), fmt_pct(e.c_sc), fmt_delta(e.b_sc, e.c_sc)]
        if show_mutation:
            row += [fmt_pct(e.b_ms), fmt_pct(e.c_ms), fmt_delta(e.b_ms, e.c_ms)]
        row.append(status_markup.get(e.status, e.status))
        table.add_row(*row)
    console.print(table)
    improved = sum(1 for e in entries if e.status == "IMPROVED")
    regressed = sum(1 for e in entries if e.status == "REGRESSED")
    unchanged = sum(1 for e in entries if e.status == "unchanged")
    console.print(f"\nSummary: {improved} improved, {regressed} regressed, {unchanged} unchanged")
    return 1 if regressed > 0 else 0


def results_to_json(results: list[ModuleResult], git_ref: str, budget: int, seed: int) -> dict:
    """Serialise a list of results to a JSON-compatible dict."""
    return {
        "meta": {
            "git_ref": git_ref,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "budget": budget,
            "seed": seed,
        },
        "results": [
            {
                "project": r.project,
                "module": r.module,
                "branch_coverage": r.branch_coverage,
                "line_coverage": r.line_coverage,
                "mutation_score": r.mutation_score,
                "mutation_killed": r.mutation_killed,
                "mutation_total": r.mutation_total,
                "llm_calls": r.llm_calls,
                "llm_input_tokens": r.llm_input_tokens,
                "llm_output_tokens": r.llm_output_tokens,
                "llm_query_time_s": r.llm_query_time_s,
                "llm_parsed_stmts": r.llm_parsed_stmts,
                "suite_coverage": r.suite_coverage,
                "suite_tests": r.suite_tests,
                "suite_error": r.suite_error,
                "duration_s": round(r.duration_s, 1),
                "exit_code": r.exit_code,
                "error": r.error,
            }
            for r in results
        ],
    }
