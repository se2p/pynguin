#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for providing and collecting constants."""

from __future__ import annotations

import abc
import ast
import logging
import os
import string
import typing

from abc import ABC
from pathlib import Path
from pkgutil import iter_modules

from setuptools import find_packages

from pynguin.utils import randomness
from pynguin.utils.orderedset import OrderedSet

# Used for type hinting and for restricting stored types
from pynguin.utils.typetracing import unwrap


if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any
    from typing import ClassVar


ConstantTypes = float | int | str | bytes | complex

# Used for generic type hinting
T = typing.TypeVar("T", float, int, str, bytes, complex)


logger = logging.getLogger(__name__)


class ConstantPool:
    """A pool of constants for various types."""

    def __init__(self):  # noqa: D107
        self._constants: dict[type[ConstantTypes], OrderedSet[ConstantTypes]] = {
            tp_: OrderedSet() for tp_ in typing.get_args(ConstantTypes)
        }

    def add_constant(self, constant: ConstantTypes) -> None:
        """Add new constant value.

        Args:
            constant: The constant to add
        """
        self._constants[type(constant)].add(constant)

    def remove_constant(self, value: ConstantTypes) -> None:
        """Remove the given constant.

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
        """Get a random value from the constant pool.

        Args:
            tp_: The type to retrieve

        Returns:
            A random element of the given type
        """
        return typing.cast("T", randomness.choice(tuple(self._constants[tp_])))

    def get_all_constants_for(self, tp_: type[T]) -> OrderedSet[T]:
        """Get all values from the constant pool.

        Args:
            tp_: The type to retrieve

        Returns:
            All constants of the given type
        """
        return typing.cast("OrderedSet[T]", self._constants[tp_])

    def __len__(self):
        return sum(len(value) for value in self._constants.values())


class RestrictedConstantPool(ConstantPool):
    """A constant pool that is restricted in its size.

    If the size limit is reached, the oldest values are purged.
    """

    def __init__(self, max_size: int = 50):
        """Create a new restricted constant pool.

        Args:
            max_size: The maximum number of collected values per type.
        """
        super().__init__()
        assert max_size > 0, "Size limit for constant pool must be positive."
        self._max_size = max_size

    def add_constant(self, constant: ConstantTypes) -> None:  # noqa: D102
        values = self._constants[type(constant)]
        values.add(constant)
        if len(values) > self._max_size:
            values.remove(values[0])


class ConstantProvider(abc.ABC):
    """Provides constants."""

    @abc.abstractmethod
    def get_constant_for(self, tp_: type[T]) -> T | None:
        """Provide a constant value of the given type.

        Args:
            tp_: The type to retrieve

        Returns:
            A constant or None, if there is no constant  # noqa: DAR202
        """


class EmptyConstantProvider(ConstantProvider):
    """Empty provider."""

    def get_constant_for(self, tp_: type[T]) -> T | None:  # noqa: D102
        return None


class DelegatingConstantProvider(ConstantProvider, ABC):
    """Either provides values from its own pool or delegates to another provider."""

    def __init__(self, pool: ConstantPool, delegate: ConstantProvider, probability: float):
        """Create a new provider.

        Args:
            pool: The pool of constants to use
            delegate: The delegate to forward the query
            probability: The probability to use a value from this provider,
                if there is one.
        """
        self._pool = pool
        self._delegate = delegate
        self._probability = probability

    def get_constant_for(self, tp_: type[T]) -> T | None:  # noqa: D102
        if self._pool.has_constant_for(tp_) and randomness.next_float() < self._probability:
            return self._pool.get_constant_for(tp_)
        return self._delegate.get_constant_for(tp_)


class DynamicConstantProvider(DelegatingConstantProvider):
    """Provide values collected during runtime."""

    def __init__(
        self,
        pool: ConstantPool,
        delegate: ConstantProvider,
        probability: float,
        max_constant_length: int,
    ):
        """Create a new dynamic constant provider.

        Args:
            pool: The pool of constants to use
            delegate: The delegate to forward the query
            probability: The probability to use a value from this provider,
                if there is one.
            max_constant_length: The maximum length of strings to store.
        """
        super().__init__(pool, delegate, probability)
        assert max_constant_length > 0, "Length limit for constant pool elements must be positive."
        self._max_constant_length = max_constant_length

    # A map containing the names of all string functions which are instrumented.
    # Maps those names to a function producing a value that negates the functions
    # result.
    STRING_FUNCTION_LOOKUP: ClassVar[dict[str, Callable[[Any], str]]] = {
        "isalnum": lambda value: f"{value}!" if value.isalnum() else "isalnum",
        "islower": lambda value: value.upper() if value.islower() else value.lower(),
        "isupper": lambda value: value.lower() if value.isupper() else value.upper(),
        "isdecimal": lambda value: ("non_decimal" if value.isdecimal() else string.digits),
        "isalpha": lambda value: f"{value}1" if value.isalpha() else "isalpha",
        "isdigit": lambda value: f"{value}_" if value.isdigit() else "0",
        "isidentifier": lambda value: (f"{value}!" if value.isidentifier() else "is_Identifier"),
        "isnumeric": lambda value: f"{value}A" if value.isnumeric() else "012345",
        "isprintable": lambda value: (
            f"{value}{os.linesep}" if value.isprintable() else "is_printable"
        ),
        "isspace": lambda value: f"{value}a" if value.isspace() else "   ",
        "istitle": lambda value: f"{value} AAA" if value.istitle() else "Is Title",
    }

    def add_value(self, value: ConstantTypes) -> None:
        """Entry point for the instrumented code.

        Args:
            value: The observed
        """
        # Might be a proxy.
        value = unwrap(value)
        if type(value) in typing.get_args(ConstantTypes):
            if isinstance(value, str | bytes) and len(value) > self._max_constant_length:
                return
            self._pool.add_constant(value)

    def add_value_for_strings(self, value: str, name: str):
        """Entry point for the instrumented code. Add a value of a string.

        Args:
            value: The value
            name: The string
        """
        # Might be a proxy.
        value = unwrap(value)
        if isinstance(value, str) and name in self.STRING_FUNCTION_LOOKUP:
            self.add_value(value)
            self.add_value(self.STRING_FUNCTION_LOOKUP[name](value))


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
    path = Path(project_path).resolve()
    for module in _find_modules_with_constants(project_path):
        module_path = path / module
        with module_path.open(mode="r", encoding="utf-8") as module_file:
            try:
                tree = ast.parse(module_file.read())
                collector.visit(tree)
            except BaseException as exception:  # noqa: BLE001
                logger.warning(
                    "Could not collect constants from %s. Skipping constant collection (%s).",
                    module,
                    exception,
                )
    return collector.constants


class _ConstantCollector(ast.NodeVisitor):
    """AST visitor that collects constants."""

    def __init__(self) -> None:
        self._pool = ConstantPool()
        self._string_expressions: OrderedSet[str] = OrderedSet()

    def visit_Constant(self, node: ast.Constant):  # noqa: N802
        if type(node.value) in typing.get_args(ConstantTypes):
            self._pool.add_constant(node.value)
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module):  # noqa: N802
        return self._visit_doc_string(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):  # noqa: N802
        return self._visit_doc_string(node)

    def visit_ClassDef(self, node: ast.ClassDef):  # noqa: N802
        return self._visit_doc_string(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # noqa: N802
        return self._visit_doc_string(node)

    def _visit_doc_string(
        self, node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module
    ):
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


class MLConstantPool:
    """Manages a dictionary of constants for ML-specific testing."""

    def __init__(self):  # noqa: D107
        self._pool: dict[str, int] = {}

    def add(self, key: str, value: int) -> None:
        """Adds a key-value pair to the constant pool."""
        self._pool[key] = value

    def reset(self) -> None:
        """Clears the constant pool."""
        self._pool.clear()

    def get_value(self, key: str, default: int | None = None) -> int | None:
        """Retrieves the value for a given key, or returns the default if not found."""
        return self._pool.get(key, default)
