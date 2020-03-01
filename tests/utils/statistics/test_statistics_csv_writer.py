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
import pynguin.configuration as config
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.utils.statistics.statistics_csv_writer import CoverageStatisticCSVWriter


def test_write_statistics(tmpdir):
    config.INSTANCE.statistics_path = tmpdir
    config.INSTANCE.seed = 42
    execution_result = ExecutionResult()
    execution_result.branch_coverage = 0.72
    writer = CoverageStatisticCSVWriter([execution_result])
    writer.write_statistics()

    with open(tmpdir / "coverage" / "42.csv") as f:
        lines = f.readlines()
        assert len(lines) == 2
