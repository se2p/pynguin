# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Tests that quick_eval measures the exported suite against the ``--project-path`` copy.

The quick_eval harness lives in ``utils/_quick_eval`` (outside ``src``); make it
importable the same way the ``utils/quick_eval.py`` entry point does.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_UTILS_DIR = Path(__file__).resolve().parents[2] / "utils"
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

from _quick_eval.runner import (  # noqa: E402
    _measure_generated_suite,  # noqa: PLC2701
    _outside_project,  # noqa: PLC2701
    _suite_env,  # noqa: PLC2701
)

_MODULE = "qe_shadowed_subject"

# The project copy is fully covered by the suite below.
_PROJECT_COPY = """\
def double(x):
    return 2 * x
"""

# The shadowing copy (standing in for an older version in the venv) has an extra,
# never-called function, so measuring it yields less than 100%.
_SHADOW_COPY = """\
def double(x):
    return 2 * x


def unused(x):
    if x:
        return 1
    return 0
"""

_SUITE = f"""\
import {_MODULE}


def test_double():
    assert {_MODULE}.double(2) == 4
"""


@pytest.fixture
def layout(tmp_path, monkeypatch):
    project = tmp_path / "project"
    shadow = tmp_path / "shadow"
    out = tmp_path / "out"
    for directory in (project, shadow, out):
        directory.mkdir()
    (shadow / f"{_MODULE}.py").write_text(_SHADOW_COPY, encoding="utf-8")
    (out / f"test_{_MODULE}.py").write_text(_SUITE, encoding="utf-8")
    # Make the shadowing copy importable for the suite subprocess, like a copy that
    # is installed in the runner venv.
    monkeypatch.setenv("PYTHONPATH", str(shadow))
    return project, shadow, out


def test_suite_measures_project_copy_not_shadowing_copy(layout):
    project, _, out = layout
    (project / f"{_MODULE}.py").write_text(_PROJECT_COPY, encoding="utf-8")

    coverage, tests, error = _measure_generated_suite(
        sys.executable, str(out), _MODULE, timeout=120, project_path=str(project)
    )

    assert error is None
    assert tests == 1
    assert coverage == pytest.approx(1.0)


def test_suite_reports_error_when_measuring_copy_outside_project(layout):
    project, shadow, out = layout  # the module exists only in the shadowing location

    coverage, tests, error = _measure_generated_suite(
        sys.executable, str(out), _MODULE, timeout=120, project_path=str(project)
    )

    assert coverage is None
    assert tests == 1
    assert error is not None
    assert "outside project path" in error
    assert str(shadow.resolve()) in error


def test_suite_import_failure_surfaces_pytest_output(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    project = tmp_path / "project"
    out = tmp_path / "out"
    project.mkdir()
    out.mkdir()
    (out / f"test_{_MODULE}.py").write_text(_SUITE, encoding="utf-8")

    coverage, _, error = _measure_generated_suite(
        sys.executable, str(out), _MODULE, timeout=120, project_path=str(project)
    )

    assert coverage is None
    assert error is not None
    assert error.startswith("coverage parse error")
    assert "error" in error.split("pytest:", 1)[1]


def test_suite_env_prepends_resolved_project_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "proj").mkdir()
    monkeypatch.setenv("PYTHONPATH", "existing")

    env = _suite_env("proj")

    assert env["PYTHONPATH"] == str((tmp_path / "proj").resolve()) + os.pathsep + "existing"


def test_suite_env_without_existing_pythonpath(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    env = _suite_env(str(tmp_path))

    assert env["PYTHONPATH"] == str(tmp_path.resolve())


def test_outside_project_filters_files_under_root(tmp_path):
    inside = tmp_path / "proj" / "m.py"
    outside = tmp_path / "site-packages" / "m.py"

    assert _outside_project([inside, outside], str(tmp_path / "proj")) == [outside]
