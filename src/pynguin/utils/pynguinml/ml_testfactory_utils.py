#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides utility functions for ML-specific test generation."""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, cast

import pynguin.configuration as config

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if not NUMPY_AVAILABLE:
    raise ImportError(
        "NumPy is not available. You can install it with poetry install --with numpy."
    )

import pynguin.testcase.statement as stmt
import pynguin.utils.pynguinml.ml_parsing_utils as mlpu
from pynguin.analyses.constants import MLConstantPool
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.pynguinml.np_rng import get_rng

if TYPE_CHECKING:
    from pynguin.analyses.typesystem import ProperType
    from pynguin.utils.pynguinml.mlparameter import MLParameter


LOGGER = logging.getLogger(__name__)

# Shapes or ndims can have dependencies where two parameters should have the same
# value. We simply store them here.
ml_constant_pool: MLConstantPool = MLConstantPool()


def select_dtype(parameter_obj: MLParameter) -> str:
    """Randomly select a dtype for the parameter.

    If the chosen dtype depends on another parameter (indicated by 'dtype:'),
    resolve the dependency and return its dtype name.

    Args:
        parameter_obj: The parameter object

    Returns:
        str: The selected dtype as a string.
    """
    # If it must be a tensor, exclude "str" datatype
    filtered_dtypes = [
        dtype
        for dtype in parameter_obj.valid_dtypes
        if not (parameter_obj.tensor_expected and dtype == "str")
    ]

    if not filtered_dtypes:
        return "None"

    picked_dtype = randomness.choice(filtered_dtypes)

    if "dtype:" in picked_dtype:
        # depends on another param
        _, ref, _ = mlpu.parse_var_dependency(picked_dtype, "dtype:")

        # generate value from dependency param
        dependency_obj = parameter_obj.parameter_dependencies[ref]

        if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):
            picked_dtype = cast("np.ndarray", dependency_obj.current_data).dtype.name
        else:
            picked_dtype = type(dependency_obj.current_data).__name__

    return picked_dtype


def select_ndim(parameter_obj: MLParameter, selected_dtype: str) -> int:
    """Randomly select a dimension for the given parameter.

    If valid ndims are defined in the parameter, one is randomly chosen. For ndim
    constraints that reference another parameter (indicated by 'ndim:'), the
    dependency is resolved to obtain the ndim. If no valid ndims are specified, a
    default value is used.

    Returns:
        int: The selected number of dimensions.

    Raises:
        ConstructionFailedException: If a dependency cannot be resolved.
    """
    # Always return 0 for str
    if "str" in selected_dtype:
        return 0

    if parameter_obj.valid_ndims:
        selected_ndim = randomness.choice(parameter_obj.valid_ndims)
        if selected_ndim.isnumeric():
            return int(selected_ndim)

        if "ndim:" in selected_ndim:
            return _resolve_ndim_dependency_for_ndim(parameter_obj, selected_ndim)

        _, ref, is_var = mlpu.parse_var_dependency(selected_ndim, "")
        if is_var:
            return _resolve_value_dependency_for_ndim(parameter_obj, ref)

        if ml_constant_pool.get_value(ref) is None:
            value = randomness.next_int(0, config.configuration.pynguinml.max_ndim + 1)
            ml_constant_pool.add(ref, value)

        return ml_constant_pool.get_value(ref)  # type: ignore[return-value]

    valid_ndim_values = mlpu.ndim_values()

    return randomness.choice(valid_ndim_values)


def _resolve_ndim_dependency_for_ndim(parameter_obj: MLParameter, selected_ndim: str) -> int:
    _, ref, _ = mlpu.parse_var_dependency(selected_ndim, "ndim:")
    dependency_obj = parameter_obj.parameter_dependencies[ref]

    if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):
        return cast("np.ndarray", dependency_obj.current_data).ndim

    if np.isscalar(dependency_obj.current_data):
        return 0

    raise ConstructionFailedException(f"Unable to get ndim of {ref}.")


