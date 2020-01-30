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
"""Provides a singleton instance of Random that can be seeded."""
import random
import string

RNG: random.Random = random.Random()


def next_char() -> str:
    """Create a random printable ascii char."""
    return RNG.choice(string.printable)


def next_string(length: int) -> str:
    """
    Create a random string consisting of printable and with the given length.
    :param length: the desired length
    """
    return "".join(next_char() for _ in range(length))
