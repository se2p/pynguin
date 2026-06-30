# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Quick evaluation script for Pynguin — fast local coverage feedback.

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
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

try:
    from rich.console import Console
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


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
    project: str
    module: str
    project_path: str


@dataclass
class ModuleResult:
    project: str
    module: str
    branch_coverage: float | None
    line_coverage: float | None
    duration_s: float
    exit_code: int
    error: str | None = None


def _find_package_path(top_level_package: str) -> str | None:
    """Return the parent directory of the installed package (suitable as --project-path)."""
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
    """Build ModuleTask list from the bundled examples."""
    tasks: list[ModuleTask] = []
    for project, top_pkg, modules in BUNDLED_EXAMPLES:
        path = _find_package_path(top_pkg)
        if path is None:
            print(f"[warn] Could not locate installed package '{top_pkg}', skipping.")
            continue
        for module in modules:
            tasks.append(ModuleTask(project=project, module=module, project_path=path))
    return tasks


def xml_tasks(rundefinition: str, projects_dir: str, modules_filter: list[str] | None) -> list[ModuleTask]:
    """Build ModuleTask list by parsing a rundefinition XML file."""
    tree = ET.parse(rundefinition)
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
            tasks.append(ModuleTask(project=project_name, module=module_name, project_path=project_path))
    return tasks


def _parse_statistics_csv(report_dir: str) -> tuple[float | None, float | None]:
    """Return (branch_coverage, line_coverage) from statistics.csv, or (None, None).

    Tries BranchCoverage first, falls back to Coverage (Pynguin's default column name).
    LineCoverage is only populated when the LINE coverage metric is enabled.
    """
    csv_path = Path(report_dir) / "statistics.csv"
    if not csv_path.exists():
        return None, None
    branch_cov: float | None = None
    line_cov: float | None = None
    try:
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key in ("BranchCoverage", "Coverage"):
                    if row.get(key):
                        branch_cov = float(row[key])
                        break
                for key in ("LineCoverage",):
                    if row.get(key):
                        line_cov = float(row[key])
                        break
    except Exception:  # noqa: BLE001
        pass
    return branch_cov, line_cov


def run_module(task: ModuleTask, budget: int, seed: int, python_exe: str) -> ModuleResult:
    """Run Pynguin on one module and return its coverage result."""
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
    with tempfile.TemporaryDirectory(prefix="pynguin_eval_") as tmpdir:
        start = time.monotonic()
        cmd = [
            python_exe, "-m", "pynguin",
            "--project-path", task.project_path,
            "--module-name", task.module,
            "--output-path", tmpdir,
            "--report-dir", tmpdir,
            "--maximum-search-time", str(budget),
            "--seed", str(seed),
            "--statistics-backend", "CSV",
            "--output-variables", "TargetModule,BranchCoverage",
        ]
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=budget + 120,
            )
            exit_code = proc.returncode
            error = proc.stderr[-500:] if proc.returncode != 0 and proc.stderr else None
        except subprocess.TimeoutExpired:
            exit_code = -1
            error = "timeout"
        duration = time.monotonic() - start
        branch_cov, line_cov = _parse_statistics_csv(tmpdir)
        return ModuleResult(
            project=task.project,
            module=task.module,
            branch_coverage=branch_cov,
            line_coverage=line_cov,
            duration_s=duration,
            exit_code=exit_code,
            error=error,
        )


def run_eval(
    tasks: list[ModuleTask],
    budget: int,
    seed: int,
    jobs: int,
    python_exe: str = sys.executable,
) -> list[ModuleResult]:
    """Run Pynguin on all tasks in parallel and return results."""
    results: list[ModuleResult] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(run_module, task, budget, seed, python_exe): task
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
            _pct = lambda v: f"{v*100:.1f}%" if v is not None else "N/A"
            print(
                f"  [{result.project}] {result.module}: "
                f"branch={_pct(result.branch_coverage)} "
                f"line={_pct(result.line_coverage)} "
                f"({result.duration_s:.0f}s, exit={result.exit_code})"
            )
    return results


