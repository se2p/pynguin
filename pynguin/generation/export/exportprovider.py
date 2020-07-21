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
"""A generic exporter that selects its export strategy based on configuration."""
from typing import Callable, Dict

import pynguin.configuration as config
from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.generation.export.noneexporter import NoneExporter
from pynguin.generation.export.pytestexporter import PyTestExporter
from pynguin.generation.export.unittestexporter import UnitTestExporter


# pylint: disable=too-few-public-methods
class ExportProvider:
    """Provides the possibility to export generated tests using a configured strategy"""

    _strategies: Dict[config.ExportStrategy, Callable[[bool], AbstractTestExporter]] = {
        config.ExportStrategy.PY_TEST: PyTestExporter,
        config.ExportStrategy.UNIT_TEST: UnitTestExporter,
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
        strategy = config.INSTANCE.export_strategy
        if strategy in cls._strategies:
            exp = cls._strategies.get(strategy)
            assert exp, "Export strategy cannot be defined as None"
            return exp(wrap_code)
        raise Exception("Unknown export strategy")
