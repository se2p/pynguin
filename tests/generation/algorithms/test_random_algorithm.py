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

from pynguin import Configuration
from pynguin.generation.algorithms.random_algorithm import RandomGenerationAlgorithm
from pynguin.generation.executor import Executor
from pynguin.utils.recorder import CoverageRecorder


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
