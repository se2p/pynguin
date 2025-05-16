#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import numpy as np


def ml_example_api(x, y, z):
    result = 0
    if np.array(x).shape == (2, 2):
        result += 1
    if y == "mean":
        result += 1
    if isinstance(z, int):
        result += 1
    return result


def _tensor_builder(x: np.ndarray):
    # just returns the ndarray
    return x
