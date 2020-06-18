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
"""Provides iterators that are more Java-esque."""
from typing import Generic, List, TypeVar

T = TypeVar("T")  # pylint:disable=invalid-name


class ListIterator(Generic[T]):
    """Small iterator that allows to modify the underlying list while iterating over
    it."""

    def __init__(self, elements: List[T]) -> None:
        """Initialize iterator with the given list.

        Args:
            elements: the list to use for initialisation
        """

        assert isinstance(elements, list), "Only works on lists"
        self._elements: List[T] = elements
        self._idx = -1

    def next(self) -> bool:
        """Checks if there is a next element.

        If so, returns True and sets current to the next element.
        Otherwise False is returned.

        Returns:
            Whether or not there is a next element
        """
        if self.can_peek():
            self._idx += 1
            return True
        return False

    def current(self) -> T:
        """Get the current element.

        Returns:
            The current element
        """
        return self._elements[self._idx]

    def current_index(self) -> int:
        """Return current index.

        Returns:
            The current index
        """
        return self._idx

    def has_previous(self) -> bool:
        """Check if there is a previous element.

        Returns:
            Whether or not a previous element exists
        """
        return self._idx > 0

    def previous(self) -> T:
        """Get the previous element.

        Returns:
            The previous element
        """
        assert self.has_previous(), "No previous element"
        return self._elements[self._idx - 1]

    def insert_before(self, insert: List[T], offset: int = 0) -> None:
        """Insert another list before the current element.

        Offset can be used to insert the list earlier in the list.

        Args:
            insert: the list to be inserted
            offset: the offset of the insert
        """
        assert offset >= 0, "Offset must be non negative"
        assert self._idx - offset >= 0, "Cannot insert out of range"
        self._elements[self._idx - offset : self._idx - offset] = insert
        self._idx += len(insert)

    def can_peek(self, distance: int = 1) -> bool:
        """Is there a next element?

        Args:
            distance: the distance from the current index

        Returns:
            Whether or not there is a next element to be peeked
        """
        return self._idx + distance < len(self._elements)

    def peek(self, distance: int = 1) -> T:
        """Provide the element that is next in the list, without
        moving the current pointer.

        Args:
             distance: the distance from the current index

        Returns:
            The element
        """
        assert self.can_peek(distance), "Cannot peek"
        return self._elements[self._idx + distance]

    def insert_after_current(self, insert: List[T], offset: int = 0) -> None:
        """Insert a list of elements.

        Warning! the inserted elements will be visited again when the iterator is
        further traversed.

        Args:
            insert: the list to be inserted
            offset: some additional offset
        """
        assert offset >= 0, "Offset must be non negative"
        self._elements[self._idx + offset + 1 : self._idx + offset + 1] = insert
