#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.utils.atomicinteger import AtomicInteger


@pytest.fixture
def atomic_integer_null():
    return AtomicInteger()


@pytest.fixture
def atomic_integer_nonnull():
    return AtomicInteger(value=42)


def test_inc(atomic_integer_null):
    assert atomic_integer_null.inc() == 1
    atomic_integer_null.inc()
    assert atomic_integer_null.value == 2


def test_dec(atomic_integer_nonnull):
    assert atomic_integer_nonnull.dec() == 41
    atomic_integer_nonnull.dec()
    assert atomic_integer_nonnull.value == 40


def test_set_get_value(atomic_integer_null):
    assert atomic_integer_null.value == 0
    atomic_integer_null.value = 23
    assert atomic_integer_null.value == 23
