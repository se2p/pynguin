#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an extended version of a mock that can be used for type inference."""
from dataclasses import dataclass
from typing import Any, Dict, List, Set
from unittest.mock import MagicMock


@dataclass(frozen=True, eq=False)
class CallInformation:
    """A wrapper to store call information."""

    name: str
    args: List[Any]
    kwargs: Dict[str, Any]

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, CallInformation):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return 31 + 17 * hash(self.name)


class DuckMock(MagicMock):
    """Provides an extended version of a mock for type inference.

    The idea of this is to utilise Python's duck-typing abilities, i.e., if a type A
    provides certain methods it is considered to be of type B—that is defined by
    these methods—even if there is no relationship between A and B in terms of type
    hierarchy.

    This mock captures all calls to its methods and allows to query them after
    execution.  Using the information on the called methods, we can search for an
    appropriate type afterwards that is a “matching duck”.
    """

    @property
    def call_information(self) -> Set[CallInformation]:
        """Provides a set of the called method names on this mock instance.

        Returns:
            A set of the called method names
        """
        call_information: Set[CallInformation] = set()
        for call in self.mock_calls:
            information = CallInformation(
                name=call[0],
                args=[
                    arg for arg in call[1]  # pylint: disable=unnecessary-comprehension
                ],
                kwargs=call[2],
            )
            call_information.add(information)
        return call_information

    @property
    def method_call_information(self) -> Dict[str, CallInformation]:
        """Provides a dictionary of method name and its call information.

        Returns:
            A dictionary of method name and its call information
        """
        return {call.name: call for call in self.call_information}
