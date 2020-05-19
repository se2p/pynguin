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
from unittest.mock import MagicMock

import pynguin.configuration as config
from pynguin.utils.statistics.statisticsbackend import (
    ConsoleStatisticsBackend,
    CSVStatisticsBackend,
    OutputVariable,
)


def test_output_variable():
    name = "foo"
    value = MagicMock(OutputVariable)
    variable = OutputVariable(name, value)
    assert variable.name == name
    assert variable.value == value


def test_write_data_csv_backend(tmpdir):
    config.INSTANCE.report_dir = tmpdir / "statistics"
    data_1 = {
        "module": OutputVariable("module", "foo"),
        "value": OutputVariable("value", "bar"),
    }
    data_2 = {
        "module": OutputVariable("module", "bar"),
        "value": OutputVariable("value", "baz"),
    }
    backend = CSVStatisticsBackend()
    backend.write_data(data_1)
    backend.write_data(data_2)


def test_write_data_console_backend(capsys):
    data = {
        "module": OutputVariable("module", "foo"),
        "value": OutputVariable("value", "bar"),
    }
    backend = ConsoleStatisticsBackend()
    backend.write_data(data)
    captured = capsys.readouterr()
    assert "foo" in captured.out
    assert "bar" in captured.out
    assert captured.err == ""
