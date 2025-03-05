#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import numpy as np


def ml_example_api(x, y, z):
    result = 0
    if _is_valid_tensor_shape(x, 2, (2, 2), "int32"):
        result += 1
    if _is_valid_tensor_shape(y, 2, (3, 3), "float32"):
        result += 1
    if _is_valid_tensor_shape(z, 3, (1, 1, 1), "int64"):
        result += 1
    return result


def _is_valid_tensor_shape(
    array: np.ndarray,
    expected_dim: int,
    expected_shape: tuple,
    expected_dtype: str
):
    return (
        array.ndim == expected_dim
        and array.shape == expected_shape
        and array.dtype.name == expected_dtype
    )


def _tensor_builder(x: np.ndarray):
    # just returns the ndarray
    return x
