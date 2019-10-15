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
from enum import Enum
from typing import List

from pynguin.configuration import Configuration
from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.generation.export.pytestexporter import PyTestExporter
from pynguin.utils.statements import Sequence


class ExportStrategy(Enum):
    """Contains all available export strategies."""

    PYTEST_EXPORTER = "PYTEST_EXPORTER"
    NONE = "NONE"

    def __str__(self) -> str:
        return self.value

    @staticmethod
    def from_string(string):
        """Returns a representation of the enum value from its string name.

        :return: A representation
        :raises: ValueError if the representation was not found
        """
        try:
            return ExportStrategy[string]
        except KeyError:
            raise ValueError()


class Exporter:
    """Provides the possibility to export generated tests using a configured strategy"""

    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration
        self._strategy = self._configure_strategy()

    def _configure_strategy(self) -> AbstractTestExporter:
        # if self._configuration.export_strategy == ExportStrategy.PYTEST_EXPORTER:
        return PyTestExporter(
            self._configuration.module_names,
            os.path.join(
                self._configuration.tests_output, f"{self._configuration.seed}.py"
            ),
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
