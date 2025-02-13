#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pynguin is an automated unit test generation framework for Python.

This module provides the main entry location for the program executions.
"""

import sys

from pynguin.cli import main


if __name__ == "__main__":
    sys.exit(main(sys.argv))
