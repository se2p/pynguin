#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for a SUT whose package is already imported from elsewhere."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import pynguin.configuration as config
from pynguin.generator import ReturnCode, run_pynguin, set_configuration

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_PACKAGE = "pynguin_shadowed_sut"


def _write_package(root: Path, function_name: str) -> None:
    package = root / _PACKAGE
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "sut.py").write_text(f"def {function_name}(x: int) -> int:\n    return x + 1\n")


def test_run_pynguin_tests_project_copy_of_preloaded_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy of the SUT package imported before the run must not replace the project's."""
    project = tmp_path / "project"
    vendored = tmp_path / "vendored"
    _write_package(project, "project_function")
    _write_package(vendored, "vendored_function")
    monkeypatch.syspath_prepend(str(vendored))
    importlib.import_module(f"{_PACKAGE}.sut")

    output = tmp_path / "out"
    conf = config.Configuration(
        algorithm=config.Algorithm.RANDOM,
        project_path=str(project),
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(output)),
        module_name=f"{_PACKAGE}.sut",
    )
    conf.stopping.maximum_search_time = 2
    conf.test_case_output.assertion_generation = config.AssertionGenerator.NONE
    set_configuration(conf)
    try:
        assert run_pynguin() == ReturnCode.OK
        assert sys.modules[f"{_PACKAGE}.sut"].__file__ == str(project / _PACKAGE / "sut.py")
        exported = (output / "test_sut.py").read_text()
        assert "project_function" in exported
        assert "vendored_function" not in exported
    finally:
        for module in [m for m in sys.modules if m.partition(".")[0] == _PACKAGE]:
            del sys.modules[module]
        if str(project) in sys.path:
            sys.path.remove(str(project))
