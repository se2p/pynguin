#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import json

from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.computations as ff
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat

from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.statistics.statisticsbackend import ConsoleStatisticsBackend
from pynguin.utils.statistics.statisticsbackend import CSVStatisticsBackend
from pynguin.utils.statistics.statisticsbackend import OutputVariable


@pytest.fixture
def search_statistics():
    return stat._SearchStatistics()


@pytest.fixture
def chromosome():
    chrom = tsc.TestSuiteChromosome()
    fitness_func = MagicMock(ff.FitnessFunction)
    fitness_func.is_maximisation_function.return_value = False
    chrom.add_fitness_function(fitness_func)
    chrom.computation_cache._fitness_cache[fitness_func] = 0
    coverage_func = MagicMock()
    chrom.add_coverage_function(coverage_func)
    chrom.computation_cache._coverage_cache[coverage_func] = 0
    chrom.changed = False
    return chrom


@pytest.fixture
def chromosome_mock():
    return MagicMock(chrom.Chromosome)


@pytest.mark.parametrize(
    "backend, type_",
    [
        pytest.param(config.StatisticsBackend.NONE, type(None)),
        pytest.param(config.StatisticsBackend.CONSOLE, ConsoleStatisticsBackend),
        pytest.param(config.StatisticsBackend.CSV, CSVStatisticsBackend),
    ],
)
def test_initialise_backend(backend, type_):
    config.configuration.statistics_output.statistics_backend = backend
    statistics = stat._SearchStatistics()
    assert isinstance(statistics._backend, type_)


def test_output_variable(search_statistics):
    sequence_output_variable = OutputVariable(
        name=RuntimeVariable.TotalExceptionsTimeline.name, value=42
    )
    output_variable = OutputVariable(name=RuntimeVariable.Length.name, value=42)
    search_statistics.set_output_variable(sequence_output_variable)
    search_statistics.set_output_variable(output_variable)
    variables = search_statistics.output_variables
    assert len(variables) == 2


def test_write_statistics_no_backend():
    config.configuration.statistics_output.statistics_backend = None
    statistics = stat._SearchStatistics()
    assert not statistics.write_statistics()


def test_write_statistics_no_individual(search_statistics):
    assert not search_statistics.write_statistics()


def test_write_statistics_with_individual(capsys, chromosome):
    config.configuration.statistics_output.statistics_backend = config.StatisticsBackend.CONSOLE
    statistics = stat._SearchStatistics()
    statistics.current_individual(chromosome)
    result = statistics.write_statistics()
    captured = capsys.readouterr()
    assert result
    assert captured.out != ""  # noqa: PLC1901


@pytest.fixture(scope="session")
def function_json():
    return json.dumps([
        {
            "col_offset": 9,
            "file": "test.py",
            "function": "foo",
            "line_number": 2,
            "parameter": "a",
            "type": ["int"],
        },
        {
            "col_offset": 17,
            "file": "test.py",
            "function": "foo",
            "line_number": 2,
            "parameter": "b",
            "type": ["complex", "float"],
        },
        {
            "col_offset": 5,
            "file": "test.py",
            "function": "foo",
            "line_number": 2,
            "type": ["str"],
        },
    ])


def test_write_statistics_with_type_eval_export(chromosome, function_json, tmp_path):
    config.configuration.statistics_output.statistics_backend = config.StatisticsBackend.CSV
    config.configuration.statistics_output.output_variables = [RuntimeVariable.SignatureInfos]
    config.configuration.statistics_output.report_dir = tmp_path
    output_file = tmp_path / "signature-infos.json"

    statistics = stat._SearchStatistics()
    statistics.current_individual(chromosome)
    statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.SignatureInfos, function_json
    )
    result = statistics.write_statistics()

    assert output_file.exists()
    assert output_file.read_text() == function_json
    assert result


def test_write_statistics_with_type_eval_export_invalid(chromosome, tmp_path):
    config.configuration.statistics_output.statistics_backend = config.StatisticsBackend.CSV
    config.configuration.statistics_output.output_variables = [RuntimeVariable.SignatureInfos]
    config.configuration.statistics_output.report_dir = tmp_path
    output_file = tmp_path / "signature-infos.json"

    statistics = stat._SearchStatistics()
    statistics.current_individual(chromosome)
    statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.SignatureInfos, "invalid_json"
    )
    result = statistics.write_statistics()

    assert not output_file.exists()
    assert result


@pytest.mark.xfail(raises=IndexError, reason="AUC computation interferes")
def test_get_output_variables(chromosome, search_statistics):
    config.configuration.statistics_output.output_variables = [
        RuntimeVariable.Coverage,
        RuntimeVariable.CoverageTimeline,
        RuntimeVariable.Length,
        RuntimeVariable.ConfigurationId,
        RuntimeVariable.ProjectName,
    ]
    config.configuration.stopping.maximum_search_time = 0.25
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.CoverageTimeline, 0.25
    )
    search_statistics.set_output_variable_for_runtime_variable(RuntimeVariable.Coverage, 0.75)
    search_statistics.set_output_variable_for_runtime_variable(RuntimeVariable.TargetModule, "foo")
    variables = search_statistics._get_output_variables(chromosome, skip_missing=True)
    assert variables[RuntimeVariable.Coverage.name].value == 0.75
    assert variables[RuntimeVariable.Length.name].value == 0
    assert not variables["ConfigurationId"].value
    assert not variables["ProjectName"].value


def test_current_individual_no_backend(chromosome):
    config.configuration.statistics_output.statistics_backend = None
    statistics = stat._SearchStatistics()
    assert statistics.current_individual(chromosome) is None


def test_current_individual_not_test_suite_chromosome(chromosome_mock):
    statistics = stat._SearchStatistics()
    assert statistics.current_individual(chromosome_mock) is None


def test_current_individual(chromosome, search_statistics):
    search_statistics.current_individual(chromosome)
    assert search_statistics._best_individual == chromosome
