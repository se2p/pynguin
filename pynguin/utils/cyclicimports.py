#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Small utility to find cyclic imports."""

import ast
import pathlib

import networkx as nx
from networkx import simple_cycles


class ImportVisitor(ast.NodeVisitor):
    """A visitor that collects all imports that match a prefix."""

    def __init__(self, root_dir: pathlib.Path, prefixes: list[str]):
        """Create new import visitor

        Args:
            root_dir: The root directory of the modules
            prefixes: The prefixes to search
        """
        self._imports: set[str] = set()
        self._root_dir = root_dir
        self._prefixes = prefixes

    def get_imports(self) -> set[str]:
        """Provides the found imports

        Returns:
            A set of imports
        """
        return self._imports

    def is_package_import(self, module: str) -> bool:
        """Check if the given module is an import of a package

        Args:
            module: The module to check

        Returns:
            True, if the given module is a directory.
        """
        return (self._root_dir / pathlib.Path(*module.split("."))).is_dir()

    def visit_Import(self, node: ast.Import):  # pylint:disable=invalid-name
        """Visit 'import x as y'

        Args:
            node: the ast node
        """
        for name in node.names:
            if not name.name.startswith(tuple(self._prefixes)):
                continue
            self._imports.add(name.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):  # pylint:disable=invalid-name
        """Visit 'from x import y'

        Args:
            node: the ast node
        """
        if not node.module or not node.module.startswith(tuple(self._prefixes)):
            return

        for name in node.names:
            # Distinguish
            # from pynguin.testcase import testcase
            #   -> imports pynguin.testcase.testcase
            # and
            # from pynguin.testcase.statement import StatementVisitor
            #   -> imports pynguin.testcase.statement
            if self.is_package_import(node.module):
                self._imports.add(node.module + "." + name.name)
            else:
                # from foo import bar
                self._imports.add(node.module)

    def visit_If(self, node: ast.If):  # pylint:disable=invalid-name
        """Visit if to skip conditional imports

        Args:
            node: the ast node
        """
        # Do not follow conditional imports from root


def find_cyclic_imports(root_dir: pathlib.Path, prefixes: list[str]) -> list:
    """Finds cyclic imports starting from the given root dir.
    Only considers imports from/to modules that match one of the given prefixes.

    Args:
        root_dir: The directory to start the search
        prefixes: The allowed prefixes of module that should be considered.

    Returns:
        A list of cycles
    """
    import_graph = nx.DiGraph()

    for prefix in prefixes:
        for module in (root_dir / pathlib.Path(prefix)).rglob("*.py"):
            if module.name == "__init__.py":
                # Skip those, as we don't use them.
                continue

            module_name = ".".join(module.relative_to(root_dir).parts).replace(
                ".py", ""
            )
            import_graph.add_node(module_name)

            parsed = ast.parse(module.read_text(encoding="UTF-8"))
            visitor = ImportVisitor(root_dir, prefixes)
            visitor.visit(parsed)
            for imported_module in visitor.get_imports():
                import_graph.add_node(imported_module)
                import_graph.add_edge(module_name, imported_module)

    # (root_dir / "import_graph.dot").write_text(to_pydot(import_graph).to_string(),
    # encoding="UTF-8")
    return list(simple_cycles(import_graph))
