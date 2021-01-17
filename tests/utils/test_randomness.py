#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import string

import hypothesis.strategies as st
from hypothesis import given

import pynguin.utils.randomness as randomness


def test_next_char_printable():
    assert randomness.next_char() in string.printable


def test_next_string_length():
    assert len(randomness.next_string(15)) == 15


def test_next_string_printable():
    rand = randomness.next_string(15)
    assert all(char in string.printable for char in rand)


def test_next_string_zero():
    rand = randomness.next_string(0)
    assert rand == ""


def test_next_int():
    rand = randomness.next_int(0, 50)
    assert 0 <= rand < 50


def test_next_float():
    rand = randomness.next_float()
    assert 0 <= rand <= 1


def test_next_gaussian():
    rand = randomness.next_gaussian()
    assert isinstance(rand, float)


def test_choice():
    sequence = ["a", "b", "c"]
    result = randomness.choice(sequence)
    assert result in ("a", "b", "c")


def test_get_seed():
    rng = randomness.Random()
    assert rng.get_seed() != 0


@given(st.integers())
def test_set_get_seed(seed):
    rng = randomness.Random()
    rng.seed(seed)
    assert rng.get_seed() == seed
