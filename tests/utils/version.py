#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import sys

import pytest


def only_3_10(func):
    """Decorator to skip tests if the Python version is not 3.10."""
    return pytest.mark.skipif(sys.version_info[:2] != (3, 10), reason="Test requires Python 3.10")(
        func
    )
