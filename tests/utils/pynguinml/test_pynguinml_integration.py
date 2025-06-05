#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib

from pathlib import Path

import pynguin.configuration as config
import pynguin.generator as gen
import pynguin.testcase.testfactory as tf

from pynguin.analyses import module
from pynguin.configuration import Minimization


def test_pynguinml_integration(tmp_path):
    config.configuration.pynguinml.ml_testing_enabled = True
    importlib.reload(gen)
    importlib.reload(module)
    importlib.reload(tf)

    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    elif project_path.name == "pynguinml":
        project_path /= "../../.."  # pragma: no cover
    project_path = project_path / "docs" / "source" / "_static" / "ml-example"
    dtype_mapping_file = project_path / "dtype_mapping.yaml"

    configuration = config.Configuration(
        algorithm=config.Algorithm.MOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=1),
        module_name="example",
        test_case_output=config.TestCaseOutputConfiguration(
            output_path=str(tmp_path),
            minimization=Minimization(
                test_case_minimization_strategy=config.MinimizationStrategy.NONE
            ),
        ),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path),
            statistics_backend=config.StatisticsBackend.NONE,
        ),
        pynguinml=config.PynguinMLConfiguration(
            ml_testing_enabled=True,
            constraints_path=str(project_path),
            dtype_mapping_path=str(dtype_mapping_file),
            constructor_function="example._tensor_builder",
            constructor_function_parameter="x",
        ),
    )
    gen.set_configuration(configuration)

    result = gen.run_pynguin()

    assert result == gen.ReturnCode.OK
