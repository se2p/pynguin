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
"""
Provides iterators that are more Java-esque.
"""
from typing import List, Any


class ModifyingIterator:
    """
    Small iterator that allows to modify the underlying list while iterating over it.
    """

    def __init__(self, elements: List[Any]):
        """
        Initialize iterator with the given list.
        """

        assert isinstance(elements, list), "Only works on lists"
        self.elements: List[Any] = elements
        self.idx = -1

    def next(self):
        """
        Checks if there is a next element. If so, returns True and set current to the next element.
        Otherwise False is returned.
        """
        if self.idx + 1 < len(self.elements):
            self.idx += 1
            return True
        return False

    def current(self):
        """
        Get the current element.
        """
        return self.elements[self.idx]

    def has_previous(self):
        """
        Check if there is a previous element.
        """
        return self.idx > 0

    def previous(self):
        """
        Get the previous element.
        """
        assert self.has_previous(), "No previous element"
        return self.elements[self.idx - 1]

    def insert_before(self, insert: List[Any], offset=0):
        """
        Insert another list before the current element.
        Offset can be used to insert the list earlier in the list.
        """
        assert offset >= 0, "Offset must be non negative"
        assert self.idx - offset >= 0, "Cannot insert out of range"
        self.elements[self.idx - offset : self.idx - offset] = insert
        self.idx += len(insert)
