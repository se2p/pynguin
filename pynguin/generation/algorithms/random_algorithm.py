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
"""Implements a random test generation algorithm similar to Randoop."""


# pylint: disable=too-few-public-methods
from typing import List, Type, Tuple

from pynguin.configuration import Configuration
from pynguin.generation.algorithms.algorithm import GenerationAlgorithm
from pynguin.generation.executor import Executor
from pynguin.utils.recorder import CoverageRecorder
from pynguin.utils.statements import Sequence


class RandomGenerationAlgorithm(GenerationAlgorithm):
    """Implements a random test generation algorithm similar to Randoop."""

    def __init__(
        self,
        recorder: CoverageRecorder,
        executor: Executor,
        configuration: Configuration,
    ) -> None:
        super().__init__(configuration)
        self._recorder = recorder
        self._executor = executor
        self._configuration = configuration

    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[Sequence], List[Sequence]]:
        """Generates sequences for a given module until the time limit is reached.

        :param time_limit: The maximum amount of time that shall be consumed
        :param modules: The list of types that are available
        :return: A tuple of lists of sequences
        """
        return [], []
