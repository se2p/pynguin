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
from typing import Sequence, Any

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


def next_int(lower_bound=-100, upper_bound=100) -> int:
    """Provide a random integer number from an interval.

    If no lower or upper bound is given, the integer is chosen from the interval
    including -100 to excluded 100.

    :param lower_bound: The lower bound for the number selection,
    :param upper_bound: The upper bound for the number selection, excluded
    """
    return RNG.randrange(lower_bound, upper_bound)


def next_float(lower_bound=0, upper_bound=1) -> float:
    """Provide a random float number uniformly selected from an interval.

    If no lower or upper bound is given, the float is chosen uniformly from the
    interval [0,1].

    :param lower_bound: The lower bound for the number selection
    :param upper_bound: The upper bound for the number selection
    :return: A random float number from the interval
    """
    return RNG.uniform(lower_bound, upper_bound)


def next_gaussian() -> float:
    """
    Returns the next pseudorandom, Gaussian ("normally") distributed
    value with mu 0.0 and sigma 1.0.
    """
    return RNG.gauss(0, 1)


def choice(sequence: Sequence[Any]) -> Any:
    """Return a random element from a non-empty sequence.

    If the sequence is empty, it raises an `IndexError`.

    :param sequence: The non-empty sequence to choose from
    :return: An randomly selected element of the sequence
    """
    return RNG.choice(sequence)
