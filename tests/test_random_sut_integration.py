#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for SUT importing functions from random module."""

from __future__ import annotations

import os
import subprocess  # noqa: S404
import sys
from typing import TYPE_CHECKING

import pynguin.configuration as config
from pynguin.generator import ReturnCode, run_pynguin, set_configuration

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = "pynguin_random_sut"

_SUT_CODE = """\
from __future__ import annotations

from random import choice, random


def jitter(x: float) -> float:
    if random() < 0.5:
        return x + 1.0
    return x - 1.0


def pick(items: list[int]) -> int:
    if not items:
        raise ValueError("empty")
    return choice(items)
"""


def _write_package(root: Path) -> None:
    package = root / _PACKAGE
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "rmod.py").write_text(_SUT_CODE, encoding="utf-8")


def test_random_sut_exports_seeding_fixture_and_tests_pass(tmp_path: Path) -> None:
    """A SUT using 'from random import random, choice' must produce a seeded, passing test suite."""
    project = tmp_path / "project"
    output = tmp_path / "out"
    _write_package(project)

    conf = config.Configuration(
        algorithm=config.Algorithm.RANDOM,
        project_path=str(project),
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(output)),
        module_name=f"{_PACKAGE}.rmod",
    )
    conf.stopping.maximum_search_time = 3
    conf.seeding.seed = 42
    set_configuration(conf)

    try:
        assert run_pynguin() == ReturnCode.OK
        test_file = output / "test_rmod.py"
        assert test_file.exists()

        content = test_file.read_text(encoding="utf-8")
        assert "import random as _pynguin_random" in content
        assert "_pynguin_seed_random" in content
        assert "_pynguin_random.seed(42)" in content

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{project}:{env.get('PYTHONPATH', '')}"
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pytest", "-q", str(test_file)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"pytest failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    finally:
        for module in [m for m in list(sys.modules) if m.partition(".")[0] == _PACKAGE]:
            del sys.modules[module]
        if str(project) in sys.path:
            sys.path.remove(str(project))
