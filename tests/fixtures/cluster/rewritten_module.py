#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture module with classes and functions whose __module__ has been rewritten."""

from __future__ import annotations


class RewrittenClass:
    """Class whose __module__ is rewritten to simulate libraries like bidict."""

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def get_value(self) -> int:
        """Return the value."""
        return self.value


class RewrittenEmptyClass:
    """Class with no methods whose __module__ is rewritten."""


def rewritten_function(x: int) -> int:
    """Function whose __module__ is rewritten."""
    return x + 1


# Simulate package root rewriting __module__
RewrittenClass.__module__ = "tests.fixtures.cluster.fake_package_root"
RewrittenEmptyClass.__module__ = "tests.fixtures.cluster.fake_package_root"
rewritten_function.__module__ = "tests.fixtures.cluster.fake_package_root"
