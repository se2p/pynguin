# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Argument parsing and subcommand dispatch for quick_eval."""

from __future__ import annotations

import argparse

from . import DEFAULT_TIMEOUT_S
from .commands import cmd_compare, cmd_compare_branch, cmd_run
from .runner import LLM_MODE_FULL, LLM_MODE_MIN, LLM_MODE_NONE

_DESCRIPTION = r"""Quick evaluation script for Pynguin — fast local coverage feedback.

Usage:
  # Run eval on bundled example subjects (no external repo needed):
  python utils/quick_eval.py run --use-bundled-examples --budget 60 --jobs 4

  # Run eval on a rundefinition from ../pynguin-experiments (bare name is resolved
  # against pynguin-experiments/rundefinitions/, --projects-dir defaults to
  # pynguin-experiments/projects):
  python utils/quick_eval.py run --rundefinition coverage-check \
      --modules codetiming._timers --budget 60 --jobs 4 --save results.json

  # Compare two saved result files:
  python utils/quick_eval.py compare baseline.json feature.json

  # Compare current branch against another git ref using worktrees:
  python utils/quick_eval.py compare-branch main \
      --use-bundled-examples --budget 60 --jobs 4
"""


def _add_task_selection(parser: argparse.ArgumentParser) -> None:
    """Add the shared task-selection flags to a subparser."""
    parser.add_argument(
        "--use-bundled-examples", action="store_true", help="Use the bundled example subjects"
    )
    parser.add_argument(
        "--rundefinition",
        help="Rundefinition XML path or a bare name resolved against "
        "../pynguin-experiments/rundefinitions/",
    )
    parser.add_argument(
        "--projects-dir",
        help="Base directory for project sources (default: ../pynguin-experiments/projects)",
    )
    parser.add_argument("--modules", nargs="+", help="Filter to specific module names")


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    """Add the shared run-configuration flags (budget/seed/jobs/metrics)."""
    parser.add_argument(
        "--budget",
        type=int,
        default=120,
        help=(
            "Time budget per module in seconds (default: 120). Must exceed the 30s stall "
            "window + 45s late-budget guard (=75s) for stall-triggered LLM calls to fire; "
            "120s leaves headroom for the request round-trip and integration."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help=(
            "Wall-clock limit per module run in seconds, covering post-search work such as "
            f"mutation analysis (default: {DEFAULT_TIMEOUT_S})"
        ),
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed (default: 0)")
    parser.add_argument("--jobs", type=int, default=None, help="Parallel workers (default: 10)")
    parser.add_argument(
        "--mutation",
        action="store_true",
        help="Capture mutation score (uses Pynguin's built-in mutation analysis)",
    )
    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument(
        "--llm",
        dest="llm_mode",
        action="store_const",
        const=LLM_MODE_FULL,
        help="Full LLM mode: enable every combinable LLM feature (LLMOSA, pre-search "
        "seeding, uncovered-target + stall-detection calls, in-search LLM assertions)",
    )
    llm_group.add_argument(
        "--min-llm",
        dest="llm_mode",
        action="store_const",
        const=LLM_MODE_MIN,
        help="Minimal LLM mode: the paper's cost-optimal deployed config "
        "(stagnation-triggered querying + refinement only; no pre-search seeding). "
        "See docs/evosuite-llm-paper-vs-pynguin.md",
    )
    parser.set_defaults(llm_mode=LLM_MODE_NONE)


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the appropriate subcommand."""
    parser = argparse.ArgumentParser(
        description=_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run eval and optionally save results")
    _add_task_selection(p_run)
    _add_run_options(p_run)
    p_run.add_argument("--save", metavar="FILE", help="Save results as JSON to FILE")
    p_run.add_argument("--output", choices=["table", "json"], default="table")

    p_cmp = sub.add_parser("compare", help="Compare two saved result JSON files")
    p_cmp.add_argument("baseline", help="Baseline results JSON file")
    p_cmp.add_argument("current", help="Current results JSON file")

    p_cb = sub.add_parser(
        "compare-branch", help="Compare current branch against a git ref using worktrees"
    )
    p_cb.add_argument("ref", help="Git ref to compare against (e.g. 'main')")
    _add_task_selection(p_cb)
    _add_run_options(p_cb)
    p_cb.add_argument("--save-baseline", metavar="FILE")
    p_cb.add_argument("--save-current", metavar="FILE")

    args, extra_args = parser.parse_known_args(argv)
    if args.command == "run":
        return cmd_run(args, extra_args)
    if args.command == "compare":
        return cmd_compare(args)
    if args.command == "compare-branch":
        return cmd_compare_branch(args, extra_args)
    return 1
