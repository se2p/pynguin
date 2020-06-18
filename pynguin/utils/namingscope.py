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
"""Provides a naming scope."""

from typing import Any, Dict


class NamingScope:
    """Maps objects to unique, human friendly names."""

    def __init__(self, prefix: str = "var") -> None:
        """Initialises the scope

        Args:
            prefix: The prefix that will be used in the name.
        """
        self._next_index = 0
        self._known_name_indices: Dict[Any, int] = {}
        self._prefix = prefix

    def get_name(self, obj: Any) -> str:
        """Get the name for the given object within this scope.

        Args:
            obj: the object for which a name is requested

        Returns:
            the variable name
        """
        if obj in self._known_name_indices:
            index = self._known_name_indices.get(obj)
        else:
            index = self._next_index
            self._known_name_indices[obj] = index
            self._next_index += 1
        return self._prefix + str(index)

    @property
    def known_name_indices(self) -> Dict[Any, int]:
        """Provides a dict of objects and their corresponding name.

        Returns:
            A dict of objects and their corresponding name
        """
        return self._known_name_indices
