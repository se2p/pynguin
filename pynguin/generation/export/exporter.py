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
import ast
import os
from typing import List

import pynguin.configuration as config
from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.generation.export.pytestexporter import PyTestExporter
from pynguin.utils.statements import Sequence


class Exporter:
    """Provides the possibility to export generated tests using a configured strategy"""

    def __init__(self) -> None:
        self._strategy = self._configure_strategy()

    @staticmethod
    def _configure_strategy() -> AbstractTestExporter:
        # if self._configuration.export_strategy == ExportStrategy.PYTEST_EXPORTER:
        return PyTestExporter(
            config.INSTANCE.module_names,
            os.path.join(config.INSTANCE.output_path, f"{config.INSTANCE.seed}.py"),
        )

    # raise Exception("Illegal export strategy")

    def export_sequences(self, sequences: List[Sequence]) -> ast.Module:
        """Exports sequences to an AST module, where each sequence is a method.

        :param sequences: A list of sequences
        :return: An AST module that contains the methods for these sequences
        """
        return self._strategy.export_sequences(sequences)

    def save_ast_to_file(self, module: ast.Module) -> None:
        """Saves an AST module to a file.

        :param module: The AST module
        """
        self._strategy.save_ast_to_file(module)
