# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Bodies of the ``run`` / ``compare`` / ``compare-branch`` subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from . import console
from .report import print_delta_table, print_results_table, results_to_json
from .runner import run_eval
from .tasks import resolve_tasks
from .worktree import build_worktree_venv, git_ref, remove_worktree

if TYPE_CHECKING:
    import argparse


# Default parallelism: a rundefinition typically has ~5 modules, and compare-branch
# runs baseline + current, so 10 workers keeps a standard comparison fully parallel.
_DEFAULT_JOBS = 10


def _jobs(args: argparse.Namespace) -> int:
    """Resolve the worker count, defaulting to _DEFAULT_JOBS."""
    return args.jobs or _DEFAULT_JOBS


def cmd_run(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Execute the 'run' subcommand: evaluate coverage for selected modules."""
    tasks = resolve_tasks(
        use_bundled=args.use_bundled_examples,
        rundefinition=args.rundefinition,
        projects_dir=args.projects_dir,
        modules=args.modules,
    )
    if tasks is None:
        return 1
    jobs = _jobs(args)
    console.print(
        f"Running {len(tasks)} module(s) with budget={args.budget}s, jobs={jobs}, seed={args.seed}"
    )
    results = run_eval(
        tasks,
        args.budget,
        args.seed,
        jobs,
        include_mutation=args.mutation,
        llm_mode=args.llm_mode,
        timeout=args.timeout,
        extra_args=extra_args,
    )
    console.print()
    print_results_table(results)
    if args.save:
        data = results_to_json(results, git_ref(), args.budget, args.seed)
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"\nResults saved to {args.save}")
    if args.output == "json":
        data = results_to_json(results, git_ref(), args.budget, args.seed)
        console.print(json.dumps(data, indent=2))
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Execute the 'compare' subcommand: diff two saved result JSON files."""
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    console.print(
        f"Baseline: {args.baseline} "
        f"(ref={baseline['meta']['git_ref']}, t={baseline['meta']['timestamp']})"
    )
    console.print(
        f"Current:  {args.current} "
        f"(ref={current['meta']['git_ref']}, t={current['meta']['timestamp']})"
    )
    console.print()
    return print_delta_table(baseline["results"], current["results"])


def cmd_compare_branch(args: argparse.Namespace, extra_args: list[str]) -> int:
    """Execute the 'compare-branch' subcommand: compare current branch vs a git ref."""
    tasks = resolve_tasks(
        use_bundled=args.use_bundled_examples,
        rundefinition=args.rundefinition,
        projects_dir=args.projects_dir,
        modules=args.modules,
    )
    if tasks is None:
        return 1
    jobs = _jobs(args)
    worktree_dir, base_python = build_worktree_venv(args.ref)
    try:
        console.print(
            f"\nRunning baseline ({args.ref}) with budget={args.budget}s, jobs={jobs} ..."
        )
        base_results = run_eval(
            tasks,
            args.budget,
            args.seed,
            jobs,
            python_exe=base_python,
            include_mutation=args.mutation,
            llm_mode=args.llm_mode,
            timeout=args.timeout,
            extra_args=extra_args,
        )
        console.print(f"\nRunning current branch with budget={args.budget}s, jobs={jobs} ...")
        curr_results = run_eval(
            tasks,
            args.budget,
            args.seed,
            jobs,
            include_mutation=args.mutation,
            llm_mode=args.llm_mode,
            timeout=args.timeout,
            extra_args=extra_args,
        )
    finally:
        remove_worktree(worktree_dir)
    base_data = results_to_json(base_results, args.ref, args.budget, args.seed)
    curr_data = results_to_json(curr_results, git_ref(), args.budget, args.seed)
    if args.save_baseline:
        Path(args.save_baseline).write_text(json.dumps(base_data, indent=2), encoding="utf-8")
        console.print(f"Baseline results saved to {args.save_baseline}")
    if args.save_current:
        Path(args.save_current).write_text(json.dumps(curr_data, indent=2), encoding="utf-8")
        console.print(f"Current results saved to {args.save_current}")
    console.print()
    return print_delta_table(base_data["results"], curr_data["results"])
