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
"""An exported implementation creating PyTest test cases from the statements."""
import ast
import os
from typing import List, Union

from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.utils.statements import Sequence


class PyTestExporter(AbstractTestExporter):
    """An exporter for PyTest-style test cases."""

    def __init__(
        self, module_names: List[str], path: Union[str, os.PathLike] = ""
    ) -> None:
        super().__init__(path)
        self._module_names = module_names

    def export_sequences(self, sequences: List[Sequence]) -> ast.Module:
        """Exports a list of sequences to files.

        :param sequences:
        :return:
        """
        import_node = self._create_ast_imports()
        functions = self._create_functions(sequences)
        module = ast.Module(body=[import_node] + functions)  # type: ignore
        if self._path:
            self.save_ast_to_file(module)
        return module

    def _create_ast_imports(self) -> ast.Import:
        imports = set()
        for module in self._module_names:
            alias_node = ast.alias(name=module, asname=None)
            imports.add(alias_node)
        import_node = ast.Import(names=imports)
        return import_node

    def _create_functions(self, sequences: List[Sequence]) -> List[ast.FunctionDef]:
        functions: List[ast.FunctionDef] = []
        for i, sequence in enumerate(sequences):
            nodes = self._create_statement_nodes(sequence)
            function_name = f"case_{i}"
            function_node = self._create_function_node(function_name, nodes)
            functions.append(function_node)
        return functions

    @staticmethod
    def _create_statement_nodes(sequence: Sequence) -> List[ast.AST]:
        pass
        # statements: List[ast.AST] = []
        # export_visitor = _PyTestExportStatementVisitor()
        # for statement in sequence:
        #     nodes = statement.accept(export_visitor)
        #     statements.append(nodes)
        # return statements

    @staticmethod
    def _create_function_node(
        function_name: str, nodes: List[ast.AST]
    ) -> ast.FunctionDef:
        function_node = ast.FunctionDef(
            name=f"test_{function_name}",
            args=ast.arguments(
                args=[],
                defaults=[],
                vararg=None,
                kwarg=None,
                kwonlyargs=[],
                kw_defaults=[],
            ),
            body=nodes,
            decorator_list=[],
            returns=None,
        )
        return function_node
