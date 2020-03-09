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
from hypothesis import given

import hypothesis.strategies as st

import pynguin.ga.fitnessfunction as ff


class _DummyFitnessFunction(ff.FitnessFunction):
    def get_fitness(self, individual) -> float:
        pass

    def is_maximisation_function(self) -> bool:
        pass


@pytest.fixture
def fitness():
    return _DummyFitnessFunction()


@pytest.fixture
def fitness_function():
    return MagicMock(ff.FitnessFunction)


def test_normalise_less_zero(fitness):
    with pytest.raises(RuntimeError):
        fitness.normalise(-1)


def test_normalise_infinity(fitness):
    assert fitness.normalise(float("inf")) == 1.0


@given(
    st.floats(
        min_value=0.0, max_value=float("inf"), exclude_min=False, exclude_max=True
    )
)
def test_normalise(fitness, value):
    assert fitness.normalise(value) == value / (1.0 + value)


def test_update_individual(fitness, fitness_function, mocker):
    individual = mocker.patch("pynguin.ga.chromosome.Chromosome")
    fitness.update_individual(fitness_function, individual, 0.42)
    individual.set_fitness.assert_called_once()
    individual.increase_number_of_evaluations.assert_called_once()
