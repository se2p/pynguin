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
"""Implements a simple static constant seeding strategy."""
from __future__ import annotations

import ast
import os
from pkgutil import iter_modules
from typing import Union, Set, Optional, Dict, cast

from setuptools import find_packages

from pynguin.utils import randomness

Types = Union[float, int, str]


class StaticConstantSeeding:
    """A simple static constant seeding strategy.

    Extracts all constants from a set of modules by using an AST visitor.
    """

    _instance: Optional[StaticConstantSeeding] = None
    _constants: Optional[Dict[str, Set[Types]]] = None

    def __new__(cls) -> StaticConstantSeeding:
        if cls._instance is None:
            cls._instance = super(StaticConstantSeeding, cls).__new__(cls)
            cls._constants = {}
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

    def collect_constants(
        self, project_path: Union[str, os.PathLike]
    ) -> Dict[str, Set[Types]]:
        """Collect all constants for a given project.

        :param project_path: The path to the project's root
        :return: A dict of type to set of constants
        """
        assert self._constants is not None
        collector = _ConstantCollector()
        for module in self._find_modules(project_path):
            with open(os.path.join(project_path, module)) as module_file:
                tree = ast.parse(module_file.read())
                collector.visit(tree)
        self._constants = collector.constants
        return self._constants

    @property
    def has_strings(self) -> bool:
        """Whether or not we have some strings collected."""
        return self._has_constants("str")

    @property
    def has_ints(self) -> bool:
        """Whether or not we have some ints collected."""
        return self._has_constants("int")

    @property
    def has_floats(self) -> bool:
        """Whether or not we have some floats collected."""
        return self._has_constants("float")

    def _has_constants(self, type_: str) -> bool:
        assert self._constants is not None
        return len(self._constants[type_]) > 0

    @property
    def random_string(self) -> str:
        """Provides a random string from the set of collected strings."""
        return cast(str, self._random_element("str"))

    @property
    def random_int(self) -> int:
        """Provides a random int from the set of collected ints."""
        return cast(int, self._random_element("int"))

    @property
    def random_float(self) -> float:
        """Provides a random float from the set of collected floats."""
        return cast(float, self._random_element("float"))

    def _random_element(self, type_: str) -> Types:
        assert self._constants is not None
        return randomness.choice(tuple(self._constants[type_]))


class _ConstantCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self._constants: Dict[str, Set[Types]] = {
            "float": set(),
            "int": set(),
            "str": set(),
        }

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._constants["str"].add(node.value)
        elif isinstance(node.value, float):
            self._constants["float"].add(node.value)
        elif isinstance(node.value, int):
            self._constants["int"].add(node.value)

    @property
    def constants(self) -> Dict[str, Set[Types]]:
        """Provides the collected constants."""
        return self._constants
