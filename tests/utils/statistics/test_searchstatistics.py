#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testsuitechromosome as tsc
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
    chrom = tsc.TestSuiteChromosome()
    fitness_func = MagicMock(ff.FitnessFunction)
    fitness_func.is_maximisation_function.return_value = False
    chrom.add_fitness_function(fitness_func)
    chrom.update_fitness_values(fitness_func, ff.FitnessValues(0, 0))
    chrom.set_changed(False)
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
    config.INSTANCE.output_variables = [
        RuntimeVariable.Coverage,
        RuntimeVariable.CoverageTimeline,
        RuntimeVariable.Length,
        RuntimeVariable.ConfigurationId,
    ]
    config.INSTANCE.budget = 0.25
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.CoverageTimeline, 0.25
    )
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.Coverage, 0.75
    )
    search_statistics.set_output_variable_for_runtime_variable(
        RuntimeVariable.TargetModule, "foo"
    )
    variables = search_statistics._get_output_variables(chromosome, skip_missing=True)
    assert variables[RuntimeVariable.Coverage.name].value == 0.75
    assert variables[RuntimeVariable.Length.name].value == 0
    assert variables["ConfigurationId"].value == ""


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
