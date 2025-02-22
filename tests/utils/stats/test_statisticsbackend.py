#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pathlib import Path
from unittest.mock import MagicMock

import pynguin.configuration as config

from pynguin.utils.statistics.statisticsbackend import ConsoleStatisticsBackend
from pynguin.utils.statistics.statisticsbackend import CSVStatisticsBackend
from pynguin.utils.statistics.statisticsbackend import OutputVariable


def test_output_variable():
    name = "foo"
    value = MagicMock(OutputVariable)
    variable = OutputVariable(name, value)
    assert variable.name == name
    assert variable.value == value


def test_write_data_csv_backend(tmpdir):
    statistics_dir = tmpdir / "statistics"
    Path(statistics_dir).mkdir(parents=True, exist_ok=True)
    config.configuration.statistics_output.report_dir = statistics_dir
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
    assert not captured.err
