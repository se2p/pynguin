#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a singleton instance of np.random.Generator."""

import numpy as np


NP_RNG: np.random.Generator | None = None


def get_rng() -> np.random.Generator:
    """Get the singleton np.random.Generator instance.

    Returns:
        The singleton np.random.Generator.
    """
    assert NP_RNG is not None
    return NP_RNG
