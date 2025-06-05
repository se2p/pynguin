#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import os
import subprocess  # noqa: S404
import tempfile

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    test_path: Path
    stat_path: Path


def run_pynguin(
    module_name: str,
    project_path: Path,
    tmpdir_path: Path,
    seed: int,
) -> RunResult:
    output_path = tmpdir_path / "output"
    report_path = tmpdir_path / "pynguin-report"

    test_path = output_path / f"test_{module_name}.py"
    stat_path = report_path / "statistics.csv"

    process = subprocess.run(  # noqa: PLW1510, S603
        [  # noqa: S607
            "pynguin",
            "--project-path",
            str(project_path),
            "--module-name",
            module_name,
            "--output_path",
            str(output_path),
            "--seed",
            str(seed),
            "--maximum-iterations",
            "10",
            "--test_case_minimization_strategy",
            "NONE",  # Disable test case minimization because it does not work properly
            "--no-rich",
            "-v",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=tmpdir_path,
        env={
            "PYNGUIN_DANGER_AWARE": "1",
            # disabled to check reproducibility: "PYTHONHASHSEED": str(seed),
            **os.environ,
        },
    )

    return RunResult(
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        test_path=test_path,
        stat_path=stat_path,
    )


def assert_run_result(result: RunResult) -> None:
    assert result.returncode == 0, result.stdout

    assert result.test_path.exists(), result.stdout

    assert result.stat_path.exists(), result.stdout

    assert len(result.stat_path.read_text().splitlines()) == 2, result.stdout


def test_e2e_generation() -> None:
    module_name = "collections"
    project_path = Path("tests/fixtures/examples").resolve()
    seed = 42

    with tempfile.TemporaryDirectory(prefix="pynguin.") as tmpdir:
        tmpdir_path = Path(tmpdir).resolve()

        result = run_pynguin(
            module_name=module_name,
            project_path=project_path,
            tmpdir_path=tmpdir_path,
            seed=seed,
        )

        assert_run_result(result)


def test_repeated_e2e_generation() -> None:
    module_name = "collections"
    project_path = Path("tests/fixtures/examples").resolve()
    seed = 42
    nb_runs = 4

    results: set[tuple[int, str, str]] = set()

    for _ in range(nb_runs):
        with tempfile.TemporaryDirectory(prefix="pynguin.") as tmpdir:
            tmpdir_path = Path(tmpdir).resolve()

            result = run_pynguin(
                module_name=module_name,
                project_path=project_path,
                tmpdir_path=tmpdir_path,
                seed=seed,
            )

            assert_run_result(result)

            results.add((
                result.returncode,
                result.test_path.read_text(),
                result.stat_path.read_text(),
            ))

    assert len(results) == 1, "Expected the same result for all runs with the same seed"
