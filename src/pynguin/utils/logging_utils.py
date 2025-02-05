#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility functions for logging."""

import logging


def reset_logging():
    """Resets logging configuration to the default."""
    root_logger = logging.getLogger()

    # Remove all handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Reset logging configuration
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
