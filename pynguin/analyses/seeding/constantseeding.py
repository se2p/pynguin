#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements simple constant seeding strategies."""
from __future__ import annotations

import ast
import logging
import os
from abc import abstractmethod
from pathlib import Path
from pkgutil import iter_modules
from typing import Any, Union, cast

from _py_abc import ABCMeta
from ordered_set import OrderedSet
from setuptools import find_packages

from pynguin.utils import randomness

Types = Union[float, int, str]


class _ConstantSeeding(metaclass=ABCMeta):
    """An abstract base class for constant seeding strategies."""

    _logger = logging.getLogger(__name__)

    @property
    def has_strings(self) -> bool:
        """Whether or not we have some strings collected.

        Returns:
            Whether or not we have some strings collected
        """
        return self.has_constants(str)

    @property
    def has_ints(self) -> bool:
        """Whether or not we have some ints collected.

        Returns:
            Whether or not we have some ints collected
        """
        return self.has_constants(int)

    @property
    def has_floats(self) -> bool:
        """Whether or not we have some floats collected.

        Returns:
            Whether or not we have some floats collected
        """
        return self.has_constants(float)

    @abstractmethod
    def has_constants(self, type_: type[Types]) -> bool:
        """Returns whether a constant of a given type exists in the pool.

        Args:
            type_: The type of the constant

        Returns:
            Whether or not a constant of the given type exists  # noqa: DAR202
        """

    @property
    def random_string(self) -> str:
        """Provides a random string from the set of collected strings.

        Returns:
            A random string
        """
        return cast(str, self.random_element(str))

    @property
    def random_int(self) -> int:
        """Provides a random int from the set of collected ints.

        Returns:
            A random int
        """
        return cast(int, self.random_element(int))

    @property
    def random_float(self) -> float:
        """Provides a random float from the set of collected floats.

        Returns:
            A random float
        """
        return cast(float, self.random_element(float))

    @abstractmethod
    def random_element(self, type_: type[Types]) -> Types:
        """Provides a random element of the given type

        Args:
            type_: The given type

        Returns:
            A random element of the given type
        """


class _StaticConstantSeeding(_ConstantSeeding):
    """A simple static constant seeding strategy.

    Extracts all constants from a set of modules by using an AST visitor.
    """

    def __init__(self) -> None:
        self._constants: dict[type[Types], OrderedSet[Types]] = {
            int: OrderedSet(),
            float: OrderedSet(),
            str: OrderedSet(),
        }

    @staticmethod
    def _find_modules(project_path: str | os.PathLike) -> OrderedSet[str]:
        modules: OrderedSet[str] = OrderedSet()
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
            package_name = package.replace(".", "/")
            pkg_path = f"{project_path}/{package_name}"
            for info in iter_modules([pkg_path]):
                if not info.ispkg:
                    name = info.name.replace(".", "/")
                    module = f"{package_name}/{name}.py"
                    module_path = Path(project_path) / Path(module)
                    if module_path.exists() and module_path.is_file():
                        # Consider only Python files for constant seeding, as the
                        # seeding relies on the availability of an AST.
                        modules.add(module)
        return modules

    def collect_constants(
        self, project_path: str | os.PathLike
    ) -> dict[type[Types], OrderedSet[Types]]:
        """Collect all constants for a given project.

        Args:
            project_path: The path to the project's root

        Returns:
            A dict of type to set of constants
        """
        assert self._constants is not None
        collector = _ConstantCollector()
        for module in self._find_modules(project_path):
            with open(
                os.path.join(project_path, module), encoding="utf-8"
            ) as module_file:
                try:
                    tree = ast.parse(module_file.read())
                    collector.visit(tree)
                except BaseException as exception:  # pylint: disable=broad-except
                    self._logger.exception("Cannot collect constants: %s", exception)
        self._constants = collector.constants
        return self._constants

    def has_constants(self, type_: type[Types]) -> bool:
        assert self._constants is not None
        return len(self._constants[type_]) > 0

    def random_element(self, type_: type[Types]) -> Types:
        assert self._constants is not None
        return randomness.choice(tuple(self._constants[type_]))


