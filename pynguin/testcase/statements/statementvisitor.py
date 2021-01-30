#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract statement visitor"""
# pylint: disable=cyclic-import
from __future__ import annotations

from abc import ABC, abstractmethod


class StatementVisitor(ABC):
    """An abstract statement visitor."""

    @abstractmethod
    def visit_int_primitive_statement(self, stmt) -> None:
        """Visit int primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_float_primitive_statement(self, stmt) -> None:
        """Visit float primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_string_primitive_statement(self, stmt) -> None:
        """Visit string primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_bytes_primitive_statement(self, stmt) -> None:
        """Visit bytes primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_boolean_primitive_statement(self, stmt) -> None:
        """Visit boolean primitive.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_none_statement(self, stmt) -> None:
        """Visit none.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_constructor_statement(self, stmt) -> None:
        """Visit constructor.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_method_statement(self, stmt) -> None:
        """Visit method.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_function_statement(self, stmt) -> None:
        """Visit function.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_field_statement(self, stmt) -> None:
        """Visit field.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_assignment_statement(self, stmt) -> None:
        """Visit assignment.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_list_statement(self, stmt) -> None:
        """Visit list.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_set_statement(self, stmt) -> None:
        """Visit set.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_tuple_statement(self, stmt) -> None:
        """Visit tuple.

        Args:
            stmt: the statement to visit
        """

    @abstractmethod
    def visit_dict_statement(self, stmt) -> None:
        """Visit dict.

        Args:
            stmt: the statement to visit
        """
