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
from pynguin.generation.valuegeneration import init_value
from pynguin.utils.string import String


def test_init_value_int():
    result = init_value(int, [])
    assert result in range(-100, 100)


def test_init_value_string():
    String.observed = []
    String.observed.append("foo")
    String.observed.append("bar")
    result = init_value(String, [])
    assert result in {"foo", "bar"}


def test_init_value_string_no_strings_seen():
    String.observed = []
    result = init_value(String, [])
    assert result == "Test"


def test_init_value_bool():
    result = init_value(bool, [])
    assert result or not result


def test_init_value_complex():
    result = init_value(complex, [])
    assert isinstance(result, complex)
    assert result.real in range(-100, 100)
    assert result.imag in range(-100, 100)


def test_init_value_float():
    result = init_value(float, [])
    assert isinstance(result, float)
    assert result >= -100
    assert result < 100