# pylint: disable=invalid-name, missing-function-docstring
class _ConstantCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self._constants: dict[type[Types], OrderedSet[Types]] = {
            float: OrderedSet(),
            int: OrderedSet(),
            str: OrderedSet(),
        }
        self._string_expressions: OrderedSet[str] = OrderedSet()

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, str):
            self._constants[str].add(node.value)
        elif isinstance(node.value, float):
            self._constants[float].add(node.value)
        elif isinstance(node.value, int):
            self._constants[int].add(node.value)
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> Any:
        return self._visit_doc_string(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        return self._visit_doc_string(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        return self._visit_doc_string(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return self._visit_doc_string(node)

    def _visit_doc_string(self, node: ast.AST) -> Any:
        if docstring := ast.get_docstring(node):
            self._string_expressions.add(docstring)
        return self.generic_visit(node)

    @property
    def constants(self) -> dict[type[Types], OrderedSet[Types]]:
        """Provides the collected constants.

        Returns:
            The collected constants
        """
        self._remove_docstrings()
        return self._constants

    def _remove_docstrings(self) -> None:
        self._constants[str] -= self._string_expressions


class DynamicConstantSeeding(_ConstantSeeding):
    """Provides a dynamic pool and methods to add and retrieve values.

    The methods in this class are added to the module under test during an instruction
    phase before the main algorithm is executed. During this instruction phase,
    bytecode is added to the module under test which executes the methods adding
    values to the dynamic pool. The instrumentation is implemented in the module
    dynamicseedinginstrumentation.py.

    During the test generation process when a new value of one of the supported types
    is needed, this module provides methods to get values from the dynamic pool
    instead of randomly generating a new one.
    """

    _string_functions_lookup = {
        "isalnum": lambda value: f"{value}!" if value.isalnum() else "isalnum",
        "islower": lambda value: value.upper() if value.islower() else value.lower(),
        "isupper": lambda value: value.lower() if value.isupper() else value.upper(),
        "isdecimal": lambda value: "non_decimal" if value.isdecimal() else "0123456789",
        "isalpha": lambda value: f"{value}1" if value.isalpha() else "isalpha",
        "isdigit": lambda value: f"{value}_" if value.isdigit() else "0",
        "isidentifier": lambda value: f"{value}!"
        if value.isidentifier()
        else "is_Identifier",
        "isnumeric": lambda value: f"{value}A" if value.isnumeric() else "012345",
        "isprintable": lambda value: f"{value}{os.linesep}"
        if value.isprintable()
        else "is_printable",
        "isspace": lambda value: f"{value}a" if value.isspace() else "   ",
        "istitle": lambda value: f"{value} AAA" if value.istitle() else "Is Title",
    }

    def __init__(self):
        self._dynamic_pool: dict[type[Types], OrderedSet[Types]] = {
            int: OrderedSet(),
            float: OrderedSet(),
            str: OrderedSet(),
        }

    def reset(self) -> None:
        """Delete all currently stored dynamic constants"""
        for elem in self._dynamic_pool.values():
            elem.clear()

    def has_constants(self, type_: type[Types]) -> bool:
        assert type_ in self._dynamic_pool
        return len(self._dynamic_pool[type_]) > 0

    def random_element(self, type_: type[Types]) -> Types:
        return randomness.choice(tuple(self._dynamic_pool[type_]))

    def add_value(self, value: Types):
        """Adds the given value to the corresponding set of the dynamic pool.

        Args:
            value: The value to add.
        """
        if isinstance(
            value, bool
        ):  # needed because True and False are accepted as ints otherwise
            return
        if type(value) in self._dynamic_pool:
            self._dynamic_pool[type(value)].add(value)

    def add_value_for_strings(self, value: str, name: str):
        """Add a value of a string.

        Args:
            value: The value
            name: The string
        """
        if not isinstance(value, str):
            return
        self._dynamic_pool[str].add(value)
        self._dynamic_pool[str].add(self._string_functions_lookup[name](value))


static_constant_seeding = _StaticConstantSeeding()
dynamic_constant_seeding = DynamicConstantSeeding()