def _resolve_value_dependency_for_ndim(parameter_obj: MLParameter, ref: str) -> int:
    dependency_obj = parameter_obj.parameter_dependencies[ref]
    value = dependency_obj.current_data
    if isinstance(value, (bool, np.bool_)):
        raise ConstructionFailedException(
            f"Referred value {ref} is a boolean value. Cannot be used to decide another var."
        )
    if not isinstance(value, (int, float)):
        raise ConstructionFailedException(
            f"Referred value {ref} is not a single numeric value. "
            f"Cannot be used to decide another var."
        )
    return int(value)


def generate_shape(parameter_obj: MLParameter, selected_ndim: int) -> list:
    """Generate a shape based on the parameter's shape constraints and the selected ndim.

    Args:
        parameter_obj: The parameter object.
        selected_ndim: The selected dimension.

    Returns:
        list: The generated shape.
    """
    random_shape = [
        randomness.next_int(0, config.configuration.pynguinml.max_shape_dim + 1)
        for _ in range(selected_ndim)
    ]

    if not parameter_obj.valid_shapes:
        return random_shape

    shape_constraints = _select_shape_constraint(parameter_obj, selected_ndim)

    if shape_constraints is None:
        return random_shape

    shape_tokens = shape_constraints.split(",")

    shape: list[int] = []

    for shape_token in shape_tokens:
        value = _process_shape_token(parameter_obj, shape_token)
        # Can be a list directly from a var dependency
        if isinstance(value, list):
            return value
        shape.append(value)

    # since -1 may exist in shape (due to '...'), process it
    final_shape: list[int] = []
    for s in shape:
        if s == -1:
            max_dim_fill = config.configuration.pynguinml.max_ndim - len(shape) + 1
            fill_size = randomness.next_int(0, max_dim_fill + 1)
            shape_dim = [
                randomness.next_int(0, config.configuration.pynguinml.max_shape_dim + 1)
                for _ in range(fill_size)
            ]
            final_shape += shape_dim
        else:
            final_shape.append(s)

    # Clamp each dimension of the shape to be within [0, max_dim]
    return [min(config.configuration.pynguinml.max_shape_dim, max(0, dim)) for dim in shape]


def _select_shape_constraint(parameter_obj: MLParameter, selected_ndim: int) -> str | None:
    for valid_shape in parameter_obj.valid_shapes:
        if "..." in valid_shape and len(valid_shape.split(",")) <= selected_ndim:
            return valid_shape
        if len(valid_shape.split(",")) == selected_ndim:
            return valid_shape
        if ":" in valid_shape:
            return valid_shape
    return None


def _process_shape_token(parameter_obj: MLParameter, shape_token: str):
    shape_value = 0
    sign = "+"

    while shape_token:  # process until shape_token is empty
        if shape_token[0] in "+-*/":
            sign = shape_token[0]
            shape_token = shape_token[1:]
            continue

        temp_value, shape_token = _resolve_shape_token(parameter_obj, shape_token)

        if isinstance(temp_value, list):
            return temp_value

        if isinstance(temp_value, str) and not mlpu.str_is_int(temp_value):
            raise ConstructionFailedException(f"Given shape value {temp_value} is invalid.")

        temp_value = int(temp_value)

        shape_value = _apply_sign(shape_value, temp_value, sign)

    return shape_value


def _resolve_shape_token(parameter_obj: MLParameter, shape_token: str):
    if shape_token.isnumeric():
        return int(shape_token), ""

    if shape_token[0] in "><":
        return _resolve_shape_bound(shape_token)

    if shape_token.startswith("."):
        return -1, ""

    if shape_token.startswith("len:"):
        return _resolve_len_dependency(parameter_obj, shape_token)

    if shape_token.startswith("ndim:"):
        return _resolve_ndim_dependency_for_shape(parameter_obj, shape_token)

    if shape_token.startswith("max_value:"):
        return _resolve_max_value_dependency(parameter_obj, shape_token)

    if shape_token.startswith("shape:"):
        return _resolve_shape_dependency(parameter_obj, shape_token)

    return _resolve_value_or_constant(parameter_obj, shape_token)


def _resolve_shape_bound(shape_token):
    unequal_sign, shape_bound = mlpu.parse_shape_bound(shape_token)
    if unequal_sign == ">":
        temp_value = randomness.next_int(
            shape_bound + 1, config.configuration.pynguinml.max_shape_dim + 1
        )
    else:
        temp_value = randomness.next_int(0, shape_bound)
    return temp_value, ""


