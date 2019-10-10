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
import sys

from pynguin import Configuration
from pynguin.generation.algorithms.random_algorithm import RandomGenerationAlgorithm
from pynguin.generation.executor import Executor
from pynguin.utils.recorder import CoverageRecorder
from pynguin.utils.statements import Sequence


@pytest.fixture
def configuration():
    return Configuration()


@pytest.fixture
def recorder_mock():
    return MagicMock(CoverageRecorder)


@pytest.fixture
def executor_mock():
    return MagicMock(Executor)


def test_generate_sequences(configuration, recorder_mock, executor_mock):
    generator = RandomGenerationAlgorithm(recorder_mock, executor_mock, configuration)
    assert generator.generate_sequences(0, []) == ([], [])


def test__has_type_violations_empty_list():
    assert not RandomGenerationAlgorithm._has_type_violations([])


def test__has_type_violations_no():
    assert not RandomGenerationAlgorithm._has_type_violations([Exception()])


def test__has_type_violations():
    assert RandomGenerationAlgorithm._has_type_violations(
        [TypeError(), AttributeError()]
    )


def test__mark_original_sequences_empty_list():
    RandomGenerationAlgorithm._mark_original_sequences([])


def test__mark_original_sequences():
    sequence = Sequence()
    assert sequence.counter == 0
    RandomGenerationAlgorithm._mark_original_sequences([sequence])
    assert sequence.counter == 1


def test__purge_sequences_no_counter(configuration, recorder_mock, executor_mock):
    algorithm = RandomGenerationAlgorithm(recorder_mock, executor_mock, configuration)
    purged, remaining = algorithm._purge_sequences([])
    assert purged == []
    assert remaining == []


def test__purge_sequences_empty_sequence(configuration, recorder_mock, executor_mock):
    configuration.counter_threshold = 1
    algorithm = RandomGenerationAlgorithm(recorder_mock, executor_mock, configuration)
    purged, remaining = algorithm._purge_sequences([])
    assert purged == []
    assert remaining == []


def test__purge_sequences(configuration, recorder_mock, executor_mock):
    configuration.counter_threshold = 1
    sequence_1 = Sequence()
    sequence_1.counter = 2
    sequence_2 = Sequence()
    sequence_2.counter = 0
    algorithm = RandomGenerationAlgorithm(recorder_mock, executor_mock, configuration)
    purged, remaining = algorithm._purge_sequences([sequence_1, sequence_2])
    assert purged == [sequence_1]
    assert remaining == [sequence_2]


@pytest.mark.skipif(sys.version_info >= (3, 8), reason="Recursion break in Python 3.8")
def test__choose_random_sequences_no_max_sequence_length(
    configuration, recorder_mock, executor_mock
):
    algorithm = RandomGenerationAlgorithm(recorder_mock, executor_mock, configuration)
    sequence = MagicMock(Sequence)
    sequence.return_value.__len__.return_value = 0
    result = algorithm._choose_random_sequences([sequence])
    assert len(result) >= 0
    assert len(result) <= 1


@pytest.mark.skipif(sys.version_info >= (3, 8), reason="Recursion break in Python 3.8")
def test__chose_random_sequences(configuration, recorder_mock, executor_mock):
    configuration.max_sequence_length = 1
    configuration.max_sequences_combined = 2
    algorithm = RandomGenerationAlgorithm(recorder_mock, executor_mock, configuration)
    sequence_1 = MagicMock(Sequence)
    sequence_1.return_value.__len__.return_value = 1
    sequence_2 = MagicMock(Sequence)
    sequence_2.return_value.__len__.return_value = 1
    result = algorithm._choose_random_sequences([sequence_1, sequence_2])
    assert len(result) >= 0
    assert len(result) <= 2