def results_to_json(results: list[ModuleResult], git_ref: str, budget: int, seed: int) -> dict:
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
                "duration_s": round(r.duration_s, 1),
                "exit_code": r.exit_code,
                "error": r.error,
            }
            for r in results
        ],
    }


def _git_ref() -> str:
    try:
        return subprocess.check_output(  # noqa: S603 S607
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def print_results_table(results: list[ModuleResult]) -> None:
    _pct = lambda v: f"{v*100:.1f}%" if v is not None else "N/A"
    if _RICH:
        console = Console()
        table = Table(title="Quick Eval Results")
        table.add_column("Project")
        table.add_column("Module")
        table.add_column("Branch Cov", justify="right")
        table.add_column("Line Cov", justify="right")
        table.add_column("Time (s)", justify="right")
        table.add_column("Exit")
        for r in sorted(results, key=lambda x: x.module):
            table.add_row(
                r.project,
                r.module,
                _pct(r.branch_coverage),
                _pct(r.line_coverage),
                f"{r.duration_s:.0f}",
                str(r.exit_code),
            )
        console.print(table)
    else:
        header = f"{'Project':<20} {'Module':<40} {'Branch':>8} {'Line':>8} {'Time':>6} Exit"
        print(header)
        print("-" * len(header))
        for r in sorted(results, key=lambda x: x.module):
            print(f"{r.project:<20} {r.module:<40} {_pct(r.branch_coverage):>8} {_pct(r.line_coverage):>8} {r.duration_s:>5.0f}s {r.exit_code}")


def print_delta_table(baseline: list[dict], current: list[dict]) -> int:
    """Print a delta table comparing baseline vs current. Returns 1 if any regression, else 0."""
    base_by_mod = {r["module"]: r for r in baseline}
    curr_by_mod = {r["module"]: r for r in current}
    all_modules = sorted(set(base_by_mod) | set(curr_by_mod))

    improved = regressed = unchanged = 0

    def _pct(v: float | None) -> str:
        return f"{v*100:.1f}%" if v is not None else "N/A"

    def _delta(b: float | None, c: float | None) -> str:
        if b is None or c is None:
            return "N/A"
        d = (c - b) * 100
        sign = "+" if d > 0 else ""
        return f"{sign}{d:.1f}%"

    if _RICH:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="Coverage Delta: baseline → current")
        table.add_column("Module")
        table.add_column("Branch (base)", justify="right")
        table.add_column("Branch (new)", justify="right")
        table.add_column("Δ Branch", justify="right")
        table.add_column("Line (base)", justify="right")
        table.add_column("Line (new)", justify="right")
        table.add_column("Δ Line", justify="right")
        table.add_column("Status")
        for mod in all_modules:
            b = base_by_mod.get(mod)
            c = curr_by_mod.get(mod)
            b_bc = b["branch_coverage"] if b else None
            c_bc = c["branch_coverage"] if c else None
            b_lc = b["line_coverage"] if b else None
            c_lc = c["line_coverage"] if c else None
            d_bc = (c_bc - b_bc) if (b_bc is not None and c_bc is not None) else None
            d_lc = (c_lc - b_lc) if (b_lc is not None and c_lc is not None) else None
            if d_bc is not None and d_bc < -0.001:
                status = "[red]REGRESSED[/red]"
                regressed += 1
            elif d_bc is not None and d_bc > 0.001:
                status = "[green]IMPROVED[/green]"
                improved += 1
            else:
                status = "unchanged"
                unchanged += 1
            table.add_row(
                mod,
                _pct(b_bc), _pct(c_bc), _delta(b_bc, c_bc),
                _pct(b_lc), _pct(c_lc), _delta(b_lc, c_lc),
                status,
            )
        console.print(table)
    else:
        header = f"{'Module':<40} {'Br-base':>8} {'Br-new':>8} {'ΔBr':>8} {'Ln-base':>8} {'Ln-new':>8} {'ΔLn':>8} Status"
        print(header)
        print("-" * len(header))
        for mod in all_modules:
            b = base_by_mod.get(mod)
            c = curr_by_mod.get(mod)
            b_bc = b["branch_coverage"] if b else None
            c_bc = c["branch_coverage"] if c else None
            b_lc = b["line_coverage"] if b else None
            c_lc = c["line_coverage"] if c else None
            d_bc = (c_bc - b_bc) if (b_bc is not None and c_bc is not None) else None
            if d_bc is not None and d_bc < -0.001:
                status = "REGRESSED"
                regressed += 1
            elif d_bc is not None and d_bc > 0.001:
                status = "IMPROVED"
                improved += 1
            else:
                status = "unchanged"
                unchanged += 1
            print(f"{mod:<40} {_pct(b_bc):>8} {_pct(c_bc):>8} {_delta(b_bc, c_bc):>8} {_pct(b_lc):>8} {_pct(c_lc):>8} {_delta(b_lc, c_lc):>8} {status}")

    print(f"\nSummary: {improved} improved, {regressed} regressed, {unchanged} unchanged")
    return 1 if regressed > 0 else 0


