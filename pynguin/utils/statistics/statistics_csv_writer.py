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
"""Provides writers for statistics to CSV files."""
import csv
import pathlib
from typing import List

import pynguin.configuration as config
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.utils.statistics.abstractstatisticswriter import AbstractStatisticsWriter


# pylint: disable=too-few-public-methods
class CoverageStatisticCSVWriter(AbstractStatisticsWriter):
    """
    A statistics writer that writes a list of coverage values from execution results
    into a CSV file.
    """

    def __init__(
        self, execution_results: List[ExecutionResult], folder: str = "coverage"
    ) -> None:
        self._execution_results = execution_results
        self._folder = folder

    def write_statistics(self) -> None:
        assert config.INSTANCE.statistics_path is not None
        output_dir = pathlib.Path(config.INSTANCE.statistics_path) / self._folder
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{config.INSTANCE.seed}.csv"
        field_names = ["timestamp", "coverage"]
        with open(output_file, mode="w") as csv_file:
            writer = csv.DictWriter(csv_file, field_names)
            writer.writeheader()
            for result in self._execution_results:
                self._write_coverage(result, writer)

    @staticmethod
    def _write_coverage(result: ExecutionResult, writer: csv.DictWriter) -> None:
        entry = {
            "timestamp": result.time_stamp,
            "coverage": result.branch_coverage,
        }
        writer.writerow(entry)
