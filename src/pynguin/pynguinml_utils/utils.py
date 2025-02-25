import re

import numpy as np

import pynguin.configuration as config


class ConstraintValidationError(Exception):
    """Raised when a constraint contains faulty information."""

    def __init__(self, message="Invalid constraint data detected."):
        super().__init__(message)


_max_ndim = None


def max_ndim():
    """Returns the maximum number of dimensions for tensors."""
    global _max_ndim
    if _max_ndim is None:
        _max_ndim = config.configuration.pynguinml.max_ndim
    return _max_ndim


_ndim_values = None


def ndim_values():
    """Returns the ndim values for tensors."""
    global _ndim_values
    if _ndim_values is None:
        _ndim_values = list(range(max_ndim() + 1))
    return _ndim_values


_max_shape_dim = None


def max_shape_dim():
    """Returns the maximum shape dimension for tensors."""
    global _max_shape_dim
    if _max_shape_dim is None:
        _max_shape_dim = config.configuration.pynguinml.max_shape_dim
    return _max_shape_dim


def str_is_number(s: str) -> bool:
    return str_is_int(s) or str_is_float(s) or str_is_inf(s)


def str_is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def str_is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False


def str_is_inf(s):
    return s in ['inf', '-inf']


def convert_to_num(s: str):  #TODO(ah) is inf necessary?
    if str_is_int(s):
        return int(s)
    elif str_is_float(s):
        return float(s)
    elif s == 'inf':
        return np.inf
    elif s == '-inf':
        return np.NINF
    else:
        return None


def parse_var_dependency(tok: str, sp_str: str = '') -> tuple[str, str, bool]:
    """
    Parses a token to extract a variable dependency.

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

    # Define a regex to capture an optional '&' and then the variable name (alphanumeric and underscores).
    pattern = r'^(?P<var_flag>&?)(?P<ref>[A-Za-z0-9_]+)'
    match = re.match(pattern, tok)
    if not match:
        raise ConstraintValidationError(
            f"Invalid variable dependency constraint '{tok}'."
        )

    is_var = bool(match.group('var_flag'))
    ret_ref = match.group('ref')
    # The remainder is whatever follows the matched variable reference.
    remainder = tok[match.end():]

    return remainder, ret_ref, is_var


def parse_unequal_signs(tok: str) -> tuple[str | None, bool]:
    """
    Parses an inequality constraint token containing >, >=, <, or <=.
    For example, given a token like '>=5' or '<=len:&a':
      - It extracts the part after the inequality sign(s).
      - If that part is numeric, it is treated as a constant (returning (None, False)).
      - Otherwise, it is assumed to represent a variable dependency,
        in which case gobble_var_dep is used to extract the variable reference.

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
        raise ConstraintValidationError(
            f"Invalid constraint '{tok}' while parsing unequal signs."
        )

    # Check that the token starts with '>' or '<'
    if tok[0] not in ('>', '<'):
        raise ConstraintValidationError(
            f"Invalid constraint '{tok}' while parsing unequal signs: "
            f"expected token to start with '>' or '<'."
        )

    # Determine whether the inequality is two-character (>= or <=) or single-character (> or <)
    if tok[1] == '=':
        if len(tok) <= 2:
            raise ConstraintValidationError(
                f"Invalid constraint '{tok}' while parsing unequal signs."
            )
        num_part, _ = parse_until(2, tok)
    else:
        num_part, _ = parse_until(1, tok)

    # If num_part is not numeric, treat it as a variable dependency.
    if not num_part.isnumeric():
        _, ref, is_var = parse_var_dependency(num_part)
    else:
        ref, is_var = None, False

    return ref, is_var


def parse_until(start_idx: int, text: str, stop_chars: str = '') -> tuple[str, int]:
    """
    Extracts characters from `text` starting at index `start_idx` until a character in
    `stop_chars` is encountered. Spaces in the text are skipped.

    Args:
        start_idx (int): The index in `text` at which to start parsing.
        text (str): The string to parse.
        stop_chars (str, optional): A string containing characters that will stop the
                                    parsing. Defaults to '' (i.e., no stop characters).

    Returns:
        tuple[str, int]: A tuple where the first element is the accumulated string of
                         characters, and the second element is the index immediately
                         after the parsed segment.

    Raises:
        ValueError: If `start_idx` is out of bounds for `text`.
    """
    if start_idx >= len(text):
        raise ValueError(f'Unable to process "{text}"; likely an incorrect input format.')

    result = ''
    i = start_idx
    for i in range(start_idx, len(text)):
        ch = text[i]
        # Skip spaces.
        if ch == ' ':
            continue
        # If the character is one of the stop_chars, break out.
        if stop_chars and ch in stop_chars:
            break
        result += ch
    # Return the result and the next index (i + 1)
    return result, i + 1


def parse_shape_bound(tok: str) -> tuple[str, int]:
    """
    Parse a shape bound token to extract the operator and a non-inclusive numeric bound.

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
    if tok[start] == '>':
        sign = '>'
        start += 1
        if tok[start] == '=':
            # e.g., ">=5": subtract 1 to make it non-inclusive
            num, _ = parse_until(start + 1, tok)
            bound = int(num) - 1
        else:
            num, _ = parse_until(start, tok)
            bound = int(num)
    elif tok[start] == '<':
        sign = '<'
        start += 1
        if tok[start] == '=':
            # e.g., "<=5": add 1 to make it non-inclusive
            num, _ = parse_until(start + 1, tok)
            bound = int(num) + 1
        else:
            num, _ = parse_until(start, tok)
            bound = int(num)
    else:
        raise ValueError(f"Token '{tok}' must start with '>' or '<'.")

    return sign, bound


def get_default_range(np_dtype: str, n_bits: str):
    """
    Return the default numerical range for the given NumPy dtype.

    For floating-point types, the full range is obtained via np.finfo; for 64-bit floats,
    the range is halved to yield a more manageable range. For integer types, the range is
    obtained via np.iinfo.

    Args:
        np_dtype (str): The NumPy data type (e.g., "float64", "int32").
        n_bits (str): The bit width as a string (e.g., "64").

    Returns:
        tuple: A tuple (low, high) representing the lower and upper bounds.

    Raises:
        ValueError: If np_dtype is invalid.
    """
    if 'float' in np_dtype:
        low = np.finfo(np_dtype).min
        high = np.finfo(np_dtype).max
        if n_bits == '64':
            low /= 2
            high /= 2
    elif 'int' in np_dtype:
        low = np.iinfo(np_dtype).min
        high = np.iinfo(np_dtype).max
    else:
        raise ValueError(f"Cannot get range for dtype {np_dtype}")
    return low, high


def pick_all_integer_types(dtype_list: list, only_unsigned=False):
    signed_list = []
    unsigned_list = []
    for dtype in dtype_list:
        if re.search('.*int[0-9]*', dtype):
            if 'u' in dtype and only_unsigned:
                unsigned_list.append(dtype)
            else:
                signed_list.append(dtype)
    return unsigned_list if only_unsigned else signed_list


def pick_all_float_types(dtype_list: list):
    results = []
    for dtype in dtype_list:
        if re.search('.*float[0-9]*', dtype):
            results.append(dtype)
    return results


def pick_scalar_types(dtype_list: list):
    ints = pick_all_integer_types(dtype_list)
    floats = pick_all_float_types(dtype_list)
    return ints + floats
