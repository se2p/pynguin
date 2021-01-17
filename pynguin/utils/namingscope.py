#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
        """Provides a dict of objects and their corresponding index.

        Returns:
            A dict of objects and their corresponding name
        """
        return self._known_name_indices
