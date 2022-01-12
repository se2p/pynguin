#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""An exported implementation creating PyTest test cases from the statements."""
from __future__ import annotations

import ast
import os
from typing import TYPE_CHECKING

from pynguin.generation.export.abstractexporter import AbstractTestExporter

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc


# pylint: disable=too-few-public-methods
class PyTestExporter(AbstractTestExporter):
    """An exporter for PyTest-style test cases."""

    def export_sequences(self, path: str | os.PathLike, test_cases: list[tc.TestCase]):
        (
            module_aliases,
            common_modules,
            asts,
        ) = self._transform_to_asts(test_cases)
        import_nodes = AbstractTestExporter._create_ast_imports(
            module_aliases, common_modules
        )
        functions = AbstractTestExporter._create_functions(asts, False)
        module = ast.Module(body=import_nodes + functions)
        AbstractTestExporter._save_ast_to_file(path, module)
