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
import ast
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin import Configuration
from pynguin.generation.export.exporter import Exporter, ExportStrategy
from pynguin.utils.statements import Sequence


@mock.patch("pynguin.generation.export.exporter.PyTestExporter")
def test_export_sequences(pytest_exporter):
    ast_module_mock = MagicMock(ast.Module)
    pytest_exporter.return_value.export_sequences.return_value = ast_module_mock
    configuration_mock = Configuration()
    exporter = Exporter(configuration_mock)
    result = exporter.export_sequences([MagicMock(Sequence)])
    assert result == ast_module_mock


@mock.patch("pynguin.generation.export.exporter.PyTestExporter")
def test_save_ast_to_file(pytest_exporter):
    ast_module_mock = MagicMock(ast.Module)
    configuration_mock = Configuration()
    exporter = Exporter(configuration_mock)
    exporter.save_ast_to_file(ast_module_mock)
    pytest_exporter.assert_called_once()


def test_export_strategy():
    assert str(ExportStrategy.NONE) == "NONE"


def test_export_strategy_from_string():
    strategy = ExportStrategy.from_string("PYTEST_EXPORTER")
    assert strategy == ExportStrategy.PYTEST_EXPORTER


def test_export_strategy_from_non_existing_string():
    with pytest.raises(ValueError):
        ExportStrategy.from_string("FOO")
