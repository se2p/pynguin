#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides resource functionality for ML-testing such as loading constraints."""

import importlib
import inspect
import json
import logging

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import networkx as nx
import yaml


try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if not NUMPY_AVAILABLE:
    raise ImportError(
        "NumPy is not available. You can install it with poetry install --with numpy."
    )

import pynguin.configuration as config

from pynguin.utils.exceptions import ConstraintValidationError
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.pynguinml.mlparameter import MLParameter


if TYPE_CHECKING:
    from types import FunctionType

    from pynguin.analyses.module import ModuleTestCluster


LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_datatype_mapping() -> dict[str, str] | None:
    """Loads and caches the datatype mapping from a YAML or JSON file.

    Returns:
        A dictionary mapping string keys to NumPy dtype strings, or `None` if
        loading or validation fails.
    """
    file_path = config.configuration.pynguinml.dtype_mapping_path.strip()
    if not file_path:
        return None

    try:
        path = Path(file_path)
        with path.open(encoding="utf-8") as f:
            if path.suffix.lower() in {".yaml", ".yml"}:
                dtype_map = yaml.safe_load(f)
            elif path.suffix.lower() == ".json":
                dtype_map = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")

        dtype_map = {k: v for k, v in dtype_map.items() if v is not None}
        for v in dtype_map.values():
            np.dtype(v)  # Validate that it's a known NumPy dtype
        return dtype_map
    except Exception as e:  # noqa: BLE001
        LOGGER.warning("Could not load datatype mapping file %s: %s", file_path, e)
        return None


@lru_cache(maxsize=1)
def get_nparray_function(test_cluster: "ModuleTestCluster") -> GenericFunction:
    """Loads and caches the nparray function for generating np.ndarray.

    Args:
        test_cluster: The test cluster for type system usage.

    Returns:
        A `GenericFunction` instance wrapping `numpy.array`.
    """
    inferred_signature = test_cluster.type_system.infer_type_info(
        np.array,
        type_inference_strategy=config.configuration.type_inference.type_inference_strategy,
    )

    # np.array is a built-in function, adjust the signature manually
    signature = inspect.Signature(
        parameters=[
            inspect.Parameter("object", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("dtype", inspect.Parameter.KEYWORD_ONLY),
        ],
        return_annotation=np.ndarray,
    )

    inferred_signature.signature = signature

    return GenericFunction(
        cast("FunctionType", np.array),
        inferred_signature,
        set(),
        "array",
    )


@lru_cache(maxsize=1)
def get_constructor_function(test_cluster: "ModuleTestCluster") -> GenericFunction | None:
    """Dynamically loads and caches a constructor function for tensors.

    Args:
        test_cluster: The test cluster for type system usage.

    Returns:
        A `GenericFunction` instance wrapping the constructor function, or `None`
        if the function could not be loaded or is not configured.
    """
    if (
        not config.configuration.pynguinml.constructor_function
        or not config.configuration.pynguinml.constructor_function_parameter
    ):
        LOGGER.info("No constructor function available for building tensors.")
        return None

    try:
        # Split the string into module and function parts
        parts = config.configuration.pynguinml.constructor_function.split(".")
        module_name, function_path = parts[0], parts[1:]

        module = importlib.import_module(module_name)

        # Traverse to the target function
        func = module
        for attr in function_path:
            func = getattr(func, attr)

        inferred_signature = test_cluster.type_system.infer_type_info(
            cast("FunctionType", func),
            type_inference_strategy=config.configuration.type_inference.type_inference_strategy,
        )

        # If it is a built-in function, we will not have the right parameter names.
        # Therefore, create our own signature with parameter name from config.
        signature = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    config.configuration.pynguinml.constructor_function_parameter,
                    inspect.Parameter.KEYWORD_ONLY,
                )
            ],
            return_annotation=Any,
        )

        inferred_signature.signature = signature

        LOGGER.info(
            "Successfully loaded constructor function: %s",
            config.configuration.pynguinml.constructor_function,
        )
        return GenericFunction(cast("FunctionType", func), inferred_signature, set(), parts[-1])
    except (ImportError, AttributeError, ValueError) as e:
        LOGGER.warning(
            "Failed to load constructor function '%s': %s",
            config.configuration.pynguinml.constructor_function,
            e,
        )
        return None