def _resolve_len_dependency(parameter_obj, shape_token):
    shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "len:")
    dependency_obj = parameter_obj.parameter_dependencies[ref]
    try:
        return len(dependency_obj.current_data), shape_token
    except TypeError:
        raise ConstructionFailedException(f"Unable to get length of {ref}.") from None


def _resolve_ndim_dependency_for_shape(parameter_obj, shape_token):
    shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "ndim:")
    dependency_obj = parameter_obj.parameter_dependencies[ref]
    if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):
        return dependency_obj.current_data.ndim, shape_token
    if np.isscalar(dependency_obj.current_data):
        return 0, shape_token
    raise ConstructionFailedException(f"Unable to get ndim of {ref}.")


def _resolve_max_value_dependency(parameter_obj, shape_token):
    shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "max_value:")
    dependency_obj = parameter_obj.parameter_dependencies[ref]
    try:
        return int(max(dependency_obj.current_data)), shape_token
    except (TypeError, ValueError):
        raise ConstructionFailedException(
            f"Unable to get max value of {ref} with value {dependency_obj.current_data}."
        ) from None


def _resolve_shape_dependency(parameter_obj, shape_token):
    shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "shape:")
    dependency_obj = parameter_obj.parameter_dependencies[ref]
    if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):
        return list(cast("np.ndarray", dependency_obj.current_data).shape), shape_token
    if isinstance(dependency_obj.current_data, (int, float, complex, str)):
        return [], shape_token
    raise ConstructionFailedException(
        f"Unable to get shape of {ref} with value {dependency_obj.current_data}."
    )


def _resolve_value_or_constant(parameter_obj, shape_token):
    shape_token, ref, is_var = mlpu.parse_var_dependency(shape_token, "")
    if is_var:
        dependency_obj = parameter_obj.parameter_dependencies[ref]
        temp_value = dependency_obj.current_data
        if isinstance(temp_value, (bool, np.bool_)):
            raise ConstructionFailedException(
                f"Referred value of {ref} is a boolean value. Cannot be used to decide another var."
            )
        if not isinstance(temp_value, (int, float)):
            raise ConstructionFailedException(
                f"Referred value of {ref} is not a single numeric value. "
                f"Cannot be used to decide another var."
            )
        return temp_value, shape_token

    if ml_constant_pool.get_value(ref) is None:
        value = randomness.next_int(0, config.configuration.pynguinml.max_shape_dim + 1)
        ml_constant_pool.add(ref, value)
    return ml_constant_pool.get_value(ref), ""


def _apply_sign(shape_value, temp_value, sign):
    if sign == "+":
        return shape_value + temp_value
    if sign == "-":
        return max(0, shape_value - temp_value)
    if sign == "*":
        return shape_value * temp_value
    if temp_value == 0:
        raise ConstructionFailedException("Attempting to divide by 0.")
    return math.ceil(shape_value / temp_value)


def generate_ndarray(parameter_obj: MLParameter, shape: list, dtype: str):
    """Generates a ndarray as a nested list based on the given data type and shape.

    This function supports generating arrays for different numeric types (int, uint,
    float, complex, bool).

    Args:
        parameter_obj: The corresponding parameter_obj.
        shape (list[int]): The desired shape of the generated ndarray.
        dtype (str): The data type for the array (e.g., "int32").

    Returns:
        tuple: A tuple containing:
            - list: The generated ndarray as a nested list.
            - int | float: The lower bound of the value range used.
            - int | float: The upper bound of the value range used.

    Raises:
        ConstructionFailedException: If the array could not be generated based on the given dtype.
    """
    low: int | float | None = None
    high: int | float | None = None
    ndarray: np.ndarray | None = None

    int_or_uint = re.search(r"^(?:int|uint)", dtype)
    if int_or_uint:
        low, high = _get_range(parameter_obj, dtype)
        ndarray = _generate_int(dtype, shape, low, high)

    float_ = re.search(r"^float", dtype)
    if float_:
        low, high = _get_range(parameter_obj, dtype)
        ndarray = _generate_float(dtype, shape, low, high)

    complex_ = re.search(r"^complex(?P<num>[0-9]*)", dtype)
    if complex_:
        n_bit_str = complex_.group("num")
        half = int(n_bit_str) // 2 if n_bit_str else 64
        # Ensure half is one of the allowed values, otherwise default to 64.
        half = half if half in {32, 64} else 64
        half_n_bit = str(half)

        float_dtype = "float" + half_n_bit
        low, high = _get_range(parameter_obj, float_dtype)

        ndarray = _generate_complex(float_dtype, dtype, shape, low, high)

    if dtype == "bool":
        low = 0
        high = 0
        ndarray = _generate_bool(shape)

    parameter_obj.current_data = ndarray

    if all(var is not None for var in (ndarray, low, high)):
        return ndarray.tolist(), low, high  # type: ignore[union-attr]

    raise ConstructionFailedException(f"Could not generate based on the datatype {dtype}.")


