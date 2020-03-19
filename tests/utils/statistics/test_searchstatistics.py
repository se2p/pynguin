# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.utils.statistics.searchstatistics import SearchStatistics
from pynguin.utils.statistics.statistics import RuntimeVariable
from pynguin.utils.statistics.statisticsbackend import (
    ConsoleStatisticsBackend,
    CSVStatisticsBackend,
    OutputVariable,
)


@pytest.fixture
def search_statistics():
    return SearchStatistics()


@pytest.fixture
def chromosome():
    return tsc.TestSuiteChromosome()


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
    config.INSTANCE.statistics_backend = backend
    statistics = SearchStatistics()
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


def test_get_all_output_variable_names(search_statistics):
    names = search_statistics._get_all_output_variable_names()
    assert "TARGET_CLASS" in names
    assert RuntimeVariable.Coverage.name in names


def test_get_output_variable_names_not_output_variables(search_statistics):
    names = search_statistics._get_output_variable_names()
    assert "TARGET_CLASS" in names
    assert RuntimeVariable.Coverage.name in names


def test_get_output_variable_names_output_variables(search_statistics):
    config.INSTANCE.output_variables = "Size, Length"
    names = search_statistics._get_output_variable_names()
    assert "Size" in names
    assert "Length" in names


def test_write_statistics_no_backend():
    config.INSTANCE.statistics_backend = None
    statistics = SearchStatistics()
    assert not statistics.write_statistics()


def test_write_statistics_no_individual(search_statistics):
    assert not search_statistics.write_statistics()


def test_write_statistics_with_individual(capsys, chromosome):
    config.INSTANCE.statistics_backend = config.StatisticsBackend.CONSOLE
    statistics = SearchStatistics()
    statistics.current_individual(chromosome)
    result = statistics.write_statistics()
    captured = capsys.readouterr()
    assert result
    assert captured.out != ""


def test_get_output_variables(chromosome, search_statistics):
    config.INSTANCE.output_variables = (
        "Coverage,CoverageTimeline,Length,configuration_id"
    )
    config.INSTANCE.budget = 0.25
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.CoverageTimeline, 0.25
    )
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.Coverage, 0.75
    )
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.TARGET_CLASS, "foo"
    )
    variables = search_statistics._get_output_variables(chromosome, skip_missing=True)
    assert variables[RuntimeVariable.Coverage.name].value == 0.75
    assert variables["CoverageTimeline_T1"].value == 0
    assert variables[RuntimeVariable.Length.name].value == 0
    assert variables["configuration_id"].value == ""


def test_current_individual_no_backend(chromosome):
    config.INSTANCE.statistics_backend = None
    statistics = SearchStatistics()
    assert statistics.current_individual(chromosome) is None


def test_current_individual_not_test_suite_chromosome(chromosome_mock):
    statistics = SearchStatistics()
    assert statistics.current_individual(chromosome_mock) is None


def test_current_individual(chromosome, search_statistics):
    search_statistics.current_individual(chromosome)
    assert search_statistics._best_individual == chromosome
