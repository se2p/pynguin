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
"""Provides an executor that executes generated sequences."""


# pylint: disable=no-else-return, inconsistent-return-statements
from typing import List, Any, Tuple, Dict

from coverage import Coverage  # type: ignore

from pynguin.utils.statements import Sequence


class Executor:
    """An executor that executes the generated sequences."""

    def __init__(self, module_paths: List[str], measure_coverage: bool = False) -> None:
        self._module_paths = module_paths
        self._measure_coverage = measure_coverage
        self._coverage: Coverage = None
        self._accumulated_coverage: Coverage = Coverage(branch=True)
        self._load_coverage: Coverage = Coverage(branch=True)
        self._classes: List[Any] = []
        self.load_modules()

    @property
    def accumulated_coverage(self) -> Coverage:
        """Provides access to the accumulated coverage property."""
        return self._accumulated_coverage

    def execute(
        self, sequence: Sequence
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Exception], Sequence]:
        """Executes a sequence of statements.

        :param sequence:
        :return:
        """

    def load_modules(self, reload: bool = False) -> None:
        """Loads the module before execution.

        :param reload: An optional boolean indicating whether modules should be
        reloaded.
        """
