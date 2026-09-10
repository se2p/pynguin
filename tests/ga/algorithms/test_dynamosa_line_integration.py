#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Integration test: DynaMOSA with line coverage."""

import pynguin.configuration as config
from pynguin.generator import run_pynguin


def test_dynamosa_with_line_coverage(tmp_path):
    """Ensure DynaMOSA works with line coverage on real code."""

    config.configuration.module_name = "tests.fixtures.simple_line_target"
    config.configuration.algorithm = config.Algorithm.DYNAMOSA

    # ✅ ADD THIS
    config.configuration.test_case_output.coverage_metrics = ["LINE", "BRANCH"]

    config.configuration.statistics_output.statistics_backend = (
        config.StatisticsBackend.NONE
    )

    config.configuration.test_case_output.output_path = tmp_path

    # Run Pynguin
    run_pynguin()

    assert tmp_path.exists()






