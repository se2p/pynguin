#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for classes whose constructor is defined by ``__new__``."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pynguin.configuration as config
from pynguin.generator import ReturnCode, run_pynguin, set_configuration

if TYPE_CHECKING:
    from pathlib import Path

_MODULE = "pynguin_new_constructor_sut"

_SOURCE = """
class Box:
    def __new__(cls, size: int):
        obj = super().__new__(cls)
        obj.size = size
        return obj


def use_box(b: Box) -> str:
    if b.size > 3:
        return "large"
    return "tiny"
"""


def test_run_pynguin_constructs_class_via_new(tmp_path: Path) -> None:
    """Pynguin calls ``Box(size=...)`` and never ``Box.__new__`` directly."""
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
        assert "Box(size=" in exported
        assert "__new__" not in exported
    finally:
        sys.modules.pop(_MODULE, None)
        if str(project) in sys.path:
            sys.path.remove(str(project))
