#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides utility functions for parsing ML-specific data."""

import re

from functools import cache

import pynguin.configuration as config


try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if not NUMPY_AVAILABLE:
    raise ValueError("NumPy is not available. You can install it with poetry install --with numpy.")

from pynguin.utils.exceptions import ConstraintValidationError


@cache
def ndim_values() -> list[int]:
    """Returns the possible dimension numbers for tensors."""
    return list(range(config.configuration.pynguinml.max_ndim + 1))


def str_is_number(s: str) -> bool:
    """Checks if a string represents a number (integer, float, or infinity)."""
    return str_is_int(s) or str_is_float(s) or str_is_inf(s)


def str_is_float(s: str) -> bool:
    """Checks if a string represents a float."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def str_is_int(s: str) -> bool:
    """Checks if a string represents an integer."""
    try:
        int(s)
        return True
    except ValueError:
        return False


def str_is_inf(s):
    """Checks if a string represents positive or negative infinity."""
    return s in {"inf", "-inf"}


def convert_to_num(s: str) -> int | float:
    """Converts a string to an integer, float, or infinity."""
    if str_is_int(s):
        return int(s)
    if str_is_float(s):  # also includes inf/-inf
        return float(s)

    raise ValueError(f"Invalid numeric string: {s}")


def parse_var_dependency(tok: str, sp_str: str = "") -> tuple[str, str, bool]:
    """Parses a token to extract a variable dependency.

    If sp_str is provided (for example, 'ndim:'), the function splits the token on that
    substring and processes the part after it. The function looks for an optional '&'
    marker that indicates a variable reference, followed by an alphanumeric (or
    underscore) name.

    Examples:
      - "ndim:&var+2"  -> returns ("+2", "var", True)
      - "ndim:var"     -> returns ("", "var", False)

    Parameters:
        tok (str): The token string to parse.
        sp_str (str): A special delimiter string to split on before processing.

    Returns:
        Tuple[str, str, bool]: A tuple containing:
            - the remainder of the token after the variable name,
            - the variable reference name,
            - a boolean indicating whether the variable was marked with '&'.

    Raises:
        ConstraintValidationError: If the token does not match the expected format.
    """
    if sp_str:
        tok = tok.split(sp_str)[1]

    # regex to capture an optional '&' and then the variable name
    pattern = r"^(?P<var_flag>&?)(?P<ref>[A-Za-z0-9_]+)"
    match = re.match(pattern, tok)
    if not match:
        raise ConstraintValidationError(f"Invalid variable dependency constraint '{tok}'.")

    is_var = bool(match.group("var_flag"))
    ret_ref = match.group("ref")
    # The remainder is whatever follows the matched variable reference.
    remainder = tok[match.end() :]

    return remainder, ret_ref, is_var


def parse_unequal_signs(tok: str) -> tuple[str | None, bool]:
    """Parses a variable dependency token containing >, >=, <, or <=.

    For example, given a token like '>=5' or '<=&a':
      - It extracts the part after the inequality sign.
      - If that part is numeric, it is treated as a constant.
      - Otherwise, it's (assumed) variable dependency is parsed.
    This does NOT parse other operators such as "ndim:", "len:", etc.

    Parameters:
        tok: The token to be parsed, e.g. '>=5'

    Returns:
        A tuple (ref, is_var) where:
          - ref is the variable reference if the token is non-numeric, or None if numeric.
          - is_var is True if a variable dependency was detected, otherwise False.

    Raises:
        ConstraintValidationError: If the token is too short, does not start with '>' or '<',
                                   or if a number is expected but missing.
    """
    # Validate token length
    if not tok or len(tok) < 2:
        raise ConstraintValidationError(f"Invalid constraint '{tok}' while parsing unequal signs.")

    # Check that the token starts with '>' or '<'
    if tok[0] not in {">", "<"}:
        raise ConstraintValidationError(
            f"Invalid constraint '{tok}' while parsing unequal signs: "
            f"expected token to start with '>' or '<'."
        )

    # Determine whether the inequality is two-character (>= or <=) or single-character (> or <)
    if tok[1] == "=":
        if len(tok) <= 2:
            raise ConstraintValidationError(
                f"Invalid constraint '{tok}' while parsing unequal signs."
            )
        num_part = tok[2:]
    else:
        num_part = tok[1:]

    # If num_part is not numeric, treat it as a variable dependency.
    if not num_part.isnumeric():
        _, ref, is_var = parse_var_dependency(num_part)
    else:
        ref, is_var = None, False

    return ref, is_var


def parse_until(start_idx: int, text: str, stop_chars: str = "") -> tuple[str, int]:
    """Extracts characters from `text` starting at index `start_idx`.

    Stops if a character in `stop_chars` is encountered. Also removes spaces.

    Args:
        start_idx (int): The index in `text` at which to start parsing.
        text (str): The string to parse.
        stop_chars (str, optional): A string containing characters that will stop the
                                    parsing. Defaults to '' (i.e., no stop characters).

    Returns:
        tuple[str, int]: A tuple where the first element is the extracted string, and
                         the second element is the index immediately after the string.

    Raises:
        ValueError: If `start_idx` is out of bounds for `text`.
    """
    if start_idx > len(text) or start_idx < 0:
        raise ValueError(f"Start index {start_idx} is out of bounds for text {text}")

    result = ""
    i = start_idx
    for i in range(start_idx, len(text)):
        ch = text[i]
        # Skip spaces.
        if ch == " ":
            continue
        # If the character is one of the stop_chars, break out.
        if stop_chars and ch in stop_chars:
            break
        result += ch
    # Return the result and the next index (i + 1)
    return result, i + 1


def parse_shape_bound(tok: str) -> tuple[str, int]:
    """Parse a shape bound token to extract the operator and a non-inclusive numeric bound.

    The token should begin with '>' or '<', optionally followed by '='. The returned bound
    is adjusted so that the inequality is non-inclusive. For example:

      - ">=5" is interpreted as "shape length > 4" (i.e. returns ('>', 4)).
      - ">5"  is interpreted as "shape length > 5" (i.e. returns ('>', 5)).
      - "<=5" is interpreted as "shape length < 6" (i.e. returns ('<', 6)).
      - "<5"  is interpreted as "shape length < 5" (i.e. returns ('<', 5)).

    Args:
        tok (str): The token to be parsed (e.g., ">=5" or "<3").

    Returns:
        tuple[str, int]: A tuple containing:
            - The operator ('>' or '<').
            - The adjusted numeric bound as an integer.

    Raises:
        ValueError: If the token is too short or does not start with '>' or '<'.
    """
    if len(tok) < 2:
        raise ValueError(f"Token '{tok}' is too short to be valid.")

    start = 0
    if tok[start] == ">":
        sign = ">"
        start += 1
        if tok[start] == "=":
            # e.g., ">=5": subtract 1 to make it non-inclusive
            num, _ = parse_until(start + 1, tok)
            bound = int(num) - 1
        else:
            num, _ = parse_until(start, tok)
            bound = int(num)
    elif tok[start] == "<":
        sign = "<"
        start += 1
        if tok[start] == "=":
            # e.g., "<=5": add 1 to make it non-inclusive
            num, _ = parse_until(start + 1, tok)
            bound = int(num) + 1
        else:
            num, _ = parse_until(start, tok)
            bound = int(num)
    else:
        raise ValueError(f"Token '{tok}' must start with '>' or '<'.")

    return sign, bound


def get_default_range(np_dtype: str) -> tuple[float, float]:
    """Return the default numerical range for the given NumPy dtype.

    Args:
        np_dtype (str): The NumPy data type (e.g., "float64", "int32").

    Returns:
        tuple: A tuple (low, high) representing the lower and upper bounds.

    Raises:
        ValueError: If np_dtype is invalid.
    """
    try:
        np_dtype_obj = np.dtype(np_dtype)
    except TypeError:
        raise ValueError(f"Invalid NumPy dtype: {np_dtype}") from None

    if np.issubdtype(np_dtype_obj, np.floating):
        finfo = np.finfo(np_dtype_obj)
        return float(finfo.min), float(finfo.max)
    if np.issubdtype(np_dtype_obj, np.integer):
        iinfo = np.iinfo(np_dtype_obj)
        return float(iinfo.min), float(iinfo.max)
    raise ValueError(f"Cannot get range for dtype {np_dtype}")


def pick_all_integer_types(dtype_list: list[str], only_unsigned=False) -> list[str]:  # noqa: FBT002
    """Extracts and returns all integer types from a list of data types.

    Args:
        dtype_list (list[str]): A list of dtype strings to filter.
        only_unsigned (bool, optional): If True, returns only unsigned integer types.

    Returns:
        list[str]: A list of matching integer types.
    """
    signed_list = []
    unsigned_list = []
    for dtype in dtype_list:
        if re.fullmatch(r"u?int\d+", dtype):
            if dtype.startswith("u") and only_unsigned:
                unsigned_list.append(dtype)
            else:
                signed_list.append(dtype)
    return unsigned_list if only_unsigned else signed_list


def pick_all_float_types(dtype_list: list[str]) -> list[str]:
    """Extracts and returns all float types from a list of data types.

    Args:
        dtype_list (list[str]): A list of dtype strings to filter.

    Returns:
        list[str]: A list of matching float types.
    """
    return [dtype for dtype in dtype_list if re.fullmatch(r"float\d+", dtype)]


def pick_scalar_types(dtype_list: list[str]) -> list[str]:
    """Extracts and returns all scalar (int and float) types from a dtype list.

    Args:
        dtype_list (list[str]): A list of dtype strings to filter.

    Returns:
        list[str]: A list of matching scalar types (ints and floats).
    """
    return pick_all_integer_types(dtype_list) + pick_all_float_types(dtype_list)


def _infer_type_from_str(value: str) -> str:
    if str_is_int(value):
        return "int"
    if str_is_float(value):
        return "float"
    if value.lower().strip() in {"true", "false"}:
        return "bool"

    return "str"


def convert_values(values: list[str]) -> list[int | float | bool | str]:
    """Converts the string values to its inferred type (int, float, bool, or string).

    Args:
        values: A list of string values.

    Returns:
        list[int | float | bool | str]: A list of converted values in their inferred types.
    """
    converted_values: list[int | float | bool | str] = []

    for value in values:
        cast_type = _infer_type_from_str(value)

        if cast_type == "int":
            converted_values.append(int(value))
        elif cast_type == "float":
            converted_values.append(float(value))
        elif cast_type == "bool":
            converted_values.append(value.lower().strip() == "true")
        else:
            converted_values.append(value)  # Keep as string

    return converted_values


def convert_str_to_type(type_str: str) -> type:
    """Converts a type name given as a string (including NumPy types) into a Python type.

    Args:
        type_str (str): The type name as a string (e.g., "int", "float32").

    Returns:
        type: The corresponding Python type (e.g., int, float, complex, str, bool).
    """
    # Mapping for common Python built-in types
    python_type_map = {"int": int, "float": float, "bool": bool, "complex": complex, "str": str}

    if type_str in python_type_map:
        return python_type_map[type_str]

    if not NUMPY_AVAILABLE:
        raise ValueError(
            f"Cannot convert NumPy type '{type_str}' because NumPy is not available. "
            "You can install it with poetry install --with numpy."
        )

    try:
        np_type = np.dtype(type_str).type
    except TypeError as e:
        raise ValueError(f"Unknown type: {type_str}") from e

    if np.issubdtype(np_type, np.integer):
        return int
    if np.issubdtype(np_type, np.floating):
        return float
    if np.issubdtype(np_type, np.complexfloating):
        return complex
    if np.issubdtype(np_type, np.bool_):
        return bool
    raise ValueError(f"Cannot convert type '{type_str}' to Python type.")


def get_shape(array: list) -> list[int]:
    """Computes the shape of a rectangular nested list.

    Args:
        array (list): A nested list representing a multidimensional array.

    Returns:
        list[int]: A list of integers representing the shape of the array.

    Raises:
        ValueError: If NumPy is not available.
    """
    if not NUMPY_AVAILABLE:
        raise ValueError(
            "NumPy is not available for computing array shape. "
            "You can install it with poetry install --with numpy."
        )
    return list(np.shape(array))
