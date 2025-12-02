#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Integration tests for the string subtype inference."""

from csv import DictReader
from pathlib import Path

import pynguin.configuration as config
import pynguin.generator as gen


def test_string_subtype_integration(tmp_path):
    """Integration test for the string subtype inference."""
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "tests" / "fixtures" / "examples" / "type_tracing"

    configuration = config.Configuration(
        seeding=config.SeedingConfiguration(seed=43),
        algorithm=config.Algorithm.DYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_iterations=1),
        module_name="string_subtype",
        test_case_output=config.TestCaseOutputConfiguration(
            output_path=str(tmp_path),
        ),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path),
            statistics_backend=config.StatisticsBackend.CSV,
        ),
        type_inference=config.TypeInferenceConfiguration(
            type_tracing=True,
            subtype_inference=config.SubtypeInferenceStrategy.STRING,
        ),
    )
    gen.set_configuration(configuration)

    result = gen.run_pynguin()

    assert result == gen.ReturnCode.OK

    csv_file = Path(tmp_path / "statistics.csv")
    assert csv_file.exists()
    parsed_csv = DictReader(csv_file.open())
    for row in parsed_csv:
        assert float(row["Coverage"]) >= 0.8