def _build_worktree_venv(git_ref: str) -> tuple[str, str]:
    """Create a git worktree for git_ref and install pynguin there. Returns (worktree_dir, python_exe)."""
    tmpdir = tempfile.mkdtemp(prefix=f"pynguin_worktree_{git_ref}_")
    print(f"Creating git worktree for '{git_ref}' at {tmpdir} ...")
    subprocess.run(  # noqa: S603 S607
        ["git", "worktree", "add", "--detach", tmpdir, git_ref],
        check=True,
    )
    venv_dir = os.path.join(tmpdir, ".eval_venv")
    print(f"Creating venv at {venv_dir} ...")
    subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)  # noqa: S603 S607
    venv_python = os.path.join(venv_dir, "bin", "python")
    print(f"Installing pynguin from worktree ...")
    subprocess.run(  # noqa: S603 S607
        [venv_python, "-m", "pip", "install", "-e", tmpdir, "--quiet"],
        check=True,
    )
    return tmpdir, venv_python


def _remove_worktree(worktree_dir: str) -> None:
    subprocess.run(  # noqa: S603 S607
        ["git", "worktree", "remove", "--force", worktree_dir],
        check=False,
    )


def cmd_run(args: argparse.Namespace) -> int:
    if args.use_bundled_examples:
        tasks = bundled_tasks()
        if args.modules:
            tasks = [t for t in tasks if t.module in args.modules]
    elif args.rundefinition:
        tasks = xml_tasks(args.rundefinition, args.projects_dir, args.modules)
    else:
        print("Error: specify --use-bundled-examples or --rundefinition", file=sys.stderr)
        return 1

    if not tasks:
        print("No tasks found.", file=sys.stderr)
        return 1

    jobs = args.jobs or max(1, (os.cpu_count() or 2) // 2)
    print(f"Running {len(tasks)} module(s) with budget={args.budget}s, jobs={jobs}, seed={args.seed}")
    results = run_eval(tasks, args.budget, args.seed, jobs)
    print()
    print_results_table(results)

    if args.save:
        data = results_to_json(results, _git_ref(), args.budget, args.seed)
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(data, indent=2))
        print(f"\nResults saved to {args.save}")

    if args.output == "json":
        data = results_to_json(results, _git_ref(), args.budget, args.seed)
        print(json.dumps(data, indent=2))

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    baseline = json.loads(Path(args.baseline).read_text())
    current = json.loads(Path(args.current).read_text())
    print(f"Baseline: {args.baseline} (ref={baseline['meta']['git_ref']}, t={baseline['meta']['timestamp']})")
    print(f"Current:  {args.current} (ref={current['meta']['git_ref']}, t={current['meta']['timestamp']})")
    print()
    return print_delta_table(baseline["results"], current["results"])


