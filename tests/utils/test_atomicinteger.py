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
