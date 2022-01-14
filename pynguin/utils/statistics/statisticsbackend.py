#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an interface for a statistics writer."""
from __future__ import annotations

import csv
import ctypes
import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

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
    def write_data(self, data: dict[str, OutputVariable]) -> None:
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

    def write_data(self, data: dict[str, OutputVariable]) -> None:
        try:
            output_dir = Path(
                config.configuration.statistics_output.report_dir
            ).resolve()
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
            logging.exception("Error while writing statistics: %s", error)


# pylint: disable=too-few-public-methods
class ConsoleStatisticsBackend(AbstractStatisticsBackend):
    """Simple dummy backend that just outputs all output variables to the console"""

    def write_data(self, data: dict[str, OutputVariable]) -> None:
        for key, value in data.items():
            print(f"{key}: {value}")
