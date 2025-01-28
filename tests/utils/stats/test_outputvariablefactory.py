#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import time

import pytest

import pynguin.configuration as config
import pynguin.ga.testsuitechromosome as tsc

from pynguin.utils.statistics.outputvariablefactory import (
    ChromosomeOutputVariableFactory,
)
from pynguin.utils.statistics.outputvariablefactory import (
    DirectSequenceOutputVariableFactory,
)
from pynguin.utils.statistics.outputvariablefactory import SequenceOutputVariableFactory
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


class _DummyChromosomeOutputVariableFactory(ChromosomeOutputVariableFactory):
    def get_data(self, individual: tsc.TestSuiteChromosome) -> int:
        return 42


class _DummySequenceOutputVariableFactory(SequenceOutputVariableFactory):
    def get_value(self, individual: tsc.TestSuiteChromosome) -> int:
        return 42


@pytest.fixture
def factory():
    return DirectSequenceOutputVariableFactory(RuntimeVariable.TotalExceptionsTimeline, 0)


@pytest.fixture
def chromosome_factory():
    return _DummyChromosomeOutputVariableFactory(RuntimeVariable.Coverage)


@pytest.fixture
def sequence_factory():
    return _DummySequenceOutputVariableFactory(RuntimeVariable.CoverageTimeline)


@pytest.fixture
def chromosome():
    return tsc.TestSuiteChromosome()


def test_get_value(factory, chromosome):
    factory.set_value(42)
    assert factory.get_value(chromosome) == 42


def test_get_float(chromosome):
    factory = DirectSequenceOutputVariableFactory.get_float(RuntimeVariable.Coverage)
    assert isinstance(factory.get_value(chromosome), float)
    assert factory.get_value(chromosome) == 0.0


def test_get_integer(chromosome):
    factory = DirectSequenceOutputVariableFactory.get_integer(RuntimeVariable.Length)
    assert isinstance(factory.get_value(chromosome), int)
    assert factory.get_value(chromosome) == 0


def test_get_output_variables(factory):
    config.configuration.stopping.maximum_search_time = 0
    result = factory.get_output_variables()
    assert result == []


def test_chromosome_factory_get_variable(chromosome_factory, chromosome):
    variable = chromosome_factory.get_variable(chromosome)
    assert variable.name == RuntimeVariable.Coverage.name
    assert variable.value == 42


def test_sequence_factory_update(sequence_factory, chromosome):
    sequence_factory.set_start_time(time.time_ns())
    sequence_factory.update(chromosome)
    assert sequence_factory._time_stamps[0] >= 0
    assert sequence_factory._values[0] == 42


def test_get_output_variables_with_content(sequence_factory, chromosome):
    def check_result(name: str, value: int, index: int):
        assert name == f"CoverageTimeline_T{index}"  # pragma: no cover
        assert value == 42  # pragma: no cover

    config.configuration.stopping.maximum_search_time = 0.25
    chromosome_2 = tsc.TestSuiteChromosome()
    sequence_factory.set_start_time(time.time_ns())
    time.sleep(0.05)
    sequence_factory.update(chromosome)
    time.sleep(0.05)
    sequence_factory.update(chromosome_2)
    time.sleep(0.05)
    variables = sequence_factory.get_output_variables()
    [check_result(var.name, var.value, index + 1) for index, var in enumerate(variables)]
    assert len(variables) >= 0


def test_get_time_line_value_without_timestamps(sequence_factory):
    assert sequence_factory._get_time_line_value("foo") == 0


def test_get_time_line_value_first(sequence_factory):
    start_time = time.time_ns()
    sequence_factory._time_stamps = [start_time + i for i in range(3)]
    sequence_factory._values = [f"val_{i}" for i in range(3)]
    assert sequence_factory._get_time_line_value(0) == "val_0"


def test_get_time_line_value_last(sequence_factory):
    start_time = time.time_ns()
    sequence_factory._time_stamps = [start_time + i for i in range(3)]
    sequence_factory._values = [f"val_{i}" for i in range(3)]
    assert sequence_factory._get_time_line_value(start_time * 2) == "val_2"


def test_get_time_line_value_interpolation(sequence_factory):
    config.configuration.statistics_output.timeline_interval = 1
    start_time = time.time_ns()
    sequence_factory.set_start_time(start_time)
    sequence_factory._time_stamps = [start_time + i for i in range(3)]
    sequence_factory._values = list(range(3))
    assert sequence_factory._get_time_line_value(start_time + 1) == 1.0


def test_get_time_line_value_no_interpolation(sequence_factory):
    config.configuration.statistics_output.timeline_interval = 1
    config.configuration.statistics_output.timeline_interpolation = False
    start_time = time.time_ns()
    sequence_factory.set_start_time(start_time)
    sequence_factory._time_stamps = [start_time + i for i in range(3)]
    sequence_factory._values = list(range(3))
    assert sequence_factory._get_time_line_value(start_time + 1) == 0


@pytest.mark.parametrize(
    "values, result",
    [
        pytest.param([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0.0),
        pytest.param([0.0, 1 / 2, 2 / 3, 3 / 4, 4 / 5, 1.0], 193 / 60),
        pytest.param([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], 5.0),
    ],
)
def test_area_under_curve(sequence_factory, values, result):
    config.configuration.stopping.maximum_search_time = 5
    start_time = time.time_ns()
    sequence_factory.set_start_time(start_time)
    sequence_factory._time_stamps = [i * 1_000_000_000 for i in range(6)]
    sequence_factory._values = values
    assert sequence_factory.area_under_curve == pytest.approx(result)


@pytest.mark.parametrize(
    "values, result",
    [
        pytest.param([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0.0),
        pytest.param([0.0, 1 / 2, 2 / 3, 3 / 4, 4 / 5, 1.0], 193 / 300),
        pytest.param([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], 1.0),
    ],
)
def test_normalised_area_under_curve(sequence_factory, values, result):
    config.configuration.stopping.maximum_search_time = 5
    start_time = time.time_ns()
    sequence_factory.set_start_time(start_time)
    sequence_factory._time_stamps = [i * 1_000_000_000 for i in range(6)]
    sequence_factory._values = values
    assert sequence_factory.normalised_area_under_curve == pytest.approx(result)


def test_normalised_area_under_curve_outlier(sequence_factory):
    config.configuration.stopping.maximum_search_time = 5
    start_time = time.time_ns()
    sequence_factory.set_start_time(start_time)
    sequence_factory._time_stamps = [i * 1_000_000_000 for i in range(6)] + [5_500_000_000]
    sequence_factory._values = [0.0, 1 / 2, 2 / 3, 3 / 4, 4 / 5, 5 / 6, 6 / 7]
    expected = 2987 / (840 * 5.5)
    assert sequence_factory.normalised_area_under_curve == pytest.approx(expected)
