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
"""Provides an abstract base class for a test generation algorithm."""


# pylint: disable=too-few-public-methods
from abc import ABC, abstractmethod

from typing import Tuple, List, Type

from pynguin.configuration import Configuration
from pynguin.utils.statements import Sequence


class GenerationAlgorithm(ABC):
    """Provides an abstract base class for a test generation algorithm."""

    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration

    @abstractmethod
    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[Sequence], List[Sequence]]:
        """Generates sequences for a given module until the time limit is reached.

        :param time_limit: The maximum amount of time that shall be consumed
        :param modules: The list of types that are available
        :return: A tuple of a list of successful sequences and a list of error sequences
        """