def _get_parameter_constraints(constraints: dict, parameter_name: str) -> dict | None:
    """Returns the specific parameter constraints from a constraints dictionary.

    Args:
        constraints: A dictionary containing parameter constraints.
        parameter_name: The name of the parameter to retrieve constraints for.

    Returns:
        A dictionary containing the constraints for the given parameter if usable
        constraints exist, or None if no usable constraints exist.
    """
    p_constraints = constraints.get(parameter_name, {})

    usable_categories = {"dtype", "ndim", "shape", "range", "enum", "tensor_t", "structure"}

    # Check if any usable categories exist in the parameter constraints
    if any(category in usable_categories for category in p_constraints):
        return p_constraints

    return None


def load_and_process_constraints(
    module_name: str, callable_name: str, parameter_names: list[str]
) -> tuple[dict[str, MLParameter | None], list[str]]:
    """Loads and processes YAML constraints for a given module and callable.

    Args:
        module_name: The name of the module.
        callable_name: The name of the callable function.
        parameter_names: A list of parameter names to process.

    Returns:
        tuple[dict[str, MLParameter], list[str]]:
            - A dictionary mapping parameter names to MLParameter objects.
            - A list representing the generation order of parameters.
    """
    constraints_base = (
        Path(config.configuration.pynguinml.constraints_path) / f"{module_name}.{callable_name}"
    )
    possible_files = [
        Path(f"{constraints_base}.yaml"),
        Path(f"{constraints_base}.yml"),
        Path(f"{constraints_base}.json"),
    ]

    # Find the first existing constraints file
    constraints_file = next((f for f in possible_files if f.exists()), None)

    if constraints_file is None:
        LOGGER.debug(
            "No constraints file found for module %s and callable %s",
            module_name,
            callable_name,
        )
        return {}, []

    try:
        with constraints_file.open(encoding="utf-8") as f:
            if constraints_file.suffix.lower() in {".yaml", ".yml"}:
                constraints_data = yaml.safe_load(f)
            else:
                constraints_data = json.load(f)
    except Exception as e:  # noqa: BLE001
        LOGGER.warning("Could not load constraint file %s: %s", constraints_file, e)
        return {}, []

    constraints = constraints_data.get("constraints", {}) if constraints_data else {}

    parameters: dict[str, MLParameter | None] = {}

    for parameter_name in parameter_names:
        parameter_constraints = _get_parameter_constraints(constraints, parameter_name)
        if parameter_constraints is not None:
            parameter = MLParameter(parameter_name, parameter_constraints, get_datatype_mapping())
        else:
            parameter = None
        parameters[parameter_name] = parameter

    generation_order: list[str] = _determine_generation_order(parameters)

    return parameters, generation_order


def _determine_generation_order(parameters: dict[str, MLParameter | None]) -> list[str]:
    g = nx.DiGraph()
    g.add_nodes_from(parameters.keys())

    # Add the edges.
    for parameter_name, parameter_object in parameters.items():
        if parameter_object is None:
            continue
        for dep_name in parameter_object.var_dep:
            if dep_name == parameter_name:
                raise ConstraintValidationError(
                    f"Parameter {parameter_name} has dependency on it self."
                )

            if dep_name not in parameters:
                raise ConstraintValidationError(
                    f"Dependency {dep_name} does not exist in parameters."
                )

            dep_object = parameters[dep_name]
            if dep_object is None:
                raise ConstraintValidationError(
                    f"Dependency object for parameter {dep_name} is None."
                )

            parameter_object.parameter_dependencies[dep_name] = dep_object
            g.add_edge(dep_name, parameter_name)

    try:
        generation_order = list(nx.topological_sort(g))
        LOGGER.debug("Generation order: %s", generation_order)
        return generation_order
    except Exception as e:
        raise ConstraintValidationError(f"Could not generate generation order: {e}") from e
