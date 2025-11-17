#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a chromosome visitor."""

from abc import ABC, abstractmethod


class ChromosomeVisitor(ABC):
    """An abstract chromosome visitor."""

    @abstractmethod
    def visit_test_suite_chromosome(self, chromosome) -> None:
        """Visit a test suite chromosome.

        Args:
            chromosome: The test suite chromosome
        """

    @abstractmethod
    def visit_test_case_chromosome(self, chromosome) -> None:
        """Visit a test suite chromosome.

        Args:
            chromosome: The test case chromosome
        """
