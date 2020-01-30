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
import string

import pynguin.utils.randomness as randomness


def test_next_char_printable():
    assert randomness.next_char() in string.printable


def test_next_string_length():
    assert len(randomness.next_string(15)) == 15


def test_next_string_printable():
    rand = randomness.next_string(15)
    assert all(char in string.printable for char in rand)


def test_next_int():
    rand = randomness.next_int(lower_bound=-50, upper_bound=50)
    assert -50 <= rand <= 50
