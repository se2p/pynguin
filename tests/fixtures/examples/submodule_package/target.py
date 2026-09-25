#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

from tests.fixtures.examples.submodule_package import helper


def target_function() -> int:
    """A target function for testing."""
    return helper.helper_function()
