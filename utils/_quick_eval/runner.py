# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Invoke Pynguin on modules and collect their results."""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess  # noqa: S404
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from . import DEFAULT_TIMEOUT_S, console
from .report import fmt_pct
from .stats import ModuleResult, parse_statistics_csv

if TYPE_CHECKING:
    from .tasks import ModuleTask

# Wall-clock cap for running one generated suite under coverage.py. Generated tests
# should execute in seconds, so keep this tight: a hung/slow generated test must not
# balloon a run far past its search budget (it is reported as "suite timeout" instead).
_SUITE_TIMEOUT_S = 120


def _build_output_vars(*, include_mutation: bool, include_llm: bool) -> str:
    """Assemble the ``--output-variables`` list for the requested metrics."""
    parts = ["TargetModule", "BranchCoverage"]
    if include_mutation:
        parts += ["MutationScore", "NumberOfKilledMutants", "NumberOfCreatedMutants"]
    if include_llm:
        parts += [
            "TotalLLMCalls",
            "TotalLLMInputTokens",
            "TotalLLMOutputTokens",
            "LLMQueryTime",
            "LLMTotalParsedStatements",
        ]
    return ",".join(parts)


# LLM evaluation modes selected by the CLI (see cli.py).
LLM_MODE_NONE = "none"  # no LLM features (pure SBST)
LLM_MODE_FULL = "full"  # every combinable LLM feature
LLM_MODE_MIN = "min"  # the paper's cost-optimal stagnation-only config


