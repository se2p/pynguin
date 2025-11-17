#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Representation of an ML-specific Parameter."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import pynguin.configuration as config
import pynguin.utils.pynguinml.ml_parsing_utils as mlpu
from pynguin.utils.exceptions import ConstraintValidationError

COMMON_NUMPY_DTYPES = [
    "int32",
    "int64",
    "float32",
    "float64",
    "complex64",
    "complex128",
    "bool",
    "str",
]


class MLParameter:
    """Parameter class for storing ML specific information."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        parameter_name: str,
        parameter_constraints: dict,
        dtype_map: dict[str, str] | None,
    ):
        """Initialize a Parameter object.

        Parses and validates parameter constraints.

        Args:
            parameter_name: the name of the parameter.
            parameter_constraints: a dictionary of constraints.
            dtype_map: a dictionary from library-specific dtypes to NumPy dtypes, or None.
        """
        self.current_data: Any = None

        self.parameter_name = parameter_name
        self.parameter_constraints = parameter_constraints

        self.valid_ndims: list[str] = []
        self.valid_shapes: list[str] = []
        self.valid_ranges: list[Range] = []
        self.valid_enum_values: list[str] = []
        self.valid_dtypes: list[str] = []
        self.tensor_expected: bool = False
        self.structure: str | None = None

        self.parameter_dependencies: dict[str, MLParameter] = {}
        self.var_dep: set[str] = set()

        self._logger.debug("Started analysing constraints of parameter %s.", parameter_name)

        self._parse_ndims()
        self._parse_shape()
        self._parse_range()
        self._parse_enum()
        self._parse_dtype(dtype_map)
        self._parse_tensor_t()
        self._parse_structure()

    def _parse_ndims(self):
        """Parse and validate 'ndim' constraints from self.parameter_constraints.

        This method extracts dimension constraints specified under the 'ndim' key,
        converts numeric constraints to strings, and handles inequality expressions
        (>, >=, <, <=) by computing a valid range of dimension values. It also extracts
        variable dependencies from constraints (e.g. 'ndim:&a') and populates the
        self.var_dep set accordingly.

        The computed valid dimension values (as strings) are stored in self.valid_ndims.

        Raises:
            ConstraintValidationError: If constraints are not in the expected format.
        """
        if "ndim" not in self.parameter_constraints:
            return

        ndim_constraints = self.parameter_constraints["ndim"]
        if not isinstance(ndim_constraints, list):
            raise ConstraintValidationError(
                "The 'ndim' constraint must be a list. Please check and correct the YAML file."
            )

        valid_ndims = set()
        for ndim in ndim_constraints:
            # possible to have int/float, convert to str for consistency
            ndim_str = str(ndim)

            if ndim_str == "?":
                continue

            if ndim_str.startswith("-"):
                self._logger.warning("Invalid ndim %s: negative values are not allowed.", ndim_str)
                continue

            if ndim_str.isnumeric():
                valid_ndims.add(ndim_str)
                continue

            if mlpu.str_is_float(ndim_str):
                self._logger.warning(
                    "The 'ndim' constraint contain floats. Please check and correct the YAML file."
                )
                continue

            if self._handle_inequality(ndim_str, valid_ndims):
                continue

            if "ndim:" in ndim_str:
                self._handle_ndim_var_dependency(ndim_str, valid_ndims)
                continue

            self._handle_var_dependency(ndim_str, valid_ndims)

        self.valid_ndims = list(valid_ndims)

    def _handle_inequality(self, ndim_str, valid_ndims) -> bool:
        if ">=" in ndim_str:
            min_ndim = self._parse_ndim_after_operator(ndim_str, ndim_str.find(">=") + 1)
            if min_ndim is not None:
                valid_ndims.update(
                    map(str, range(min_ndim, config.configuration.pynguinml.max_ndim + 1))
                )
            return True

        if ">" in ndim_str:
            tmp = self._parse_ndim_after_operator(ndim_str, ndim_str.find(">"))
            if tmp is not None:
                min_ndim = tmp + 1
                valid_ndims.update(
                    map(str, range(min_ndim, config.configuration.pynguinml.max_ndim + 1))
                )
            return True

        if "<=" in ndim_str:
            max_ndim = self._parse_ndim_after_operator(ndim_str, ndim_str.find("<=") + 1)
            if max_ndim is not None:
                valid_ndims.update(map(str, range(max_ndim + 1)))
            return True

        if "<" in ndim_str:
            tmp = self._parse_ndim_after_operator(ndim_str, ndim_str.find("<"))
            if tmp is not None:
                max_ndim = tmp - 1
                valid_ndims.update(map(str, range(max_ndim + 1)))
            return True

        return False

    def _parse_ndim_after_operator(self, ndim_string, idx) -> int | None:
        num = ndim_string[idx + 1 :]
        try:
            num = int(num)
        except ValueError:
            num = None

        if num is not None:
            if num < 0:
                self._logger.warning("Invalid ndim %s: negative values are not allowed.", num)
                return None

            if num > config.configuration.pynguinml.max_ndim:
                self._logger.warning(
                    "The ndim value %s is greater than configured max ndim value %s.",
                    num,
                    config.configuration.pynguinml.max_ndim,
                )
                return None

        return num

    def _handle_ndim_var_dependency(self, ndim_str, valid_ndims):
        _, ref, is_var = mlpu.parse_var_dependency(ndim_str, "ndim:")
        if not is_var:
            self._logger.warning(
                'Expected a variable (with "&") in "ndim:xx", got constant "%s" instead.',
                ref,
            )
            raise ConstraintValidationError
        self.var_dep.add(ref)
        valid_ndims.add(ndim_str)

    def _handle_var_dependency(self, ndim_str, valid_ndims):
        _, ref, is_var = mlpu.parse_var_dependency(ndim_str)
        if is_var:
            self.var_dep.add(ref)
        valid_ndims.add(ndim_str)

    def _parse_shape(self):
        """Parse and validate 'shape' constraints from self.parameter_constraints.

        This method processes shape constraints specified as a list of strings.
        For each shape specification:
          - Whitespace is removed.
          - Surrounding square brackets are stripped.
          - Variable dependencies are extracted via __process_shape_tokens.

        Valid shape specifications are stored in self.valid_shapes in the cleaned
        format, while any variable dependencies found are added to self.var_dep.

        Raises:
            ConstraintValidationError: If the 'shape' constraint is not provided as a list.
        """
        if "shape" not in self.parameter_constraints:
            return

        shape_constraints = self.parameter_constraints["shape"]
        if not isinstance(shape_constraints, list):
            self._logger.warning(
                "The 'shape' constraint must be a list. Please check and correct the YAML file."
            )
            raise ConstraintValidationError

        var_dep = []
        final_shape_spec_list = []

        for shape in shape_constraints:
            if not shape or not isinstance(shape, str):
                continue

            shape_cleaned = "".join(shape.split())  # remove whitespaces

            if shape_cleaned[0] == "[" and shape_cleaned[-1] == "]":
                shape_cleaned = shape_cleaned[1:-1]  # remove '[]'

            shape_tokens = re.split(r"[,+\-*/]", shape_cleaned)

            try:
                var_dep_part = self._process_shape_dependencies(shape_tokens)
            except ConstraintValidationError as e:
                self._logger.warning("Shape spec %s is not understandable: %s. Skipping.", shape, e)
                continue

            final_shape_spec_list.append(shape_cleaned)
            var_dep.extend(var_dep_part)

        self.valid_shapes = final_shape_spec_list
        self.var_dep.update(var_dep)

    @staticmethod
    def _process_shape_dependencies(shape_tokens: list[str]) -> list[str]:
        var_dep = []

        for shape_token in shape_tokens:
            if not shape_token:
                raise ConstraintValidationError(
                    f"Empty shape constraint token found: {shape_token}."
                )

            if shape_token.isnumeric() or shape_token[0] == ".":
                continue

            if mlpu.str_is_float(shape_token):
                raise ConstraintValidationError(
                    f"Shape constraint token cannot be a float number: {shape_token}."
                )

            ref, is_var = MLParameter._parse_token_dependency(shape_token)

            if ref is not None and is_var:
                var_dep.append(ref)

        return var_dep

    @staticmethod
    def _parse_token_dependency(shape_token: str) -> tuple[str | None, bool]:
        if shape_token[0] in "><":
            return mlpu.parse_unequal_signs(shape_token)
        if shape_token[0] == "&":
            _, ref, is_var = mlpu.parse_var_dependency(shape_token)
            return ref, is_var
        if "len:" in shape_token:
            return MLParameter._validate_named_dependency(shape_token, "len:")
        if "ndim:" in shape_token:
            return MLParameter._validate_named_dependency(shape_token, "ndim:")
        if "max_value:" in shape_token:
            return MLParameter._validate_named_dependency(shape_token, "max_value:")
        if "shape:" in shape_token:
            return MLParameter._validate_named_dependency(shape_token, "shape:")
        # fallback to generic dependency
        _, ref, is_var = mlpu.parse_var_dependency(shape_token)
        return ref, is_var

    @staticmethod
    def _validate_named_dependency(shape_token: str, prefix: str) -> tuple[str, bool]:
        _, ref, is_var = mlpu.parse_var_dependency(shape_token, prefix)
        if not is_var:
            raise ConstraintValidationError(
                f'Expected a variable (with "&") in "{prefix}xx", got constant "{ref}" instead.'
            )
        return ref, is_var

    def _parse_range(self):
        """Parse and process 'range' constraints from self.parameter_constraints.

        Each constraint is processed via __process_range_constraint to produce a Range
        object, which is appended to self.valid_ranges.

        Raises:
            ConstraintValidationError: If the 'range' constraint is not a list of strings.
        """
        if "range" not in self.parameter_constraints:
            return

        range_constraints: list[str] = self.parameter_constraints["range"]
        if not isinstance(range_constraints, list) or any(
            not isinstance(x, str) for x in range_constraints
        ):
            self._logger.warning(
                "The 'range' constraint must be a list of strings. "
                "Please check and correct the YAML file."
            )
            raise ConstraintValidationError

        for range_constraint in range_constraints:
            expected_dtype = None
            if ":" in range_constraint and all(
                x not in range_constraint for x in ("ndim:", "len:", "dtype:", "max_value:")
            ):  # special form, e.g., "int:[0, inf)"
                expected_dtype = range_constraint.split(":")[0]
                range_constraint = range_constraint.split(":")[1]  # noqa: PLW2901

            range_: Range | None = self._process_range_constraint(expected_dtype, range_constraint)
            if range_ is not None:
                self.valid_ranges.append(range_)

    def _process_range_constraint(
        self, expected_dtype: str | None, range_constraint: str
    ) -> Range | None:
        if (
            range_constraint[0] not in "(["
            or range_constraint[-1] not in "])"
            or "," not in range_constraint
        ):
            self._logger.warning("Invalid range constraint: %s", range_constraint)
            return None

        # epsilon when inclusivity is false
        float_epsilon = 1e-8
        int_epsilon = 1

        lower_bound_inclusive = range_constraint[0] == "["
        lower_bound_value = self._parse_bound_value(
            range_constraint,
            1,
            ",",
            inclusive=lower_bound_inclusive,
        )
        if lower_bound_value is None:
            return None

        lower_bound_value = self._add_epsilon_for_lower_bound(
            float_epsilon, int_epsilon, lower_bound_inclusive, lower_bound_value
        )

        upper_bound_inclusive = range_constraint[-1] == "]"
        upper_bound_value = self._parse_bound_value(
            range_constraint,
            range_constraint.find(",") + 1,
            ")]",
            inclusive=upper_bound_inclusive,
        )
        if upper_bound_value is None:
            return None

        upper_bound_value = self._add_epsilon_for_upper_bound(
            float_epsilon, int_epsilon, upper_bound_inclusive, upper_bound_value
        )

        assert lower_bound_value is not None
        assert upper_bound_value is not None

        if lower_bound_value > upper_bound_value:
            self._logger.warning(
                "Lower bound value cannot be greater than upper bound: %s", range_constraint
            )
            return None
        if (
            lower_bound_value == upper_bound_value
            and not lower_bound_inclusive
            and not upper_bound_inclusive
        ):
            self._logger.warning("The range must have distinct minimum and maximum values.")
            return None

        return Range(
            required_dtype=expected_dtype,
            lower_bound=lower_bound_value,
            upper_bound=upper_bound_value,
        )

    @staticmethod
    def _add_epsilon_for_upper_bound(
        float_epsilon, int_epsilon, upper_bound_inclusive, upper_bound_value
    ):
        if not upper_bound_inclusive:
            if isinstance(upper_bound_value, int):
                upper_bound_value -= int_epsilon
            elif isinstance(upper_bound_value, float):
                upper_bound_value -= float_epsilon
        return upper_bound_value

    @staticmethod
    def _add_epsilon_for_lower_bound(
        float_epsilon, int_epsilon, lower_bound_inclusive, lower_bound_value
    ):
        if not lower_bound_inclusive:
            if isinstance(lower_bound_value, int):
                lower_bound_value += int_epsilon
            elif isinstance(lower_bound_value, float):
                lower_bound_value += float_epsilon
        return lower_bound_value

    def _parse_bound_value(
        self,
        range_constraint: str,
        start_idx: int,
        stop_chars: str,
        *,
        inclusive: bool,
    ) -> float | int | None:
        bound_str, _ = mlpu.parse_until(start_idx, range_constraint, stop_chars)
        if not mlpu.str_is_number(bound_str):
            self._logger.warning("Bound values of range constraint must be int, float or inf.")
            return None

        return mlpu.convert_to_num(bound_str)

    def _parse_enum(self):
        """Parse 'enum' constraints from self.parameter_constraints."""
        if "enum" in self.parameter_constraints:
            self.valid_enum_values = self.parameter_constraints["enum"]

    def _parse_dtype(self, dtype_map: dict[str, str] | None):
        default_dtypes = COMMON_NUMPY_DTYPES if dtype_map is None else list(set(dtype_map.values()))
        self.valid_dtypes = default_dtypes

        if "dtype" not in self.parameter_constraints or dtype_map is None:
            return

        dtype_constraints = self.parameter_constraints.get("dtype")
        if dtype_constraints is None:
            self._logger.warning("A dtype constraint is None. Using the default datatype list.")
            return

        if not isinstance(dtype_constraints, list):
            self._logger.warning(
                "The 'dtype' constraint must be a list. Please check and correct the YAML file. "
                "Using the default datatype list."
            )
            return

        known_dtypes_dict = {
            dtype: dtype_map[dtype] for dtype in dtype_constraints if dtype in dtype_map
        }
        known_dtypes = list(known_dtypes_dict.values())

        if any("str" in dtype.lower() for dtype in dtype_constraints):
            known_dtypes.append("str")

        rest_dtypes = list(
            set(dtype_constraints)
            - set(known_dtypes_dict.keys())
            - {dtype for dtype in dtype_constraints if "str" in dtype.lower()}
        )

        special_dtypes = self._extract_special_dtypes(rest_dtypes)
        self._extract_dtype_dependencies(rest_dtypes, known_dtypes)

        rest_dtypes = list(set(rest_dtypes) - set(special_dtypes) - set(known_dtypes))
        if rest_dtypes:
            self._logger.warning("Unknown dtypes occurred: %s", rest_dtypes)

        if not known_dtypes and not special_dtypes:
            self._logger.warning("All dtypes are unrecognizable. Using the default dtypes.")
            return

        dtype_list = self._expand_special_dtypes(special_dtypes, default_dtypes)
        dtype_list += known_dtypes
        self.valid_dtypes = list(set(dtype_list))

    @staticmethod
    def _extract_special_dtypes(dtype_list):
        return [
            dtype
            for dtype in dtype_list
            if dtype.lower() in {"int", "float", "tensorshape", "scalar", "numeric"}
        ]

    def _extract_dtype_dependencies(self, dtype_list, known_dtypes):
        dtype_dep_list = [dtype for dtype in dtype_list if "dtype:" in dtype]
        for dtype_dep in dtype_dep_list:
            _, ref, is_var = mlpu.parse_var_dependency(dtype_dep, "dtype:")
            if not is_var:
                self._logger.warning(
                    'Expected a variable (with "&") in "dtype:xx", got constant %s instead.', ref
                )
                raise ConstraintValidationError
            self.var_dep.add(ref)
            known_dtypes.append(dtype_dep)

    def _expand_special_dtypes(self, special_dtypes, default_dtypes):
        dtype_list = []
        for dtype in special_dtypes:
            match dtype.lower():
                case "int":
                    dtype_list += mlpu.pick_all_integer_types(default_dtypes)
                case "float":
                    dtype_list += mlpu.pick_all_float_types(default_dtypes)
                case "tensorshape":
                    dtype_list += mlpu.pick_all_integer_types(default_dtypes, only_unsigned=True)
                    self.valid_ndims = ["1"]
                case "scalar":
                    dtype_list += mlpu.pick_scalar_types(default_dtypes)
                    self.valid_ndims = ["0"]
                case "numeric":
                    dtype_list += mlpu.pick_scalar_types(default_dtypes)
        return dtype_list

    def _parse_tensor_t(self):
        """Parse 'tensor_t' constraints from self.parameter_constraints."""
        tensor_t = self.parameter_constraints.get("tensor_t")
        if tensor_t is not None:
            self.tensor_expected = True

    def _parse_structure(self):
        """Parse 'structure' constraints from self.parameter_constraints.

        Structure means the array should not be a classic tensor but a normal list or tuple.
        It prioritizes list as a structure first.

        Raises:
            ConstraintValidationError: If the 'structure' constraint is not in the expected format.
        """
        structure = self.parameter_constraints.get("structure")

        if structure is None:
            return

        if not isinstance(structure, list):
            raise ConstraintValidationError("Structure constraint must be a list.")

        if "list" in structure:
            self.structure = "list"
        elif "tuple" in structure:
            self.structure = "tuple"


@dataclass
class Range:
    """Represents a numerical range."""

    required_dtype: str | None = None
    lower_bound: int | float | None = None
    upper_bound: int | float | None = None
