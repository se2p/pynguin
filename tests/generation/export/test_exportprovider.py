#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
    config.configuration.export_strategy = conf
    exporter = ExportProvider.get_exporter()
    assert isinstance(exporter, instance)


def test_unknown_strategy():
    config.configuration.export_strategy = MagicMock(config.ExportStrategy)
    with pytest.raises(Exception):
        ExportProvider.get_exporter()