def _llm_credential_args() -> list[str]:
    """Return the ``--api-key`` / ``--llm-url`` / ``--model-name`` flags from the env.

    API credentials are resolved from the environment (populated from the
    pynguin-experiments ``.env`` by the entry point) and passed explicitly so a
    malformed host environment variable cannot silently break the run.
    """
    args: list[str] = []
    api_key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("PYNGUIN_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    llm_url = os.environ.get("LLM_BASE_URL") or os.environ.get("PYNGUIN_LLM_BASE_URL")
    model_name = os.environ.get("LLM_MODEL") or os.environ.get("PYNGUIN_LLM_MODEL")
    if api_key:
        args += ["--api-key", api_key.strip()]
    if llm_url:
        args += ["--llm-url", llm_url.strip()]
    if model_name:
        args += ["--model-name", model_name.strip()]
    return args


def _llm_cli_args(mode: str) -> list[str]:
    """Return the Pynguin CLI flags that configure LLM test generation for ``mode``.

    ``full`` enables every combinable LLM feature: the LLMOSA algorithm, pre-search
    initial-population seeding, the pre-search uncovered-targets call, stagnation-
    triggered querying, and in-search LLM assertion generation.

    ``min`` mirrors the paper's cost-optimal *deployed* configuration
    (docs/evosuite-llm-paper-vs-pynguin.md): stagnation-triggered querying **only**,
    plus the post-processing refinement pipeline (readability + semantic assertions +
    repair). Pre-search seeding and the pre-search uncovered-targets call stay OFF, since
    the paper finds the cost-coverage optimum is stagnation-triggered injection alone.

    Both modes keep Pynguin's already paper-calibrated timing/repair/context defaults
    (30 s stagnation window, 45 s late-budget guard, 2 repair iterations, 1 intervention,
    64 000-char context, 30 s request timeout) and enable response caching.
    """
    if mode == LLM_MODE_MIN:
        args = [
            "--algorithm",
            "LLMOSA",
            "--large-language-model.enable-response-caching",
            "True",
            "--large-language-model.call-llm-on-stall-detection",
            "True",
            "--llm-refinement.enabled",
            "True",
        ]
    else:  # LLM_MODE_FULL
        args = [
            "--algorithm",
            "LLMOSA",
            "--large-language-model.enable-response-caching",
            "True",
            "--large-language-model.call-llm-for-uncovered-targets",
            "True",
            "--large-language-model.call-llm-on-stall-detection",
            "True",
            "--large-language-model.hybrid-initial-population",
            "True",
            "--assertion-generation",
            "LLM",
        ]
    return args + _llm_credential_args()


def _search_int(pattern: str, text: str) -> int | None:
    """Return the first integer captured by ``pattern`` in ``text``, or None."""
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _parse_pytest_counts(stdout: str) -> tuple[int | None, int | None]:
    """Return (passed, failed+errored) parsed from pytest's summary line, best-effort."""
    passed = _search_int(r"(\d+) passed", stdout)
    failed = _search_int(r"(\d+) failed", stdout) or 0
    errored = _search_int(r"(\d+) error", stdout) or 0
    total_bad = failed + errored
    return passed, (total_bad or None)


def ensure_runner_tools(python_exe: str) -> None:
    """Ensure pytest and coverage are installed in the runner environment."""
    try:
        subprocess.run(  # noqa: S603
            [python_exe, "-m", "pip", "install", "-q", "coverage", "pytest"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as err:
        console.print(
            "[yellow]Warning: could not install coverage/pytest into runner env:[/yellow] "
            f"{err.stderr.decode()[-300:]}"
        )


def _measure_generated_suite(
    python_exe: str, output_dir: str, module: str, timeout: int
) -> tuple[float | None, int | None, str | None]:
    """Run the exported test suite under coverage.py and return (coverage, tests, error).

    ``coverage`` is coverage.py's combined line+branch fraction (0..1) restricted to
    ``module``; ``tests`` is the number of passing tests; ``error`` is a short note when
    the suite could not be measured or had failing tests. This is the independent,
    execution-based measurement (does the *exported* suite really cover the module?).
    """
    out = Path(output_dir)
    if not list(out.glob("test_*.py")):
        return None, None, "no generated tests"
    data_file = out / ".coverage"
    json_file = out / "coverage.json"
    try:
        proc = subprocess.run(  # noqa: S603
            [
                python_exe,
                "-m",
                "coverage",
                "run",
                "--branch",
                f"--source={module}",
                "--data-file",
                str(data_file),
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                str(out),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(out),
        )
    except subprocess.TimeoutExpired:
        return None, None, f"suite timeout after {timeout}s"
    except OSError as exc:
        return None, None, f"suite run error: {exc}"
    if proc.returncode == 5:  # pytest exit code 5: no tests collected
        return None, 0, "no tests collected"
    passed, failed = _parse_pytest_counts(proc.stdout)
    try:
        subprocess.run(  # noqa: S603
            [
                python_exe,
                "-m",
                "coverage",
                "json",
                "--data-file",
                str(data_file),
                "-o",
                str(json_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
            cwd=str(out),
        )
        totals = json.loads(json_file.read_text(encoding="utf-8"))["totals"]
        coverage = float(totals["percent_covered"]) / 100.0
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
        return None, passed, f"coverage parse error: {exc}"
    return coverage, passed, (f"{failed} failed" if failed else None)


def _as_int(v: float | None) -> int | None:
    return int(v) if v is not None else None


def _as_float(v: float | None) -> float | None:
    return float(v) if v is not None else None


def _result_from_stats(
    task: ModuleTask,
    stats: dict[str, float | int | None],
    duration: float,
    exit_code: int,
    error: str | None,
    *,
    suite: tuple[float | None, int | None, str | None],
) -> ModuleResult:
    """Build a :class:`ModuleResult` from a parsed statistics dictionary and suite result."""
    suite_coverage, suite_tests, suite_error = suite
    return ModuleResult(
        project=task.project,
        module=task.module,
        branch_coverage=_as_float(stats["branch_coverage"]),
        line_coverage=_as_float(stats["line_coverage"]),
        duration_s=duration,
        exit_code=exit_code,
        error=error,
        mutation_score=_as_float(stats["mutation_score"]),
        mutation_killed=_as_int(stats["mutation_killed"]),
        mutation_total=_as_int(stats["mutation_total"]),
        llm_calls=_as_int(stats["llm_calls"]),
        llm_input_tokens=_as_int(stats["llm_input_tokens"]),
        llm_output_tokens=_as_int(stats["llm_output_tokens"]),
        llm_query_time_s=_as_float(stats["llm_query_time_s"]),
        llm_parsed_stmts=_as_int(stats["llm_parsed_stmts"]),
        suite_coverage=suite_coverage,
        suite_tests=suite_tests,
        suite_error=suite_error,
    )


def run_module(
    task: ModuleTask,
    budget: int,
    seed: int,
    python_exe: str,
    *,
    include_mutation: bool = False,
    llm_mode: str = LLM_MODE_NONE,
    timeout: int = DEFAULT_TIMEOUT_S,
    extra_args: list[str] | None = None,
) -> ModuleResult:
    """Run Pynguin on one module and return its coverage (and optional mutation/LLM) result.

    The timeout is a wall-clock limit for the whole run, not just the search phase;
    see DEFAULT_TIMEOUT_S.
    """
    include_llm = llm_mode != LLM_MODE_NONE
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
            _build_output_vars(include_mutation=include_mutation, include_llm=include_llm),
        ]
        if include_llm:
            cmd += _llm_cli_args(llm_mode)
        if extra_args:
            cmd += extra_args

        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            exit_code = proc.returncode
            # Pynguin writes tracebacks to stdout, not stderr, so a crash (e.g. a
            # missing optional dependency) leaves stderr empty. Fall back to the tail
            # of stdout so the failure reason is not silently lost as "no generated tests".
            if proc.returncode != 0:
                error = (proc.stderr or proc.stdout or "")[-500:] or None
            else:
                error = None
        except subprocess.TimeoutExpired:
            exit_code = -1
            error = f"timeout after {timeout}s"
        duration = time.monotonic() - start
        stats = parse_statistics_csv(tmpdir)
        suite = _measure_generated_suite(
            python_exe, tmpdir, task.module, timeout=min(timeout, _SUITE_TIMEOUT_S)
        )
    return _result_from_stats(task, stats, duration, exit_code, error, suite=suite)


def ensure_llm_available(python_exe: str) -> None:
    """Fail fast if an LLM mode is requested but the ``openai`` extra is not installed.

    LLMOSA imports the ``openai`` client at algorithm-instantiation time and raises
    ``ValueError`` if it is missing, which surfaces only as a per-module exit-2 crash
    with no tests. Checking once up front avoids launching a fleet of runs that all
    fail the same way.
    """
    proc = subprocess.run(  # noqa: S603
        [python_exe, "-c", "import openai"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "LLM mode requested but the 'openai' extra is not installed in the runner "
            f"environment ({python_exe}). Install it with: poetry install --extras openai"
        )


def install_sut_dependencies(tasks: list[ModuleTask], python_exe: str) -> None:
    """Install dependencies of SUT projects into the python_exe environment."""
    installed_projects: set[str] = set()
    for task in tasks:
        if task.project in installed_projects:
            continue
        project_dir = Path(task.project_path)
        if not project_dir.exists():
            continue

        has_config = (
            (project_dir / "pyproject.toml").exists()
            or (project_dir / "setup.py").exists()
            or (project_dir / "requirements.txt").exists()
        )
        if has_config:
            console.print(f"Installing SUT dependencies for project '{task.project}' ...")
            try:
                if (project_dir / "pyproject.toml").exists() or (project_dir / "setup.py").exists():
                    subprocess.run(  # noqa: S603
                        [python_exe, "-m", "pip", "install", "-e", str(project_dir)],
                        check=True,
                        capture_output=True,
                    )
                elif (project_dir / "requirements.txt").exists():
                    req_path = str(project_dir / "requirements.txt")
                    subprocess.run(  # noqa: S603
                        [python_exe, "-m", "pip", "install", "-r", req_path],
                        check=True,
                        capture_output=True,
                    )
                console.print(
                    f"  Successfully installed SUT dependencies for project '{task.project}'"
                )
            except subprocess.CalledProcessError as err:
                msg = (
                    f"[bold red]Warning: Failed to install SUT dependencies for "
                    f"'{task.project}':[/bold red]\n{err.stderr.decode()}"
                )
                console.print(msg)
            installed_projects.add(task.project)


def _print_progress(result: ModuleResult) -> None:
    """Print a one-line progress summary for a completed run."""
    mut_info = (
        f" mut={fmt_pct(result.mutation_score)} ({result.mutation_killed}/{result.mutation_total})"
        if result.mutation_score is not None
        else ""
    )
    llm_info = f" llm_calls={result.llm_calls}" if result.llm_calls is not None else ""
    if result.suite_coverage is not None:
        suite_info = f" suite={fmt_pct(result.suite_coverage)}"
    elif result.suite_error:
        suite_info = f" suite=({result.suite_error})"
    else:
        suite_info = ""
    console.print(
        f"  [{result.project}] {result.module}: "
        f"branch={fmt_pct(result.branch_coverage)} "
        f"line={fmt_pct(result.line_coverage)}"
        f"{suite_info}{mut_info}{llm_info} "
        f"({result.duration_s:.0f}s, exit={result.exit_code})"
    )


def run_eval(
    tasks: list[ModuleTask],
    budget: int,
    seed: int,
    jobs: int,
    *,
    python_exe: str = sys.executable,
    include_mutation: bool = False,
    llm_mode: str = LLM_MODE_NONE,
    timeout: int = DEFAULT_TIMEOUT_S,
    extra_args: list[str] | None = None,
) -> list[ModuleResult]:
    """Run Pynguin on all tasks in parallel and return results."""
    if llm_mode != LLM_MODE_NONE:
        ensure_llm_available(python_exe)
    install_sut_dependencies(tasks, python_exe)
    ensure_runner_tools(python_exe)
    results: list[ModuleResult] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                run_module,
                task,
                budget,
                seed,
                python_exe,
                include_mutation=include_mutation,
                llm_mode=llm_mode,
                timeout=timeout,
                extra_args=extra_args,
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
            _print_progress(result)
    return results
