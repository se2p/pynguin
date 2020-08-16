#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
