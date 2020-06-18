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
"""Provides an interface for a statistics writer."""
import csv
import ctypes
import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generic, TypeVar

import pynguin.configuration as config

T = TypeVar("T")  # pylint: disable=invalid-name


@dataclass(frozen=True)
class OutputVariable(Generic[T]):
    """Encapsulates an output variable of the result statistics."""

    name: str
    value: T


# pylint: disable=too-few-public-methods
class AbstractStatisticsBackend(metaclass=ABCMeta):
    """An interface for a statistics writer."""

    @abstractmethod
    def write_data(self, data: Dict[str, OutputVariable]) -> None:
        """Write the particular statistics values.

        Args:
            data: the data to write
        """


# pylint: disable=too-few-public-methods
class CSVStatisticsBackend(AbstractStatisticsBackend):
    """A statistics backend writing all (selected) output variables to a CSV file."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        csv.field_size_limit(int(ctypes.c_ulong(-1).value // 2))

    def write_data(self, data: Dict[str, OutputVariable]) -> None:
        try:
            output_dir = self._get_report_dir()
            output_file = output_dir / "statistics.csv"
            with output_file.open(mode="a") as csv_file:
                field_names = [k for k, _ in data.items()]
                csv_writer = csv.DictWriter(
                    csv_file, fieldnames=field_names, quoting=csv.QUOTE_NONNUMERIC
                )
                if output_file.stat().st_size == 0:  # file is empty, write CSV header
                    csv_writer.writeheader()
                csv_writer.writerow({k: str(v.value) for k, v in data.items()})
        except OSError as error:
            logging.warning("Error while writing statistics: %s", error)

    def _get_report_dir(self) -> Path:
        report_dir = Path(config.INSTANCE.report_dir).absolute()
        if not report_dir.exists():
            try:
                report_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                msg = "Cannot create report dir %s", config.INSTANCE.report_dir
                self._logger.error(msg)
                raise RuntimeError(msg)
        return report_dir


# pylint: disable=too-few-public-methods
class ConsoleStatisticsBackend(AbstractStatisticsBackend):
    """Simple dummy backend that just outputs all output variables to the console"""

    def write_data(self, data: Dict[str, OutputVariable]) -> None:
        for key, value in data.items():
            print(f"{key}: {value}")
