#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.computations as ff
import pynguin.ga.postprocess as pp
import pynguin.generator as gen

from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def test_init_with_configuration():
    conf = MagicMock(log_file=None)
    gen.set_configuration(configuration=conf)
    assert config.configuration == conf


def test__load_sut_failed():
    gen.set_configuration(configuration=MagicMock(log_file=None, module_name="this.does.not.exist"))
    assert gen._load_sut(MagicMock()) is False


def test__load_sut_success():
    gen.set_configuration(configuration=MagicMock(log_file=None))
    with mock.patch("importlib.import_module"):
        assert gen._load_sut(MagicMock())


def test_setup_test_cluster_empty():
    gen.set_configuration(
        configuration=MagicMock(
            type_inference=MagicMock(
                type_inference_strategy=config.TypeInferenceStrategy.TYPE_HINTS
            ),
        )
    )
    with mock.patch("pynguin.generator.generate_test_cluster") as gen_mock:
        tc = MagicMock()
        tc.num_accessible_objects_under_test.return_value = 0
        gen_mock.return_value = tc
        assert gen._setup_test_cluster() is None


def test_setup_test_cluster_not_empty():
    gen.set_configuration(
        configuration=MagicMock(
            type_inference=MagicMock(
                type_inference_strategy=config.TypeInferenceStrategy.TYPE_HINTS
            ),
        )
    )
    with mock.patch("pynguin.generator.generate_test_cluster") as gen_mock:
        tc = MagicMock()
        tc.num_accessible_objects_under_test.return_value = 1
        gen_mock.return_value = tc
        assert gen._setup_test_cluster()


def test_setup_path_invalid_dir(tmp_path):
    gen.set_configuration(configuration=MagicMock(log_file=None, project_path=tmp_path / "nope"))
    assert gen._setup_path() is False


def test_setup_path_valid_dir(tmp_path):
    module_name = "test_module"
    gen.set_configuration(
        configuration=MagicMock(log_file=None, project_path=tmp_path, module_name=module_name)
    )
    with mock.patch("sys.path") as path_mock:
        assert gen._setup_path() is True
        path_mock.insert.assert_called_with(0, tmp_path)


def test_setup_hook():
    module_name = "test_module"
    gen.set_configuration(configuration=MagicMock(log_file=None, module_name=module_name))
    with mock.patch.object(gen, "install_import_hook") as hook_mock:
        assert gen._setup_import_hook(None, None)
        hook_mock.assert_called_once()


@pytest.mark.parametrize(
    "optimize,track,existing,added",
    [
        (
            config.CoverageMetric.BRANCH,
            {RuntimeVariable.FinalLineCoverage},
            ff.TestSuiteBranchCoverageFunction,
            [ff.TestSuiteLineCoverageFunction, ff.TestSuiteBranchCoverageFunction],
        ),
        (
            config.CoverageMetric.LINE,
            {RuntimeVariable.FinalBranchCoverage},
            ff.TestSuiteLineCoverageFunction,
            [ff.TestSuiteLineCoverageFunction, ff.TestSuiteBranchCoverageFunction],
        ),
        (
            config.CoverageMetric.LINE,
            {},
            ff.TestSuiteLineCoverageFunction,
            [ff.TestSuiteLineCoverageFunction],
        ),
        (
            config.CoverageMetric.BRANCH,
            {},
            ff.TestSuiteBranchCoverageFunction,
            [ff.TestSuiteBranchCoverageFunction],
        ),
    ],
)
def test__track_one_coverage_while_optimising_for_other(optimize, track, existing, added):
    config.configuration.statistics_output.output_variables = [
        track,
    ]
    algorithm = MagicMock(test_suite_coverage_functions=[existing(MagicMock())])
    to_calculate = []
    gen.add_additional_metrics(
        algorithm=algorithm,
        cov_metrics={optimize},
        executor=MagicMock(),
        metrics_for_reinstrumentation=set(),
        output_variables=track,
        to_calculate=to_calculate,
    )
    assert [type(elem[1]) for elem in to_calculate] == added


def test__reset_cache_for_result():
    test_case = MagicMock()
    result = MagicMock(test_case_chromosomes=[test_case])
    with mock.patch.object(  # noqa: SIM117
        test_case, "invalidate_cache"
    ) as test_case_cache_mock:
        with mock.patch.object(test_case, "remove_last_execution_result") as test_case_result_mock:
            with mock.patch.object(result, "invalidate_cache") as result_cache_mock:
                gen._reset_cache_for_result(result)
                result_cache_mock.assert_called_once()
                test_case_cache_mock.assert_called_once()
                test_case_result_mock.assert_called_once()


def test__minimize_assertions():
    config.configuration.test_case_output.assertion_generation = (
        config.AssertionGenerator.CHECKED_MINIMIZING
    )
    result = MagicMock()
    with mock.patch.object(result, "accept") as result_accept_mock:
        gen._minimize_assertions(result)
        result_accept_mock.assert_called_once()
        assert isinstance(result_accept_mock.call_args.args[0], pp.AssertionMinimization)


def test__setup_report_dir(tmp_path: Path):
    path = tmp_path / "foo" / "bar"
    config.configuration.statistics_output.report_dir = path.absolute()
    config.configuration.statistics_output.create_coverage_report = True
    assert gen._setup_report_dir()
    assert path.exists()
    assert path.is_dir()


def test__setup_report_dir_not_required(tmp_path: Path):
    path = tmp_path / "foo" / "bar"
    config.configuration.statistics_output.report_dir = path.absolute()
    config.configuration.statistics_output.create_coverage_report = False
    config.configuration.statistics_output.statistics_backend = config.StatisticsBackend.NONE
    assert gen._setup_report_dir()
    assert not path.exists()


def test_run(tmp_path):
    gen.set_configuration(configuration=MagicMock(log_file=None, project_path=tmp_path / "nope"))
    with mock.patch("pynguin.generator._run") as run_mock:
        gen.run_pynguin()
        run_mock.assert_called_once()


def test_integrate(tmp_path):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "docs" / "source" / "_static"
    configuration = config.Configuration(
        algorithm=config.Algorithm.MOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=1),
        module_name="example",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
    )
    gen.set_configuration(configuration)
    result = gen.run_pynguin()
    assert result == gen.ReturnCode.OK


def test_integrate_typetracing_union_type(tmp_path):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "tests" / "fixtures" / "type_tracing"
    configuration = config.Configuration(
        algorithm=config.Algorithm.MOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=1),
        module_name="union_type",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
        type_inference=config.TypeInferenceConfiguration(type_tracing=True),
    )
    gen.set_configuration(configuration)
    result = gen.run_pynguin()
    assert result == gen.ReturnCode.OK
