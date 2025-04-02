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

from typing import TYPE_CHECKING
from typing import cast

import numpy as np

import pynguin.configuration as config
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

        if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):  # noqa: UP038
            picked_dtype = cast("np.ndarray", dependency_obj.current_data).dtype.name
        else:
            picked_dtype = type(dependency_obj.current_data).__name__

    return picked_dtype


def select_ndim(parameter_obj: MLParameter, selected_dtype: str) -> int:  # noqa: C901
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
            # depends on another param
            _, ref, _ = mlpu.parse_var_dependency(selected_ndim, "ndim:")

            # generate value from dependency param
            dependency_obj = parameter_obj.parameter_dependencies[ref]

            if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):  # noqa: UP038
                return cast("np.ndarray", dependency_obj.current_data).ndim

            if np.isscalar(dependency_obj.current_data):
                return 0

            raise ConstructionFailedException(f"Unable to get ndim of {ref}.")

        _, ref, is_var = mlpu.parse_var_dependency(selected_ndim, "")

        if is_var:
            dependency_obj = parameter_obj.parameter_dependencies[ref]

            value = dependency_obj.current_data
            if isinstance(value, (bool | np.bool_)):
                raise ConstructionFailedException(
                    f"Referred value {ref} is a boolean value. "
                    f"Cannot be used to decide another var."
                )
            if not isinstance(value, (int, float)):  # noqa: UP038
                raise ConstructionFailedException(
                    f"Referred value {ref} is not a single numeric value. "
                    f"Cannot be used to decide another var."
                )

            return int(value)

        if ml_constant_pool.get_value(ref) is None:
            value = randomness.next_int(0, config.configuration.pynguinml.max_ndim + 1)
            ml_constant_pool.add(ref, value)

        return ml_constant_pool.get_value(ref)  # type: ignore[return-value]

    # If it must be a tensor, exclude 0 as a dimension
    valid_ndim_values = [
        n for n in mlpu.ndim_values() if not (parameter_obj.tensor_expected and n == 0)
    ]

    return randomness.choice(valid_ndim_values)


def generate_shape(parameter_obj: MLParameter, selected_ndim: int) -> list:  # noqa: C901
    """Generate a shape based on the parameter's shape constraints and the selected ndim.

    Args:
        parameter_obj: The parameter object.
        selected_ndim: The selected dimension.

    Returns:
        list: The generated shape.
    """
    if parameter_obj.valid_shapes:
        shape_constraints = None
        for valid_shape in parameter_obj.valid_shapes:
            if "..." in valid_shape and len(valid_shape.split(",")) <= selected_ndim:
                shape_constraints = valid_shape
                break
            if len(valid_shape.split(",")) == selected_ndim:
                shape_constraints = valid_shape
                break
            if ":" in valid_shape:  # param dependency
                shape_constraints = valid_shape
                break

        if shape_constraints:
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
            return final_shape

    return [
        randomness.next_int(0, config.configuration.pynguinml.max_shape_dim + 1)
        for _ in range(selected_ndim)
    ]


