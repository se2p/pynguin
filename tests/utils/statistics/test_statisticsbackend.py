#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
    config.configuration.report_dir = tmpdir / "statistics"
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
