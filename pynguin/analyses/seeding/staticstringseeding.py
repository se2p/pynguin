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
"""Implements a simple static string seeding strategy."""
from __future__ import annotations
import ast
import os
from pkgutil import iter_modules
from typing import Union, Set, Optional

from setuptools import find_packages

from pynguin.utils import randomness


class StaticStringSeeding:
    """A simple static string seeding strategy.

    Extracts all strings from a set of modules by using an AST visitor.
    """

    _instance: Optional[StaticStringSeeding] = None
    _strings: Optional[Set[str]] = None

    def __new__(cls) -> StaticStringSeeding:
        if cls._instance is None:
            cls._instance = super(StaticStringSeeding, cls).__new__(cls)
            cls._strings = set()
        return cls._instance

    @staticmethod
    def _find_modules(project_path: Union[str, os.PathLike]) -> Set[str]:
        modules: Set[str] = set()
        for package in find_packages(
            project_path,
            exclude=[
                "*.tests",
                "*.tests.*",
                "tests.*",
                "tests",
                "test",
                "test.*",
                "*.test.*",
                "*.test",
            ],
        ):
            pkg_path = "{}/{}".format(project_path, package.replace(".", "/"))
            for info in iter_modules([pkg_path]):
                if not info.ispkg:
                    modules.add(f"{package}/{info.name}.py")
        return modules

    def collect_strings(self, project_path: Union[str, os.PathLike]) -> Set[str]:
        """Collect all strings for a given project.

        :param project_path: The path to the project's root
        :return: A set of all collected strings
        """
        assert self._strings is not None
        collector = _StringCollector()
        for module in self._find_modules(project_path):
            with open(os.path.join(project_path, module)) as module_file:
                tree = ast.parse(module_file.read())
                collector.visit(tree)
        self._strings = collector.strings
        return self._strings

    @property
    def has_strings(self) -> bool:
        """Whether or not we have some strings collected."""
        assert self._strings is not None
        return len(self._strings) > 0

    @property
    def random_string(self) -> str:
        """Provides a random string from the set of collected strings."""
        assert self._strings is not None
        return randomness.choice(tuple(self._strings))


class _StringCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self._strings: Set[str] = set()

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._strings.add(node.value)

    @property
    def strings(self) -> Set[str]:
        """Provides the collected strings."""
        return self._strings
