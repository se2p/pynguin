#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import string

import hypothesis.strategies as st

from hypothesis import given

from pynguin.utils import randomness


def test_next_char_printable():
    assert randomness.next_char() in string.printable


def test_next_string_length():
    assert len(randomness.next_string(15)) == 15


def test_next_string_printable():
    rand = randomness.next_string(15)
    assert all(char in string.printable for char in rand)


def test_next_string_zero():
    rand = randomness.next_string(0)
    assert not rand


def test_next_int():
    rand = randomness.next_int(0, 50)
    assert 0 <= rand < 50


def test_next_float():
    rand = randomness.next_float()
    assert 0 <= rand <= 1


def test_next_gaussian():
    rand = randomness.next_gaussian()
    assert isinstance(rand, float)


def test_next_bool():
    rand = randomness.next_bool()
    assert isinstance(rand, bool)


def test_next_byte():
    rand = randomness.next_byte()
    assert isinstance(rand, int)
    assert 0 <= rand <= 255


def test_next_bytes_zero():
    rand = randomness.next_bytes(0)
    assert rand == b""


def test_next_bytes_fixed():
    rand = randomness.next_bytes(15)
    assert len(rand) == 15


def test_next_bytes_valid_bytes():
    rand = randomness.next_bytes(15)
    assert all(0 <= byte <= 255 for byte in rand)


def test_choice():
    sequence = ["a", "b", "c"]
    result = randomness.choice(sequence)
    assert result in {"a", "b", "c"}


def test_choices():
    sequence = ["a", "b", "c"]
    weights = [0.1, 0.5, 0.3]
    result = randomness.choices(sequence, weights)
    assert len(result) == 1
    assert result[0] in {"a", "b", "c"}


def test_get_seed():
    rng = randomness.Random()
    assert rng.get_seed() != 0


@given(st.integers())
def test_set_get_seed(seed):
    rng = randomness.Random()
    rng.seed(seed)
    assert rng.get_seed() == seed
