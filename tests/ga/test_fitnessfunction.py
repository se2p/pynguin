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

import hypothesis.strategies as st
import pytest
from hypothesis import given

import pynguin.ga.fitnessfunction as ff


@pytest.fixture
def fitness_function():
    return MagicMock(ff.FitnessFunction)


def test_normalise_less_zero():
    with pytest.raises(RuntimeError):
        ff.FitnessFunction.normalise(-1)


def test_normalise_infinity():
    assert ff.FitnessFunction.normalise(float("inf")) == 1.0


@given(
    st.floats(
        min_value=0.0, max_value=float("inf"), exclude_min=False, exclude_max=True
    )
)
def test_normalise(value):
    assert ff.FitnessFunction.normalise(value) == value / (1.0 + value)


def test_validation_ok():
    values = ff.FitnessValues(0, 0)
    assert len(values.validate()) == 0


def test_validation_wrong_fitness():
    values = ff.FitnessValues(-1, 0)
    assert len(values.validate()) == 1


def test_validation_wrong_coverage():
    values = ff.FitnessValues(0, 5)
    assert len(values.validate()) == 1


def test_validation_both_wrong():
    values = ff.FitnessValues(-1, 5)
    assert len(values.validate()) == 2
