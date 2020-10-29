#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an assertion visitor."""
from abc import abstractmethod


class AssertionVisitor:
    """Abstract visitor for assertions."""

    @abstractmethod
    def visit_primitive_assertion(self, assertion) -> None:
        """Visit a primitive assertion.

        Args:
            assertion: the visited assertion

        """

    @abstractmethod
    def visit_none_assertion(self, assertion) -> None:
        """Visit a none assertion.

        Args:
            assertion: the visited assertion

        """