def cmd_compare_branch(args: argparse.Namespace) -> int:
    if args.use_bundled_examples:
        tasks = bundled_tasks()
        if args.modules:
            tasks = [t for t in tasks if t.module in args.modules]
    elif args.rundefinition:
        tasks = xml_tasks(args.rundefinition, args.projects_dir, args.modules)
    else:
        print("Error: specify --use-bundled-examples or --rundefinition", file=sys.stderr)
        return 1

    if not tasks:
        print("No tasks found.", file=sys.stderr)
        return 1

    jobs = args.jobs or max(1, (os.cpu_count() or 2) // 2)

    worktree_dir, base_python = _build_worktree_venv(args.ref)
    try:
        print(f"\nRunning baseline ({args.ref}) with budget={args.budget}s, jobs={jobs} ...")
        base_results = run_eval(tasks, args.budget, args.seed, jobs, python_exe=base_python)

        print(f"\nRunning current branch with budget={args.budget}s, jobs={jobs} ...")
        curr_results = run_eval(tasks, args.budget, args.seed, jobs)
    finally:
        _remove_worktree(worktree_dir)

    base_data = results_to_json(base_results, args.ref, args.budget, args.seed)
    curr_data = results_to_json(curr_results, _git_ref(), args.budget, args.seed)

    if args.save_baseline:
        Path(args.save_baseline).write_text(json.dumps(base_data, indent=2))
        print(f"Baseline results saved to {args.save_baseline}")
    if args.save_current:
        Path(args.save_current).write_text(json.dumps(curr_data, indent=2))
        print(f"Current results saved to {args.save_current}")

    print()
    return print_delta_table(base_data["results"], curr_data["results"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    p_run = sub.add_parser("run", help="Run eval and optionally save results")
    p_run.add_argument("--use-bundled-examples", action="store_true", help="Use the bundled example subjects")
    p_run.add_argument("--rundefinition", help="Path to rundefinition XML (e.g. coverage-check.xml)")
    p_run.add_argument("--projects-dir", help="Base directory for project sources referenced in the XML")
    p_run.add_argument("--modules", nargs="+", help="Filter to specific module names")
    p_run.add_argument("--budget", type=int, default=60, help="Time budget per module in seconds (default: 60)")
    p_run.add_argument("--seed", type=int, default=0, help="Random seed (default: 0)")
    p_run.add_argument("--jobs", type=int, default=None, help="Parallel workers (default: cpu_count/2)")
    p_run.add_argument("--save", metavar="FILE", help="Save results as JSON to FILE")
    p_run.add_argument("--output", choices=["table", "json"], default="table", help="Output format")

    # --- compare ---
    p_cmp = sub.add_parser("compare", help="Compare two saved result JSON files")
    p_cmp.add_argument("baseline", help="Baseline results JSON file")
    p_cmp.add_argument("current", help="Current results JSON file")

    # --- compare-branch ---
    p_cb = sub.add_parser("compare-branch", help="Compare current branch against a git ref using worktrees")
    p_cb.add_argument("ref", help="Git ref to compare against (e.g. 'main')")
    p_cb.add_argument("--use-bundled-examples", action="store_true")
    p_cb.add_argument("--rundefinition")
    p_cb.add_argument("--projects-dir")
    p_cb.add_argument("--modules", nargs="+")
    p_cb.add_argument("--budget", type=int, default=60)
    p_cb.add_argument("--seed", type=int, default=0)
    p_cb.add_argument("--jobs", type=int, default=None)
    p_cb.add_argument("--save-baseline", metavar="FILE", help="Save baseline results to FILE")
    p_cb.add_argument("--save-current", metavar="FILE", help="Save current results to FILE")

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
