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
"""Provides classes to record coverage for executed sequences during test generation."""
import dataclasses
import datetime
import os
import sys
from typing import List, Type, Union, Dict

from coverage import Coverage  # type: ignore


class CoverageRecorder:
    """Records coverage for executed sequences."""

    def __init__(
        self,
        modules: List[Type],
        store: bool = False,
        file_name: Union[str, os.PathLike] = None,
        folder: Union[str, os.PathLike] = None,
    ) -> None:
        self._records: Dict[str, List[Record]] = {}
        self._store: bool = store
        self._modules: List[Type] = modules
        if file_name:
            self._file_name = file_name
        else:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
            self._file_name = timestamp + ".csv"

        if folder:
            self._folder = folder
        else:
            self._folder = os.path.join(
                "out", datetime.datetime.now().strftime("%Y-%m-%d_%H")
            )

        for module in modules:
            self._records[module.__name__] = []

    def add_module(self, module: Type) -> None:
        """Adds a module for recording.

        :param module: The type of the module to add for recording.
        """

    def record_data(self, data: Coverage = None) -> None:
        """Records coverage data.

        :param data: A coverage object containing the collected coverage
        """

    def save(self, folder: Union[str, os.PathLike] = None) -> None:
        """Saves the recorded data to a CSV file.

        :param folder:  An optional path to an output folder
        """


@dataclasses.dataclass
class Record:
    """Represents one coverage record."""

    module: str
    coverage: str
    timestamp: float


# pylint: disable=attribute-defined-outside-init
class HiddenPrints:
    """A context-managing class that binds stdout to a null device."""

    def __enter__(self) -> None:
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, mode="w")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        sys.stdout.close()
        sys.stdout = self._original_stdout
