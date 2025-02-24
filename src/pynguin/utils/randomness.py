#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a singleton instance of Random that can be seeded."""

from __future__ import annotations

import random
import string

from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar


if TYPE_CHECKING:
    from collections.abc import Sequence


class Random(random.Random):  # noqa: S311
    """Override Random to allow querying for the seed value.

    It generates a seed if none was given from `time.time_ns()`.  This is NOT
    cryptographically safe, and this random-number generator should not be used for
    anything related to cryptography.  For our case, however, it is good enough to
    use the current time stamp in nano seconds as seed.
    """

    def __init__(self, x=None) -> None:  # noqa: D107
        super().__init__(x)
        self._current_seed: int | None = None
        self.seed(x)

    def seed(self, a=None, version: int = 2) -> None:  # noqa: D102
        if a is None:
            import time  # noqa: PLC0415

            a = time.time_ns()

        self._current_seed = a
        super().seed(a)

    def get_seed(self) -> int:
        """Provides the used seed for random-number generation.

        Returns:
            Provides the used seed
        """
        assert self._current_seed is not None
        return self._current_seed


RNG: Random = Random()
RNG.seed()


def next_char() -> str:
    """Create a random printable ascii char.

    Returns:
        A random printable ascii char
    """
    return RNG.choice(string.printable)


def next_string(length: int) -> str:
    """Create a random string consisting of printable and with the given length.

    Args:
        length: the desired length

    Returns:
        A string of given length
    """
    return "".join(next_char() for _ in range(length))


def next_int(lower_bound=-100, upper_bound=100) -> int:
    """Provide a random integer number from an interval.

    If no lower or upper bound is given, the integer is chosen from the interval
    including -100 to excluded 100.

    Args:
        lower_bound: The lower bound for the number selection,
        upper_bound: The upper bound for the number selection, excluded

    Returns:
        A random integer from the interval
    """
    return RNG.randrange(lower_bound, upper_bound)


def next_float(lower_bound=0, upper_bound=1) -> float:
    """Provide a random float number uniformly selected from an interval.

    If no lower or upper bound is given, the float is chosen uniformly from the
    interval [0,1].

    Args:
        lower_bound: The lower bound for the number selection
        upper_bound: The upper bound for the number selection

    Returns:
        A random float number from the interval
    """
    return RNG.uniform(lower_bound, upper_bound)


def next_gaussian() -> float:
    """Returns the next pseudorandom.

    Use a Gaussian ("normally") distribution value with mu 0.0 and sigma 1.0.

    Returns:
        The next random number
    """
    return RNG.gauss(0, 1)


_T = TypeVar("_T")


def choice(sequence: Sequence[_T]) -> _T:
    """Return a random element from a non-empty sequence.

    If the sequence is empty, it raises an `IndexError`.

    Args:
        sequence: The non-empty sequence to choose from

    Returns:
        An randomly selected element of the sequence
    """
    return RNG.choice(sequence)


def choices(
    population: Sequence[Any],
    weights: Sequence[float] | None = None,
    *,
    cum_weights: Sequence[float] | None = None,
    k: int = 1,
) -> list[Any]:
    """Return a k sized list of population elements chosen with replacement.

    If the relative weights or cumulative weights are not specified, the selections are
    made with equal probability.

    Args:
        population: The non-empty population to choose from
        weights: A sequence of weights
        cum_weights: A sequence of cumulative weights
        k: The size of the sample

    Returns:
        A list of sampled elements from the sequence with respect to the weight
    """
    return RNG.choices(population, weights, cum_weights=cum_weights, k=k)


def next_bool() -> bool:
    """Returns a random boolean.

    Returns:
        A random boolean
    """
    return next_float() < 0.5


def next_byte() -> int:
    """Returns a random byte.

    Returns:
        A random byte.
    """
    return RNG.getrandbits(8)


def next_bytes(length: int) -> bytes:
    """Create random bytes of given length.

    Args:
        length: the length of the bytes

    Returns:
        Random bytes of given length.
    """
    return bytes(next_byte() for _ in range(length))
