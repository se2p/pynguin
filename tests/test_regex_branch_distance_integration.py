#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test: branches guarded by regular expressions get covered (#347)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import pynguin.configuration as config
import pynguin.generator as gen
from pynguin.generator import ReturnCode, run_pynguin, set_configuration
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_MODULE = "pynguin_regex_sut"

_SUT = """
import re

VERSION_RE = re.compile(r"^\\d+\\.\\d+\\.\\d+$")


def bump(version: str) -> str:
    if VERSION_RE.match(version) is None:
        return "invalid"
    major = int(version.split(".")[0])
    if major >= 1:
        return "stable"
    return "pre-release"


def is_hex_color(text: str) -> bool:
    if re.fullmatch(r"#[0-9a-f]{6}", text):
        return True
    return False
"""


def test_regex_guarded_branches_are_covered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / f"{_MODULE}.py").write_text(_SUT)

    tracked: dict[Any, Any] = {}
    track = gen.stat.track_output_variable

    def _track(variable, value):
        tracked[variable] = value
        track(variable, value)

    monkeypatch.setattr(gen.stat, "track_output_variable", _track)

    conf = config.Configuration(
        algorithm=config.Algorithm.DYNAMOSA,
        project_path=str(project),
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path / "out")),
        module_name=_MODULE,
    )
    conf.stopping.maximum_search_time = 20
    conf.stopping.maximum_coverage = 100
    conf.seeding.seed = 0
    conf.test_case_output.assertion_generation = config.AssertionGenerator.NONE
    set_configuration(conf)
    try:
        assert run_pynguin() == ReturnCode.OK
    finally:
        sys.modules.pop(_MODULE, None)
        if str(project) in sys.path:
            sys.path.remove(str(project))

    assert tracked[RuntimeVariable.PostSearchCoverage] == 1.0
