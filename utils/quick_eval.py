# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
r"""Quick evaluation script for Pynguin — fast local coverage feedback.

Usage:
  # Run eval on bundled example subjects (no external repo needed):
  python utils/quick_eval.py run --use-bundled-examples --budget 60 --jobs 4

  # Run eval on specific modules from a rundefinition XML:
  python utils/quick_eval.py run \\
      --rundefinition /path/to/coverage-check.xml \\
      --projects-dir /path/to/emse-projects \\
      --modules codetiming._timers flutes.timing \\
      --budget 60 --jobs 4 --save results.json

  # Compare two saved result files:
  python utils/quick_eval.py compare baseline.json feature.json

  # Compare current branch against another git ref using worktrees:
  python utils/quick_eval.py compare-branch main \\
      --use-bundled-examples --budget 60 --jobs 4
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import importlib.util
import json
import logging
import os
import shutil
import subprocess  # noqa: S404
import sys
import tempfile
import time
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

_LOG = logging.getLogger(__name__)
_console = Console()
_err_console = Console(stderr=True)
_GIT: str = shutil.which("git") or "git"
_VENV_CACHE_DIR = Path.home() / ".cache" / "pynguin-eval" / "venvs"

# Bundled example subjects — small packages installed in the project venv.
# Each entry: (project_name, top_level_package, [module_names_to_test])
BUNDLED_EXAMPLES: list[tuple[str, str, list[str]]] = [
    ("codetiming", "codetiming", ["codetiming._timers"]),
    ("first", "first", ["first"]),
    ("python-slugify", "slugify", ["slugify"]),
    ("tzlocal", "tzlocal", ["tzlocal"]),
    ("untangle", "untangle", ["untangle"]),
]


@dataclass
class ModuleTask:
    """Input specification for one Pynguin run."""

    project: str
    module: str
    project_path: str


@dataclass
class ModuleResult:
    """Coverage result for one Pynguin run."""

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
    status: str


def _fmt_pct(v: float | None) -> str:
    """Format a coverage fraction as a percentage string."""
    return f"{v * 100:.1f}%" if v is not None else "N/A"


def _fmt_delta(b: float | None, c: float | None) -> str:
    """Format the signed delta between two coverage fractions."""
    if b is None or c is None:
        return "N/A"
    d = (c - b) * 100
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.1f}%"


def _find_package_path(top_level_package: str) -> str | None:
    """Return the parent dir of an installed package, suitable as --project-path."""
    spec = importlib.util.find_spec(top_level_package)
    if spec is None:
        return None
    if spec.origin:
        return str(Path(spec.origin).parent.parent)
    if spec.submodule_search_locations:
        locs = list(spec.submodule_search_locations)
        if locs:
            return str(Path(locs[0]).parent)
    return None


def bundled_tasks() -> list[ModuleTask]:
    """Build a ModuleTask list from the bundled example subjects."""
    tasks: list[ModuleTask] = []
    for project, top_pkg, modules in BUNDLED_EXAMPLES:
        path = _find_package_path(top_pkg)
        if path is None:
            _console.print(f"[yellow][warn][/yellow] Cannot locate '{top_pkg}', skipping.")
            continue
        tasks.extend(
            ModuleTask(project=project, module=module, project_path=path) for module in modules
        )
    return tasks


def xml_tasks(
    rundefinition: str, projects_dir: str, modules_filter: list[str] | None
) -> list[ModuleTask]:
    """Build a ModuleTask list by parsing a rundefinition XML file."""
    tree = ET.parse(rundefinition)  # noqa: S314
    root = tree.getroot()
    tasks: list[ModuleTask] = []
    for project_elem in root.findall("project"):
        sources = project_elem.findtext("sources", "")
        project_name = project_elem.findtext("name", "")
        project_path = str(Path(projects_dir) / sources)
        for mod_elem in project_elem.findall("modules/module"):
            module_name = mod_elem.text or ""
            if modules_filter and module_name not in modules_filter:
                continue
            tasks.append(
                ModuleTask(project=project_name, module=module_name, project_path=project_path)
            )
    return tasks


def _parse_statistics_csv(
    report_dir: str,
) -> tuple[float | None, float | None, float | None, int | None, int | None]:
    """Return (branch_cov, line_cov, mutation_score, killed, total) from statistics.csv.

    Tries BranchCoverage first, falls back to Coverage (Pynguin's default column).
    Mutation fields are only present when --mutation is active (i.e., MutationScore was
    added to --output-variables).
    """
    csv_path = Path(report_dir) / "statistics.csv"
    if not csv_path.exists():
        return None, None, None, None, None
    branch_cov: float | None = None
    line_cov: float | None = None
    mutation_score: float | None = None
    killed: int | None = None
    total: int | None = None
    try:
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bc_str = row.get("BranchCoverage") or row.get("Coverage")
                if bc_str:
                    branch_cov = float(bc_str)
                lc_str = row.get("LineCoverage")
                if lc_str:
                    line_cov = float(lc_str)
                ms_str = row.get("MutationScore")
                if ms_str:
                    mutation_score = float(ms_str)
                k_str = row.get("NumberOfKilledMutants")
                if k_str:
                    killed = int(k_str)
                t_str = row.get("NumberOfCreatedMutants")
                if t_str:
                    total = int(t_str)
    except Exception as exc:  # noqa: BLE001
        _LOG.debug("Failed to parse statistics CSV in %s: %s", report_dir, exc)
    return branch_cov, line_cov, mutation_score, killed, total


def run_module(
    task: ModuleTask,
    budget: int,
    seed: int,
    python_exe: str,
    *,
    include_mutation: bool = False,
) -> ModuleResult:
    """Run Pynguin on one module and return its coverage (and optionally mutation) result."""
    if not Path(task.project_path).exists():
        return ModuleResult(
            project=task.project,
            module=task.module,
            branch_coverage=None,
            line_coverage=None,
            duration_s=0.0,
            exit_code=-1,
            error=f"project-path does not exist: {task.project_path}",
        )
    output_vars = "TargetModule,BranchCoverage"
    if include_mutation:
        output_vars += ",MutationScore,NumberOfKilledMutants,NumberOfCreatedMutants"
    with tempfile.TemporaryDirectory(prefix="pynguin_eval_") as tmpdir:
        start = time.monotonic()
        cmd = [
            python_exe,
            "-m",
            "pynguin",
            "--project-path",
            task.project_path,
            "--module-name",
            task.module,
            "--output-path",
            tmpdir,
            "--report-dir",
            tmpdir,
            "--maximum-search-time",
            str(budget),
            "--seed",
            str(seed),
            "--statistics-backend",
            "CSV",
            "--output-variables",
            output_vars,
        ]
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=budget + 120,
                check=False,
            )
            exit_code = proc.returncode
            error: str | None = proc.stderr[-500:] if proc.returncode != 0 and proc.stderr else None
        except subprocess.TimeoutExpired:
            exit_code = -1
            error = "timeout"
        duration = time.monotonic() - start
        branch_cov, line_cov, mut_score, mut_killed, mut_total = _parse_statistics_csv(tmpdir)
        return ModuleResult(
            project=task.project,
            module=task.module,
            branch_coverage=branch_cov,
            line_coverage=line_cov,
            duration_s=duration,
            exit_code=exit_code,
            error=error,
            mutation_score=mut_score,
            mutation_killed=mut_killed,
            mutation_total=mut_total,
        )


def run_eval(
    tasks: list[ModuleTask],
    budget: int,
    seed: int,
    jobs: int,
    *,
    python_exe: str = sys.executable,
    include_mutation: bool = False,
) -> list[ModuleResult]:
    """Run Pynguin on all tasks in parallel and return results."""
    results: list[ModuleResult] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                run_module, task, budget, seed, python_exe, include_mutation=include_mutation
            ): task
            for task in tasks
        }
        for future in concurrent.futures.as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = ModuleResult(
                    project=task.project,
                    module=task.module,
                    branch_coverage=None,
                    line_coverage=None,
                    duration_s=0.0,
                    exit_code=-1,
                    error=str(exc),
                )
            results.append(result)
            mut_info = (
                f" mut={_fmt_pct(result.mutation_score)}"
                f" ({result.mutation_killed}/{result.mutation_total})"
                if result.mutation_score is not None
                else ""
            )
            _console.print(
                f"  [{result.project}] {result.module}: "
                f"branch={_fmt_pct(result.branch_coverage)} "
                f"line={_fmt_pct(result.line_coverage)}"
                f"{mut_info} "
                f"({result.duration_s:.0f}s, exit={result.exit_code})"
            )
    return results


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
                "duration_s": round(r.duration_s, 1),
                "exit_code": r.exit_code,
                "error": r.error,
            }
            for r in results
        ],
    }


def _git_ref() -> str:
    """Return the current git short hash, or 'unknown' if not in a repo."""
    try:
        return subprocess.check_output(  # noqa: S603
            [_GIT, "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def print_results_table(results: list[ModuleResult]) -> None:
    """Print a Rich table of coverage results."""
    show_mutation = any(r.mutation_score is not None for r in results)
    table = Table(title="Quick Eval Results")
    table.add_column("Project")
    table.add_column("Module")
    table.add_column("Branch Cov", justify="right")
    table.add_column("Line Cov", justify="right")
    if show_mutation:
        table.add_column("Mut Score", justify="right")
        table.add_column("Killed/Total", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("Exit")
    for r in sorted(results, key=lambda x: x.module):
        row = [
            r.project,
            r.module,
            _fmt_pct(r.branch_coverage),
            _fmt_pct(r.line_coverage),
        ]
        if show_mutation:
            row.append(_fmt_pct(r.mutation_score))
            killed = r.mutation_killed if r.mutation_killed is not None else "?"
            total = r.mutation_total if r.mutation_total is not None else "?"
            row.append(f"{killed}/{total}")
        row += [f"{r.duration_s:.0f}", str(r.exit_code)]
        table.add_row(*row)
    _console.print(table)


def _compute_deltas(baseline: list[dict], current: list[dict]) -> list[_DeltaEntry]:
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
        d_bc = (c_bc - b_bc) if (b_bc is not None and c_bc is not None) else None
        d_ms = (c_ms - b_ms) if (b_ms is not None and c_ms is not None) else None
        if (d_bc is not None and d_bc < -0.001) or (d_ms is not None and d_ms < -0.001):
            status = "REGRESSED"
        elif (d_bc is not None and d_bc > 0.001) or (d_ms is not None and d_ms > 0.001):
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
                status=status,
            )
        )
    return entries


def print_delta_table(baseline: list[dict], current: list[dict]) -> int:
    """Print a coverage/mutation delta table and return 1 if any module regressed, else 0."""
    entries = _compute_deltas(baseline, current)
    show_mutation = any(e.b_ms is not None or e.c_ms is not None for e in entries)
    table = Table(title="Coverage Delta: baseline → current")
    table.add_column("Module")
    table.add_column("Branch (base)", justify="right")
    table.add_column("Branch (new)", justify="right")
    table.add_column("Δ Branch", justify="right")
    table.add_column("Line (base)", justify="right")
    table.add_column("Line (new)", justify="right")
    table.add_column("Δ Line", justify="right")
    if show_mutation:
        table.add_column("Mut (base)", justify="right")
        table.add_column("Mut (new)", justify="right")
        table.add_column("Δ Mut", justify="right")
    table.add_column("Status")
    status_markup = {"REGRESSED": "[red]REGRESSED[/red]", "IMPROVED": "[green]IMPROVED[/green]"}
    for e in entries:
        row = [
            e.module,
            _fmt_pct(e.b_bc),
            _fmt_pct(e.c_bc),
            _fmt_delta(e.b_bc, e.c_bc),
            _fmt_pct(e.b_lc),
            _fmt_pct(e.c_lc),
            _fmt_delta(e.b_lc, e.c_lc),
        ]
        if show_mutation:
            row += [_fmt_pct(e.b_ms), _fmt_pct(e.c_ms), _fmt_delta(e.b_ms, e.c_ms)]
        row.append(status_markup.get(e.status, e.status))
        table.add_row(*row)
    _console.print(table)
    improved = sum(1 for e in entries if e.status == "IMPROVED")
    regressed = sum(1 for e in entries if e.status == "REGRESSED")
    unchanged = sum(1 for e in entries if e.status == "unchanged")
    _console.print(f"\nSummary: {improved} improved, {regressed} regressed, {unchanged} unchanged")
    return 1 if regressed > 0 else 0


def _resolve_full_hash(git_ref: str) -> str:
    """Resolve a git ref to its full commit hash."""
    return subprocess.check_output(  # noqa: S603
        [_GIT, "rev-parse", git_ref], text=True
    ).strip()


def _build_worktree_venv(git_ref: str) -> tuple[str | None, str]:
    """Return (worktree_dir_or_None, python_exe) for the given git ref.

    The venv is cached at ~/.cache/pynguin-eval/venvs/{full_hash}/ so repeated
    calls for the same commit reuse it without re-installing. Uses a non-editable
    install so the venv survives worktree removal.
    """
    full_hash = _resolve_full_hash(git_ref)
    venv_dir = _VENV_CACHE_DIR / full_hash
    venv_python = str(venv_dir / "bin" / "python")
    if venv_dir.exists() and Path(venv_python).exists():
        _console.print(f"Reusing cached venv for {git_ref} ({full_hash[:12]}) at {venv_dir}")
        return None, venv_python
    worktree_dir = tempfile.mkdtemp(prefix=f"pynguin_worktree_{git_ref}_")
    _console.print(
        f"Creating git worktree for '{git_ref}' ({full_hash[:12]}) at {worktree_dir} ..."
    )
    subprocess.run(  # noqa: S603
        [_GIT, "worktree", "add", "--detach", worktree_dir, git_ref],
        check=True,
    )
    venv_dir.mkdir(parents=True, exist_ok=True)
    _console.print(f"Creating venv at {venv_dir} ...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)  # noqa: S603
    _console.print("Installing pynguin from worktree (non-editable, cached) ...")
    subprocess.run(  # noqa: S603
        [venv_python, "-m", "pip", "install", worktree_dir, "--quiet"],
        check=True,
    )
    return worktree_dir, venv_python


def _remove_worktree(worktree_dir: str | None) -> None:
    """Remove a git worktree created by _build_worktree_venv, if any."""
    if worktree_dir is None:
        return
    subprocess.run(  # noqa: S603
        [_GIT, "worktree", "remove", "--force", worktree_dir],
        check=False,
    )


def _resolve_tasks(args: argparse.Namespace) -> list[ModuleTask] | None:
    """Resolve the task list from --use-bundled-examples or --rundefinition args."""
    if args.use_bundled_examples:
        tasks = bundled_tasks()
        if args.modules:
            tasks = [t for t in tasks if t.module in args.modules]
    elif args.rundefinition:
        tasks = xml_tasks(args.rundefinition, args.projects_dir, args.modules)
    else:
        _err_console.print("Error: specify --use-bundled-examples or --rundefinition")
        return None
    if not tasks:
        _err_console.print("No tasks found.")
        return None
    return tasks


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the 'run' subcommand: evaluate coverage for selected modules."""
    tasks = _resolve_tasks(args)
    if tasks is None:
        return 1
    jobs = args.jobs or max(1, (os.cpu_count() or 2) // 2)
    _console.print(
        f"Running {len(tasks)} module(s) with budget={args.budget}s, jobs={jobs}, seed={args.seed}"
    )
    results = run_eval(tasks, args.budget, args.seed, jobs, include_mutation=args.mutation)
    _console.print()
    print_results_table(results)
    if args.save:
        data = results_to_json(results, _git_ref(), args.budget, args.seed)
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(data, indent=2), encoding="utf-8")
        _console.print(f"\nResults saved to {args.save}")
    if args.output == "json":
        data = results_to_json(results, _git_ref(), args.budget, args.seed)
        _console.print(json.dumps(data, indent=2))
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Execute the 'compare' subcommand: diff two saved result JSON files."""
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    _console.print(
        f"Baseline: {args.baseline} "
        f"(ref={baseline['meta']['git_ref']}, t={baseline['meta']['timestamp']})"
    )
    _console.print(
        f"Current:  {args.current} "
        f"(ref={current['meta']['git_ref']}, t={current['meta']['timestamp']})"
    )
    _console.print()
    return print_delta_table(baseline["results"], current["results"])


def cmd_compare_branch(args: argparse.Namespace) -> int:
    """Execute the 'compare-branch' subcommand: compare current branch vs a git ref."""
    tasks = _resolve_tasks(args)
    if tasks is None:
        return 1
    jobs = args.jobs or max(1, (os.cpu_count() or 2) // 2)
    worktree_dir, base_python = _build_worktree_venv(args.ref)
    try:
        _console.print(
            f"\nRunning baseline ({args.ref}) with budget={args.budget}s, jobs={jobs} ..."
        )
        base_results = run_eval(
            tasks,
            args.budget,
            args.seed,
            jobs,
            python_exe=base_python,
            include_mutation=args.mutation,
        )
        _console.print(f"\nRunning current branch with budget={args.budget}s, jobs={jobs} ...")
        curr_results = run_eval(tasks, args.budget, args.seed, jobs, include_mutation=args.mutation)
    finally:
        _remove_worktree(worktree_dir)
    base_data = results_to_json(base_results, args.ref, args.budget, args.seed)
    curr_data = results_to_json(curr_results, _git_ref(), args.budget, args.seed)
    if args.save_baseline:
        Path(args.save_baseline).write_text(json.dumps(base_data, indent=2), encoding="utf-8")
        _console.print(f"Baseline results saved to {args.save_baseline}")
    if args.save_current:
        Path(args.save_current).write_text(json.dumps(curr_data, indent=2), encoding="utf-8")
        _console.print(f"Current results saved to {args.save_current}")
    _console.print()
    return print_delta_table(base_data["results"], curr_data["results"])


def main() -> int:
    """Parse CLI arguments and dispatch to the appropriate subcommand."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run eval and optionally save results")
    p_run.add_argument(
        "--use-bundled-examples", action="store_true", help="Use the bundled example subjects"
    )
    p_run.add_argument("--rundefinition", help="Path to rundefinition XML")
    p_run.add_argument("--projects-dir", help="Base directory for project sources in the XML")
    p_run.add_argument("--modules", nargs="+", help="Filter to specific module names")
    p_run.add_argument(
        "--budget", type=int, default=60, help="Time budget per module in seconds (default: 60)"
    )
    p_run.add_argument("--seed", type=int, default=0, help="Random seed (default: 0)")
    p_run.add_argument("--jobs", type=int, default=None, help="Parallel workers (default: cpu/2)")
    p_run.add_argument("--save", metavar="FILE", help="Save results as JSON to FILE")
    p_run.add_argument("--output", choices=["table", "json"], default="table")
    p_run.add_argument(
        "--mutation",
        action="store_true",
        help="Capture mutation score (uses Pynguin's built-in mutation analysis)",
    )

    p_cmp = sub.add_parser("compare", help="Compare two saved result JSON files")
    p_cmp.add_argument("baseline", help="Baseline results JSON file")
    p_cmp.add_argument("current", help="Current results JSON file")

    p_cb = sub.add_parser(
        "compare-branch", help="Compare current branch against a git ref using worktrees"
    )
    p_cb.add_argument("ref", help="Git ref to compare against (e.g. 'main')")
    p_cb.add_argument("--use-bundled-examples", action="store_true")
    p_cb.add_argument("--rundefinition")
    p_cb.add_argument("--projects-dir")
    p_cb.add_argument("--modules", nargs="+")
    p_cb.add_argument("--budget", type=int, default=60)
    p_cb.add_argument("--seed", type=int, default=0)
    p_cb.add_argument("--jobs", type=int, default=None)
    p_cb.add_argument("--save-baseline", metavar="FILE")
    p_cb.add_argument("--save-current", metavar="FILE")
    p_cb.add_argument(
        "--mutation",
        action="store_true",
        help="Capture mutation score (uses Pynguin's built-in mutation analysis)",
    )

    args = parser.parse_args()
    if args.command == "run":
        return cmd_run(args)
    if args.command == "compare":
        return cmd_compare(args)
    if args.command == "compare-branch":
        return cmd_compare_branch(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
