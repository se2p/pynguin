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
"""An export implementation creating unittest test cases from the statements."""
import ast
import os
from typing import List, Sequence, Union

import pynguin.testcase.testcase as tc
from pynguin.generation.export.abstractexporter import AbstractTestExporter


# pylint: disable=too-few-public-methods
class UnitTestExporter(AbstractTestExporter):
    """An exporter for UnitTest-style test cases."""

    def export_sequences(
        self, path: Union[str, os.PathLike], test_cases: List[tc.TestCase]
    ):
        asts, module_aliases = self._transform_to_asts(test_cases)
        import_node = AbstractTestExporter._create_ast_imports(
            module_aliases, "unittest"
        )
        functions = AbstractTestExporter._create_functions(asts, True)
        module = ast.Module(
            body=import_node + [UnitTestExporter._create_unit_test_class(functions)]
        )
        AbstractTestExporter._save_ast_to_file(path, module)

    @staticmethod
    def _create_unit_test_class(functions: Sequence[ast.stmt]) -> ast.stmt:
        return ast.ClassDef(
            bases=[
                ast.Attribute(
                    attr="TestCase",
                    ctx=ast.Load(),
                    value=ast.Name(id="unittest", ctx=ast.Load()),
                )
            ],
            name="GeneratedTestSuite",
            body=functions,
            decorator_list=[],
        )
