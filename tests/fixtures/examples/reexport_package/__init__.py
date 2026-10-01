#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A package that re-exports a class under the name of its defining submodule."""

from __future__ import annotations

from tests.fixtures.examples.reexport_package.widget import widget

__all__ = ["widget"]
