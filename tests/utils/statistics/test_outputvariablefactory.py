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
import time

import pytest

import pynguin.configuration as config
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.utils.statistics.outputvariablefactory import (
    DirectSequenceOutputVariableFactory,
    ChromosomeOutputVariableFactory,
    SequenceOutputVariableFactory,
)
from pynguin.utils.statistics.statistics import RuntimeVariable


class _DummyChromosomeOutputVariableFactory(ChromosomeOutputVariableFactory):
    def get_data(self, individual: tsc.TestSuiteChromosome) -> int:
        return 42


class _DummySequenceOutputVariableFactory(SequenceOutputVariableFactory):
    def get_value(self, individual: tsc.TestSuiteChromosome) -> int:
        return 42


@pytest.fixture
def factory():
    return DirectSequenceOutputVariableFactory(
        RuntimeVariable.TotalExceptionsTimeline, 0
    )


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
    config.INSTANCE.budget = 0
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
        assert name == f"CoverageTimeline_T{index}"
        assert value == 42

    config.INSTANCE.budget = 0.005
    chromosome_2 = tsc.TestSuiteChromosome()
    sequence_factory.set_start_time(time.time_ns())
    time.sleep(0.05)
    sequence_factory.update(chromosome)
    time.sleep(0.05)
    sequence_factory.update(chromosome_2)
    time.sleep(0.05)
    variables = sequence_factory.get_output_variables()
    [
        check_result(var.name, var.value, index + 1)
        for index, var in enumerate(variables)
    ]
    assert len(variables) > 0


def test_get_time_line_value_without_timestamps(sequence_factory):
    assert sequence_factory._get_time_line_value("foo") == 0