def _get_range(parameter_obj: MLParameter, np_dtype: str):
    default_low, default_high = mlpu.get_default_range(np_dtype)
    default_low = max(default_low, -config.configuration.test_creation.max_int)
    default_high = min(default_high, config.configuration.test_creation.max_int)

    if not parameter_obj.valid_ranges:
        return default_low, default_high

    picked_range = None
    for range_ in parameter_obj.valid_ranges:
        if range_.required_dtype is not None and np_dtype == range_.required_dtype:
            picked_range = range_
            break
    if picked_range is None:
        picked_range = randomness.choice(parameter_obj.valid_ranges)

    if (
        picked_range.lower_bound is None
        or picked_range.lower_bound == -np.inf
        or picked_range.lower_bound < default_low
    ):
        low = default_low
    else:
        low = picked_range.lower_bound

    if (
        picked_range.upper_bound is None
        or picked_range.upper_bound == np.inf
        or picked_range.upper_bound > default_high
    ):
        high = default_high
    else:
        high = picked_range.upper_bound

    if (low < 0 or high < 0) and "uint" in np_dtype:
        low = 0
        high = max(high, low)

    return low, high


def _generate_int(np_dtype: str, shape: list, low: float, high: float):
    return get_rng().integers(
        size=shape, low=int(low), high=int(high), dtype=np.dtype(np_dtype), endpoint=True
    )


def _generate_float(np_dtype: str, shape: list, low: float, high: float):
    precision = randomness.next_int(0, 7)

    return np.round(
        get_rng().uniform(size=shape, low=float(low), high=float(high)),
        decimals=precision,
    ).astype(np_dtype)


def _generate_complex(float_dtype: str, np_dtype: str, shape: list, low: float, high: float):
    precision_real = randomness.next_int(0, 7)
    real_part = np.round(
        get_rng().uniform(size=shape, low=float(low), high=float(high)),
        decimals=precision_real,
    ).astype(float_dtype)

    precision_imag = randomness.next_int(0, 7)
    imag_part = np.round(
        get_rng().uniform(size=shape, low=float(low), high=float(high)),
        decimals=precision_imag,
    ).astype(float_dtype)

    return (real_part + 1j * imag_part).astype(np_dtype)


def _generate_bool(shape: list):
    return get_rng().random(shape) < 0.5


def change_generation_order(generation_order: list, param_types: dict[str, ProperType]):
    """Sorts param_types dict based on the order defined in generation_order.

    Args:
        generation_order (list): list of generation order
        param_types (dict): dict of param_types

    Returns:
        The sorted param_types based on the order defined in generation_order.
    """
    order_index = {name: idx for idx, name in enumerate(generation_order)}
    return dict(
        sorted(param_types.items(), key=lambda item: order_index.get(item[0], float("inf")))
    )


def reset_parameter_objects(parameters: dict[str, MLParameter | None]) -> None:
    """Reset all parameter objects and clear the ML constant pool.

    This removes any cached data used for parameter dependencies, ensuring a clean
    state before processing a new callable.
    """
    # Remove all the generated data in each parameter object
    for parameter in parameters.values():
        if parameter is not None:
            parameter.current_data = None

    ml_constant_pool.reset()


def is_ml_statement(statement: stmt.Statement):
    """Returns if a statement is an ML-specific statement."""
    if isinstance(statement, stmt.FunctionStatement) and not statement.should_mutate:
        return True
    return isinstance(statement, stmt.NdArrayStatement | stmt.AllowedValuesStatement)
