#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test: post-assertion coverage must not drop because of the SUT reload."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import pynguin.configuration as config
from pynguin import generator as gen
from pynguin.generator import ReturnCode, run_pynguin, set_configuration
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_MODULE = "pynguin_reload_state_sut"
_FLAG = "_pynguin_reload_state_registered"

# Like a codec registration: the first call in a process takes a different branch,
# and that process-global state survives the reload for the final metrics.
_SUT = f"""import sys


def register() -> bool:
    if getattr(sys, "{_FLAG}", False):
        return False
    setattr(sys, "{_FLAG}", True)
    return True
"""


def test_post_assertion_coverage_unaffected_by_reload_state(
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
    conf.stopping.maximum_search_time = 2
    conf.seeding.seed = 0
    set_configuration(conf)
    try:
        assert run_pynguin() == ReturnCode.OK
    finally:
        sys.modules.pop(_MODULE, None)
        if hasattr(sys, _FLAG):
            delattr(sys, _FLAG)
        if str(project) in sys.path:
            sys.path.remove(str(project))

    assert tracked[RuntimeVariable.PostSearchCoverage] == 1.0
    assert tracked[RuntimeVariable.PostAssertionGenerationCoverage] == 1.0
    assert tracked[RuntimeVariable.PreRefinementCoverage] == 1.0
