#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""A generic exporter that selects its export strategy based on configuration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pynguin.configuration as config
from pynguin.generation.export.noneexporter import NoneExporter
from pynguin.generation.export.pytestexporter import PyTestExporter

if TYPE_CHECKING:
    from pynguin.generation.export.abstractexporter import AbstractTestExporter


# pylint: disable=too-few-public-methods
class ExportProvider:
    """Provides the possibility to export generated tests using a configured strategy"""

    _strategies: dict[config.ExportStrategy, Callable[[bool], AbstractTestExporter]] = {
        config.ExportStrategy.PY_TEST: PyTestExporter,
        config.ExportStrategy.NONE: NoneExporter,
    }

    @classmethod
    def get_exporter(cls, wrap_code: bool = False) -> AbstractTestExporter:
        """Provides an instance of the configured test exporter.

        The flag `wrap_code` indicates whether or not the exported code should be
        wrapped with a `try`-`except`-block.

        Args:
            wrap_code: Whether or not to wrap the generated code

        Returns:
            A test-exporter instance

        Raises:
            Exception: If no appropriate strategy could be found
        """
        strategy = config.configuration.test_case_output.export_strategy
        if strategy in cls._strategies:
            exp = cls._strategies.get(strategy)
            assert exp, "Export strategy cannot be defined as None"
            return exp(wrap_code)
        raise Exception("Unknown export strategy")
