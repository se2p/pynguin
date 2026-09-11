#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for fine-grained line targeting."""

from __future__ import annotations

import pathlib

import pynguin.configuration as config
import pynguin.generator as gen
from tests.utils.utils import assert_generated_test_covers_lines


def test_integrate_fine_grained_line_targeting(tmp_path: pathlib.Path) -> None:
    """Integration test for targeting specific line ranges in Pynguin."""
    project_path = pathlib.Path().absolute()
    configuration = config.Configuration(
        algorithm=config.Algorithm.DYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_iterations=500),
        module_name="tests.fixtures.examples.difficult",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
        to_cover=config.ToCoverConfiguration(only_cover_line_ranges=["12"]),
    )
    gen.set_configuration(configuration)
    result = gen.run_pynguin()
    assert result == gen.ReturnCode.OK

    target_file = project_path / "tests" / "fixtures" / "examples" / "difficult.py"
    assert_generated_test_covers_lines(
        output_dir=tmp_path,
        target_file_path=target_file,
        target_lines={12},
        expected_symbol="difficult_branches",
    )
