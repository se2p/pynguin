#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
