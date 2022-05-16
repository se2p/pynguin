#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides classes for providing and collecting constants"""

from __future__ import annotations

import abc
import ast
import dataclasses
import logging
import os
import typing
from abc import ABC
from pathlib import Path
from pkgutil import iter_modules

from ordered_set import OrderedSet
from setuptools import find_packages

from pynguin.utils import randomness

# Used for type hinting and for restricting stored types
ConstantTypes = float | int | str | bytes

# Used for generic type hinting
T = typing.TypeVar("T", float, int, str, bytes)


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ConstantPool:
    """A pool of constants for various types."""

    def __init__(self):
        self._constants: dict[type[ConstantTypes], OrderedSet[ConstantTypes]] = {
            tp_: OrderedSet() for tp_ in typing.get_args(ConstantTypes)
        }

    def add_constant(self, constant: ConstantTypes) -> None:
        """Add new constant value

        Args:
            constant: The constant to add
        """
        self._constants[type(constant)].add(constant)

    def remove_constant(self, value: ConstantTypes) -> None:
        """Remove the given constant

        Args:
            value: the constant to remove
        """
        values = self._constants.get(type(value))
        assert values is not None
        values.discard(value)

    def has_constant_for(self, tp_: type[T]) -> bool:
        """Does this pool have a constant of the given type?

        Args:
            tp_: The queried type

        Returns:
            True, if there is a constant
        """
        return len(self._constants[tp_]) > 0

    def get_constant_for(self, tp_: type[T]) -> T:
        """Get a random value from the constant pool

        Args:
            tp_: The type to retrieve

        Returns:
            A random element of the given type
        """
        return typing.cast(T, randomness.choice(tuple(self._constants[tp_])))

    def get_all_constants_for(self, tp_: type[T]) -> OrderedSet[T]:
        """Get all values from the constant pool

        Args:
            tp_: The type to retrieve

        Returns:
            All constants of the given type
        """
        return typing.cast(OrderedSet[T], self._constants[tp_])

    def __len__(self):
        return sum(len(value) for value in self._constants.values())


class ConstantProvider(abc.ABC):  # pylint:disable=too-few-public-methods
    """Provides constants"""

    @abc.abstractmethod
    def get_constant_for(self, tp_: type[T]) -> T | None:
        """Provide a constant value of the given type.

        Args:
            tp_: The type to retrieve

        Returns:
            A constant or None, if there is no constant  # noqa: DAR202
        """


class EmptyConstantProvider(ConstantProvider):  # pylint:disable=too-few-public-methods
    """Empty provider"""

    def get_constant_for(self, tp_: type[T]) -> T | None:
        return None


class DelegatingConstantProvider(
    ConstantProvider, ABC
):  # pylint:disable=too-few-public-methods
    """Either provides values from its own pool or delegates to another provider."""

    def __init__(
        self, pool: ConstantPool, delegate: ConstantProvider, probability: float
    ):
        """Create a new provider

        Args:
            pool: The pool of constants to use
            delegate: The delegate to forward the query
            probability: The probability to use a value from this provider,
                if there is one.
        """
        self._pool = pool
        self._delegate = delegate
        self._probability = probability

    def get_constant_for(self, tp_: type[T]) -> T | None:
        if (
            self._pool.has_constant_for(tp_)
            and randomness.next_float() < self._probability
        ):
            return self._pool.get_constant_for(tp_)
        return self._delegate.get_constant_for(tp_)


class DynamicConstantProvider(DelegatingConstantProvider):
    """Provide values collected during runtime."""

    # A map containing the names of all string functions which are instrumented.
    # Maps those names to a function producing a value that negates the functions
    # result.
    STRING_FUNCTION_LOOKUP = {
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

    def add_value(self, value: ConstantTypes) -> None:
        """Entry point for the instrumented code.

        Args:
            value: The observed
        """
        if type(value) in typing.get_args(ConstantTypes):
            self._pool.add_constant(value)

    def add_value_for_strings(self, value: str, name: str):
        """Entry point for the instrumented code. Add a value of a string.

        Args:
            value: The value
            name: The string
        """
        if type(value) is str:  # pylint:disable=unidiomatic-typecheck
            self._pool.add_constant(value)
            self._pool.add_constant(self.STRING_FUNCTION_LOOKUP[name](value))


def _find_modules_with_constants(project_path: str | os.PathLike) -> OrderedSet[str]:
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


def collect_static_constants(project_path: str | os.PathLike) -> ConstantPool:
    """Collect all constants for a given project.

    Args:
        project_path: The path to the project's root

    Returns:
        A dict of type to set of constants
    """
    collector = _ConstantCollector()
    for module in _find_modules_with_constants(project_path):
        with open(os.path.join(project_path, module), encoding="utf-8") as module_file:
            try:
                tree = ast.parse(module_file.read())
                collector.visit(tree)
            except BaseException as exception:  # pylint: disable=broad-except
                logger.exception("Cannot collect constants: %s", exception)
    return collector.constants


# pylint: disable=invalid-name, missing-function-docstring
class _ConstantCollector(ast.NodeVisitor):
    """AST visitor that collects constants"""

    def __init__(self) -> None:
        self._pool = ConstantPool()
        self._string_expressions: OrderedSet[str] = OrderedSet()

    def visit_Constant(self, node: ast.Constant):
        if type(node.value) in typing.get_args(ConstantTypes):
            self._pool.add_constant(node.value)
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module):
        return self._visit_doc_string(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return self._visit_doc_string(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        return self._visit_doc_string(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return self._visit_doc_string(node)

    def _visit_doc_string(self, node: ast.AST):
        if docstring := ast.get_docstring(node):
            self._string_expressions.add(docstring)
        return self.generic_visit(node)

    @property
    def constants(self) -> ConstantPool:
        """Provides the collected constants.

        Returns:
            The collected constants
        """
        for doc in self._string_expressions:
            self._pool.remove_constant(doc)
        return self._pool
