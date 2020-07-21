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

import pytest

import pynguin.configuration as config
from pynguin.generation.export.exportprovider import ExportProvider
from pynguin.generation.export.noneexporter import NoneExporter
from pynguin.generation.export.pytestexporter import PyTestExporter
from pynguin.generation.export.unittestexporter import UnitTestExporter


@pytest.mark.parametrize(
    "conf,instance",
    [
        pytest.param(config.ExportStrategy.PY_TEST, PyTestExporter),
        pytest.param(config.ExportStrategy.UNIT_TEST, UnitTestExporter),
        pytest.param(config.ExportStrategy.NONE, NoneExporter),
    ],
)
def test_get_exporter(conf, instance):
    config.INSTANCE.export_strategy = conf
    exporter = ExportProvider.get_exporter()
    assert isinstance(exporter, instance)


def test_unknown_strategy():
    config.INSTANCE.export_strategy = MagicMock(config.ExportStrategy)
    with pytest.raises(Exception):
        ExportProvider.get_exporter()
