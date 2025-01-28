#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Module-level docstring."""
import string

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def public_function(a: int) -> float:
    """A public function

    Args:
        a: Argument description

    Returns:
        Return description
    """
    return float(a)


class AClass:
    """Class-level docstring."""

    def __init__(self, b: float) -> None:
        self._b = b

    def public_method(self, c: str) -> str:
        """A public method

        Args:
            c: Argument description

        Returns:
            Return description
        """
        return self._protected_method(c)

    def _protected_method(self, c: str) -> str:
        """A protected method

        Args:
            c: Argument description

        Returns:
            Return description
        """
        return self.__private_method(c)

    def __private_method(self, c: str) -> str:
        """A private method

        Args:
            c: Argument description

        Returns:
            Return description

        Raises:
            ``ValueError`` if b was negative
        """
        if self._b > 0:
            return f"{c}: {self._b}"
        raise ValueError("Do not support negative values for b")

    @property
    def b(self) -> float:
        """Provides the b property.

        Returns:
            The b property
        """
        return self._b

    async def asynchronous_method(self) -> Iterator[str]:
        """Yields some characters

        Yields:
            Some characters
        """
        for character in string.ascii_letters:
            yield f"{character}: {self.__twice(self._b)}"

    @staticmethod
    def __twice(x: complex | int | float) -> complex | int | float:
        return 2 * x
