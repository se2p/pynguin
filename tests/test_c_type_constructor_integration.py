#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for classes whose constructor is implemented in C."""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

import pynguin.configuration as config
from pynguin.generator import ReturnCode, run_pynguin, set_configuration

if TYPE_CHECKING:
    from pathlib import Path

_MODULE = "pynguin_c_type_constructor_sut"

_SOURCE = """
import datetime


def use_date(d: datetime.date) -> str:
    if d.month == 2:
        return "feb"
    return "other"
"""


def test_run_pynguin_constructs_c_type_via_imported_module(tmp_path: Path) -> None:
    """Pynguin calls ``module_.datetime.date(year=..., ...)`` and passes the date."""
    project = tmp_path / "project"
    project.mkdir()
    (project / f"{_MODULE}.py").write_text(_SOURCE)
    output = tmp_path / "out"
    conf = config.Configuration(
        algorithm=config.Algorithm.DYNAMOSA,
        project_path=str(project),
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(output)),
        module_name=_MODULE,
        seeding=config.SeedingConfiguration(seed=1),
    )
    conf.stopping.maximum_search_time = 5
    conf.test_case_output.assertion_generation = config.AssertionGenerator.NONE
    set_configuration(conf)
    try:
        assert run_pynguin() == ReturnCode.OK
        exported = (output / f"test_{_MODULE}.py").read_text()
        # A date or a datetime, which is a subclass of date.
        assert re.search(rf"{_MODULE}_\.datetime\.date(time)?\(\s*year=", exported)
        assert "use_date(d=var_" in exported
    finally:
        sys.modules.pop(_MODULE, None)
        if str(project) in sys.path:
            sys.path.remove(str(project))
