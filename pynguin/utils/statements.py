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
"""Provides various types of statements, similar to an AST."""
# pylint: disable=too-few-public-methods
from typing import List, Dict, Any, Union, Iterator


class Statement:
    """A simple program statement."""


class Sequence:
    """A sequence simply is a list of statements."""

    def __init__(self,) -> None:
        self._statements: List[Statement] = []
        self._arcs = None
        self._output_values: Dict[str, Any] = {}
        self._counter: int = 0

    def append(self, statement: Any) -> None:
        """Appends a statement object to the sequence.

        :param statement: The statement object to append
        """
        assert isinstance(statement, Statement)
        self._statements.append(statement)

    def pop(self) -> Statement:
        """Pops the last inserted statement from the sequence and returns it.

        :return: The last inserted statement from the sequence
        """
        return self._statements.pop()

    def __len__(self) -> int:
        return self._statements.__len__()

    def __getitem__(self, item: Union[int, slice]) -> Union[Statement, List[Statement]]:
        return self._statements.__getitem__(item)

    def __add__(self, other: Any) -> "Sequence":
        assert isinstance(other, Sequence)
        # pylint: disable=protected-access
        self._statements = self._statements.__add__(other._statements)
        return self

    def __iter__(self) -> Iterator[Statement]:
        return self._statements.__iter__()

    def __reversed__(self) -> Iterator[Statement]:
        return reversed(self._statements)

    # pylint: disable=protected-access
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Sequence):
            return False

        if not self._arcs or not other._arcs:
            return self._statements == other._statements

        return self._arcs == other._arcs

    @property
    def arcs(self):
        """Returns the arcs property."""
        return self._arcs

    @arcs.setter
    def arcs(self, arcs) -> None:
        self._arcs = arcs

    @property
    def output_values(self) -> Dict[str, Any]:
        """Returns the output values property."""
        return self._output_values

    @output_values.setter
    def output_values(self, output_values: Dict[str, Any]) -> None:
        self._output_values = output_values

    @property
    def counter(self) -> int:
        """Returns the counter property."""
        return self._counter

    @counter.setter
    def counter(self, counter: int) -> None:
        self._counter = counter