def _process_shape_token(parameter_obj: MLParameter, shape_token: str):  # noqa: C901, PLR0915
    shape_value = 0
    sign = "+"
    while shape_token:  # process until shape_token is empty
        if shape_token[0] in "+-*/":
            sign = shape_token[0]
            shape_token = shape_token[1:]
            continue
        if shape_token.isnumeric():
            temp_value = int(shape_token)
            shape_token = ""
        elif shape_token[0] == ">" or shape_token[0] == "<":  # implicitly 1D
            unequal_sign, shape_bound = mlpu.parse_shape_bound(shape_token)
            if unequal_sign == ">":
                temp_value = randomness.next_int(
                    shape_bound + 1, config.configuration.pynguinml.max_shape_dim + 1
                )
            else:
                temp_value = randomness.next_int(0, shape_bound)
            shape_token = ""
        elif shape_token[0] == ".":  # there's unknown number of dimensions
            shape_token = ""
            temp_value = -1
        elif shape_token[0] == "l" and "len:" in shape_token:
            shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "len:")
            dependency_obj = parameter_obj.parameter_dependencies[ref]
            try:
                temp_value = len(dependency_obj.current_data)
            except TypeError:
                raise ConstructionFailedException(f"Unable to get length of {ref}.")  # noqa: B904
        elif shape_token[0] == "n" and "ndim:" in shape_token:
            shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "ndim:")
            dependency_obj = parameter_obj.parameter_dependencies[ref]

            if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):  # noqa: UP038
                temp_value = dependency_obj.current_data.ndim
            elif np.isscalar(dependency_obj.current_data):
                temp_value = 0
            else:
                raise ConstructionFailedException(f"Unable to get ndim of {ref}.")
        elif shape_token[0] == "m" and "max_value:" in shape_token:  # implicitly 1D
            shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "max_value:")
            dependency_obj = parameter_obj.parameter_dependencies[ref]
            try:
                temp_value = int(max(dependency_obj.current_data))
            except (TypeError, ValueError):
                raise ConstructionFailedException(  # noqa: B904
                    f"Unable to get max value of {ref} with value {dependency_obj.current_data}."
                )
        elif shape_token[0] == "s" and "shape:" in shape_token:
            shape_token, ref, _ = mlpu.parse_var_dependency(shape_token, "shape:")
            dependency_obj = parameter_obj.parameter_dependencies[ref]

            if isinstance(dependency_obj.current_data, (np.ndarray, np.generic)):  # noqa: UP038
                temp_value = list(cast("np.ndarray", dependency_obj.current_data).shape)  # type: ignore[assignment]
            elif isinstance(dependency_obj.current_data, int | float | complex | str):
                temp_value = []  # type: ignore[assignment]
            else:
                raise ConstructionFailedException(
                    f"Unable to get shape of {ref} with value {dependency_obj.current_data}."
                )
        else:
            # referring to another var or constant value e.g. [batch_size,num_labels]
            shape_token, ref, is_var = mlpu.parse_var_dependency(shape_token, "")
            if is_var:
                dependency_obj = parameter_obj.parameter_dependencies[ref]
                temp_value = dependency_obj.current_data
                if isinstance(temp_value, np.bool_ | bool):
                    raise ConstructionFailedException(
                        f"Referred value of {ref} is a boolean value. "
                        f"Cannot be used to decide another var."
                    )
                if not isinstance(temp_value, int | float):
                    raise ConstructionFailedException(
                        f"Referred value of {ref} is not a single numeric value. "
                        f"Cannot be used to decide another var."
                    )
            else:
                if ml_constant_pool.get_value(ref) is None:
                    value = randomness.next_int(0, config.configuration.pynguinml.max_shape_dim + 1)
                    ml_constant_pool.add(ref, value)
                shape_token = ""
                temp_value = ml_constant_pool.get_value(ref)  # type: ignore[assignment]

        if isinstance(temp_value, list):  # from a dependency
            return temp_value
        if isinstance(temp_value, str) and not mlpu.str_is_int(temp_value):
            raise ConstructionFailedException(f"Given shape value {temp_value} is invalid.")

        temp_value = int(temp_value)

        # check for special values
        if sign == "+":
            shape_value += temp_value
        elif sign == "-":
            shape_value = max(0, shape_value - temp_value)
        elif sign == "*":
            shape_value *= temp_value
        else:  # sign is '/'
            if temp_value == 0:
                raise ConstructionFailedException("Attempting to divide by 0.")
            shape_value = math.ceil(shape_value / temp_value)
    return shape_value


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

    # int/uint
    m = re.search(r"^(?:int|uint)", dtype)
    if m:
        low, high = _get_range(parameter_obj, dtype)
        ndarray = _generate_int(dtype, shape, low, high)  # type: ignore[arg-type]

    # float
    m = re.search(r"^float", dtype)
    if m:
        low, high = _get_range(parameter_obj, dtype)
        ndarray = _generate_float(dtype, shape, low, high)  # type: ignore[arg-type]

    # complex
    m = re.search(r"^complex(?P<num>[0-9]*)", dtype)
    if m:
        n_bit_str = m.group("num")
        half = int(n_bit_str) // 2 if n_bit_str else 64
        # Ensure half is one of the allowed values, otherwise default to 64.
        half = half if half in {32, 64} else 64
        half_n_bit = str(half)

        float_dtype = "float" + half_n_bit
        low, high = _get_range(parameter_obj, float_dtype)

        ndarray = _generate_complex(float_dtype, dtype, shape, low, high)  # type: ignore[arg-type]

    # bool
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

    if low < 0 and "uint" in np_dtype:
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
    """Resets all parameter objects and clears the ML constant pool."""
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
