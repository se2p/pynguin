#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for managing ML API constraints."""

import importlib
import inspect
import logging

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import networkx as nx
import numpy as np
import yaml  # type: ignore[import-untyped]

import pynguin.configuration as config

from pynguin.configuration import TypeInferenceStrategy
from pynguin.utils.exceptions import ConstraintValidationError
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.pynguinml.mlparameter import MLParameter


if TYPE_CHECKING:
    from types import FunctionType

    from pynguin.analyses.module import ModuleTestCluster


class ConstraintsManager:
    """Singleton class to manage ML API constraints."""

    _logger = logging.getLogger(__name__)

    _instance = None

    def __new__(cls):  # noqa: D102
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the ConstraintsManager instance.

        Sets up the ML testing environment by validating the constraints path and
        loading the datatype mapping.
        """
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._root_path = config.configuration.pynguinml.constraints_path.strip()
        if not self._root_path or not Path(self._root_path).is_dir():
            self._ml_testing_enabled = False
        else:
            self._ml_testing_enabled = True
            self._datatype_map = self._load_dtype_map()

        self._constructor_function: GenericFunction | None = None
        self._nparray_func: GenericFunction | None = None

        self._initialized: bool = True

    def ml_testing_enabled(self) -> bool:
        """Returns if the ML testing environment is enabled."""
        return self._ml_testing_enabled

    def _load_dtype_map(self):
        file_path = config.configuration.pynguinml.dtype_mapping_path.strip()
        try:
            with Path(file_path).open(encoding="utf-8") as f:
                dtype_map = yaml.safe_load(f)
            dtype_map = {k: v for k, v in dtype_map.items() if v is not None}
            for v in dtype_map.values():
                # Verify that it is a NumPy datatype
                np.dtype(v)
            return dtype_map
        except Exception as e:  # noqa: BLE001
            self._logger.warning("Could not load datatype mapping file %s: %s", file_path, e)
            return {}

    def datatype_map(self):
        """Returns the datatype map."""
        return self._datatype_map

    @staticmethod
    def __get_parameter_constraints(constraints: dict, parameter_name: str) -> dict | None:
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

    def load_constructor_function(
        self,
        constructor_function_str: str,
        test_cluster: "ModuleTestCluster",
        type_inference_strategy: TypeInferenceStrategy,
    ) -> None:
        """Dynamically loads a constructor function for tensors.

        Args:
            constructor_function_str: The full path of the constructor function.
            test_cluster: The test cluster for type system usage.
            type_inference_strategy: The type inference strategy to use.
        """
        try:
            # Split the string into module and function parts
            parts = constructor_function_str.split(".")
            module_name, function_path = parts[0], parts[1:]

            module = importlib.import_module(module_name)

            # Traverse to the target function
            func = module
            for attr in function_path:
                func = getattr(func, attr)

            inferred_signature = test_cluster.type_system.infer_type_info(
                cast("FunctionType", func),
                type_inference_strategy=type_inference_strategy,
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

            self._constructor_function = GenericFunction(
                cast("FunctionType", func), inferred_signature, set(), parts[-1]
            )
            self._logger.info(
                "Successfully loaded constructor function: %s", constructor_function_str
            )
        except (ImportError, AttributeError, ValueError) as e:
            self._logger.warning(
                "Failed to load constructor function '%s': %s", constructor_function_str, e
            )

    def load_nparray_function(
        self, test_cluster: "ModuleTestCluster", type_inference_strategy: TypeInferenceStrategy
    ) -> None:
        """Loads the nparray function for generating np.ndarray.

        Args:
            test_cluster: The test cluster for type system usage.
            type_inference_strategy: The type inference strategy to use.
        """
        inferred_signature = test_cluster.type_system.infer_type_info(
            np.array,
            type_inference_strategy=type_inference_strategy,
        )

        # np.array is of type built-in function and therefore inferred_signature will
        # not have the right signature
        signature = inspect.Signature(
            parameters=[
                inspect.Parameter("object", inspect.Parameter.KEYWORD_ONLY),
                inspect.Parameter("dtype", inspect.Parameter.KEYWORD_ONLY),
            ],
            return_annotation=np.ndarray,
        )

        inferred_signature.signature = signature

        self._nparray_func = GenericFunction(
            cast("FunctionType", np.array), inferred_signature, set(), "array"
        )

    def constructor_function(self):
        """Returns the constructor function for building tensors."""
        return self._constructor_function

    def nparray_function(self):
        """Returns the np.array function."""
        return self._nparray_func

    def load_and_process_constraints(
        self, module_name: str, callable_name: str, parameter_names: list[str]
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
        # load yaml constraints file
        yaml_file = Path(self._root_path) / f"{module_name}.{callable_name}.yaml"
        if not Path(yaml_file).exists():
            self._logger.debug(
                "No constraints file found for module %s and callable %s",
                module_name,
                callable_name,
            )
            return {}, []

        try:
            with Path(yaml_file).open(encoding="utf-8") as f:
                constraints_data = yaml.safe_load(f)
        except Exception as e:  # noqa: BLE001
            self._logger.warning("Could not load yaml file %s: %s", yaml_file, e)
            return {}, []

        constraints = constraints_data.get("constraints", {})

        parameters: dict[str, MLParameter | None] = {}

        for parameter_name in parameter_names:
            parameter_constraints = self.__get_parameter_constraints(constraints, parameter_name)
            if parameter_constraints is not None:
                parameter = MLParameter(parameter_name, parameter_constraints, self._datatype_map)
            else:
                parameter = None
            parameters[parameter_name] = parameter

        generation_order: list[str] = self._determine_generation_order(parameters)

        return parameters, generation_order

    def _determine_generation_order(self, parameters: dict[str, MLParameter | None]) -> list[str]:
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
            self._logger.debug("Generation order: %s", generation_order)
            return generation_order
        except Exception as e:
            raise ConstraintValidationError(f"Could not generate generation order: {e}") from e
