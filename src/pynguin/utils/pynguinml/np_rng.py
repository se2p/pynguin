#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a singleton instance of np.random.Generator."""

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


if not NUMPY_AVAILABLE:
    raise ImportError(
        "NumPy is not available. You can install it with poetry install --with numpy."
    )


NP_RNG: np.random.Generator | None = None


def init_rng(seed: int) -> None:
    """Initialize the numpy random number generator with a seed.

    Args:
        seed: The seed to use for the random number generator.
    """
    global NP_RNG  # noqa: PLW0603
    NP_RNG = np.random.default_rng(seed)


def get_rng() -> np.random.Generator:
    """Get the singleton np.random.Generator instance.

    Returns:
        The singleton np.random.Generator.
    """
    assert NP_RNG is not None, "RNG not initialized. Call init_rng first."
    return NP_RNG
