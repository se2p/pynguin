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
"""An abstract test exporter"""
import ast
import os
from abc import ABCMeta, abstractmethod

from typing import Union, List

import astor  # type: ignore

import pynguin.testcase.testcase as tc


class AbstractTestExporter(metaclass=ABCMeta):
    """An abstract test exporter"""

    def __init__(self, path: Union[str, os.PathLike] = "") -> None:
        self._path = path

    @abstractmethod
    def export_sequences(self, sequences: List[tc.TestCase]) -> ast.Module:
        """Exports sequences to an AST module, where each sequence is a method.

        :param sequences: A list of sequences
        :return: An AST module that contains the methods for these sequences
        """

    def save_ast_to_file(self, module: ast.Module) -> None:
        """Saves an AST module to a file.

        :param module: The AST module
        """
        if self._path:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, mode="w") as file:
                file.write(astor.to_source(module))
