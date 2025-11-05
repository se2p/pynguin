#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Contains the dataclasses for the TypeEvalPy JSON export.

These are based on the ``pydantic`` schema provided by ``TypeEvalPy``.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import typing
from abc import ABC
from pathlib import Path

from astroid.nodes import AsyncFunctionDef, FunctionDef

import pynguin.configuration as config
from pynguin.analyses.typesystem import (
    AnyType,
    InferredSignature,
    Instance,
    NoneType,
    TupleType,
    TypeVisitor,
    UnionType,
    Unsupported,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)

if typing.TYPE_CHECKING:
    from astroid.nodes import Arguments, AssignName

    from pynguin.analyses.module import CallableData, SignatureInfo, TypeGuessingStats
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
    from pynguin.utils.orderedset import OrderedSet

AstroidFunctionDef: typing.TypeAlias = AsyncFunctionDef | FunctionDef


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaElement:
    """Data class for a TypeEvalPy schema element."""

    file: str
    line_number: int
    type: list[str]
    col_offset: int | None = None
    variable: str | None = None
    function: str | None = None
    parameter: str | None = None
    all_type_preds: list[list[str]] | None = None


@dataclasses.dataclass(frozen=True)
class ParsedTypeEvalPyData:
    """Container for parsed TypeEvalPy JSON data."""

    elements: list[TypeEvalPySchemaElement]
    """List of all TypeEvalPy schema elements."""

    def get_function_parameters(self, function_name: str) -> dict[str, list[str]]:
        """Get all parameters for a specific function.

        Args:
            function_name: Name of the function

        Returns:
            Dictionary mapping parameter names to their types
        """
        parameters = {}
        for element in self.elements:
            if element.function == function_name and element.parameter is not None:
                parameters[element.parameter] = element.type
        return parameters

    def get_function_return_types(self, function_name: str) -> list[str]:
        """Get return types for a specific function.

        Args:
            function_name: Name of the function

        Returns:
            List of return types for the function
        """
        for element in self.elements:
            if (
                element.function == function_name
                and element.parameter is None
                and element.variable is None
            ):
                return element.type
        return []

    def get_variable_types(self, variable_name: str) -> list[str]:
        """Get types for a specific variable.

        Args:
            variable_name: Name of the variable

        Returns:
            List of types for the variable
        """
        for element in self.elements:
            if element.variable == variable_name:
                return element.type
        return []

    def get_all_functions(self) -> set[str]:
        """Get all function names in the data.

        Returns:
            Set of all function names
        """
        functions = set()
        for element in self.elements:
            if element.function is not None:
                functions.add(element.function)
        return functions

    def get_all_variables(self) -> set[str]:
        """Get all variable names in the data.

        Returns:
            Set of all variable names
        """
        variables = set()
        for element in self.elements:
            if element.variable is not None:
                variables.add(element.variable)
        return variables


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaLocalVariable(ABC):
    """Information about a local variable.

    Attributes:
        file: the name of the file containing this variable
        line_number: the line number of the variable declaration
        col_offset: the column offset of the variable declaration
        type: the list of types suitable for this variable
        variable: the name of the variable
    """

    file: str
    line_number: int
    col_offset: int
    type: list[str]
    variable: str


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaLocalVariableInsideFunction(ABC):
    """Information about a local variable inside a function.

    Attributes:
        file: the name of the file containing this variable
        line_number: the line number of the variable declaration
        col_offset: the column offset of the variable declaration
        type: the list of types suitable for this variable
        function: the name of the function defining the variable
        variable: the name of the variable
    """

    file: str
    line_number: int
    col_offset: int
    type: list[str]
    function: str
    variable: str


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaParameter(ABC):
    """Information about a parameter of a function.

    Attributes:
        file: the name of the file containing this function
        line_number: the line number of the function
        col_offset: the column offset of the function
        type: the list of types suitable for this parameter
        function: the name of the function
        parameter: the name of the parameter
    """

    file: str
    line_number: int
    col_offset: int
    type: list[str]
    function: str
    parameter: str


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaFunctionReturn(ABC):
    """Information about the return type of a function.

    Attributes:
         file: the name of the file containing this function
         line_number: the line number of the function
         col_offset: the column offset of the function
         type: the list of types suitable as return types
         function: the name of the function
    """

    file: str
    line_number: int
    col_offset: int
    type: list[str]
    function: str | None = None


class _TypeExpansionVisitor(TypeVisitor[set[str]]):
    def visit_any_type(self, left: AnyType) -> set[str]:
        return {"Any"}

    def visit_none_type(self, left: NoneType) -> set[str]:
        return {"None"}

    def visit_instance(self, left: Instance) -> set[str]:
        return {left.type.name if left.type.module == "builtins" else left.type.full_name}

    def visit_tuple_type(self, left: TupleType) -> set[str]:
        return {"tuple"}

    def visit_union_type(self, left: UnionType) -> set[str]:
        if len(left.items) == 1:
            return left.items[0].accept(self)
        return {elem for t in left.items for elem in t.accept(self)}

    def visit_unsupported_type(self, left: Unsupported) -> set[str]:
        return {"<?>"}


def convert_parameter(  # noqa: PLR0917
    file_name: str,
    function_node: AstroidFunctionDef,
    parameter_name: str,
    signature: InferredSignature,
    function_name: str,
    signature_info: SignatureInfo | None,
) -> TypeEvalPySchemaParameter:
    """Converts the parameter type of a function's parameter.

    Args:
        file_name: the name of the file defining the function
        function_node: the root node of the function in the AST
        parameter_name: the name of the parameter to convert
        signature: information about the type signature of the function
        function_name: name of the function/method
        signature_info: signature info

    Returns:
        A schema function parameter object for the TypeEvalPy schema
    """

    def find_parameter_node(arguments: Arguments, name: str) -> AssignName:
        for argument in arguments.arguments:
            if argument.name == name:
                return argument
        raise KeyError(f"Could not find an argument with name {name}")

    def format_parameter_types(sig: InferredSignature, param_name: str) -> list[str]:
        result: set[str] = set()
        parameter = sig.signature.parameters.get(param_name)
        visitor = _TypeExpansionVisitor()
        if parameter is not None and parameter.annotation != sig.signature.empty:
            result.update(
                sig.original_parameters[param_name].accept(
                    visitor  # type: ignore[arg-type]
                )
            )
        if config.configuration.type_inference.type_tracing > 0:
            guessed_types = sig.current_guessed_parameters.get(param_name)
            if guessed_types is not None:
                result.update(
                    type_
                    for guessed_type in guessed_types
                    for type_ in guessed_type.accept(visitor)
                )
            if signature_info is not None:
                guessed = signature_info.guessed_parameter_types.get(param_name)
                if guessed is not None:
                    result.update(guessed)
        return sorted(result)

    parameter_node = find_parameter_node(function_node.args, parameter_name)
    line_number = parameter_node.lineno
    col_offset = parameter_node.col_offset + 1  # TODO(sl): check if addition is correct
    types: list[str] = format_parameter_types(signature, parameter_name)
    return TypeEvalPySchemaParameter(
        file=file_name,
        line_number=line_number,
        col_offset=col_offset,
        type=types,
        function=function_name,
        parameter=parameter_name,
    )


def convert_return(
    file_name: str,
    function_node: AstroidFunctionDef,
    signature: InferredSignature,
    function_name: str,
    *,
    is_function: bool,
) -> TypeEvalPySchemaFunctionReturn:
    """Converts the return value of a function.

    Args:
        file_name: the name of the file defining the function
        function_node: the root node of the function in the AST
        signature: information about the type signature of the function
        function_name: name of the function/method
        is_function: whether the callable is a function or a method

    Returns:
        A schema function return object for the TypeEvalPy schema
    """

    def format_return_types(sig: InferredSignature) -> list[str]:
        result: set[str] = set()
        visitor = _TypeExpansionVisitor()
        if sig.signature.return_annotation != sig.signature.empty:
            result.update(
                sig.original_return_type.accept(visitor)  # type: ignore[arg-type]
            )
        if config.configuration.type_inference.type_tracing > 0:
            result.update(sig.return_type.accept(visitor))  # type: ignore[arg-type]
        return sorted(result)

    line_number = function_node.lineno
    if is_function:
        col_offset = function_node.col_offset + len("def ") + 1  # 1-indexed
    else:
        col_offset = function_node.col_offset + 1  # 1-indexed
    types: list[str] = format_return_types(signature)
    return TypeEvalPySchemaFunctionReturn(
        file=file_name,
        line_number=line_number,
        col_offset=col_offset,
        type=types,
        function=function_name,
    )


# Union type for backward compatibility with existing code
TypeEvalPySchemaElementUnion = (
    TypeEvalPySchemaElement
    | TypeEvalPySchemaLocalVariable
    | TypeEvalPySchemaLocalVariableInsideFunction
    | TypeEvalPySchemaParameter
    | TypeEvalPySchemaFunctionReturn
)


def provide_json(
    file_name: str,
    accessibles: OrderedSet[GenericAccessibleObject],
    function_data: dict[GenericAccessibleObject, CallableData],
    stats: TypeGuessingStats,
) -> str:
    """Provide the JSON string representation for the callables in the SUT.

    Args:
        file_name: the name of the file defining the SUT
        accessibles: the set of all accessibles from the SUT
        function_data: a map of accessibles and their respective information from the
                       analyses
        stats: type guessing stats

    Returns:
        JSON string
    """
    schema_elements: list[TypeEvalPySchemaElementUnion] = []

    for accessible in accessibles:
        if not isinstance(accessible, GenericCallableAccessibleObject):
            continue

        callable_data = function_data.get(accessible)

        if isinstance(accessible, GenericConstructor):
            assert accessible.owner is not None
            function_name = f"{accessible.owner.name}.__init__"
        elif isinstance(accessible, GenericMethod):
            function_name = f"{accessible.owner.name}.{accessible.method_name}"
        elif isinstance(accessible, GenericFunction):
            function_name = f"{accessible.function_name}"
        else:
            raise NotImplementedError(f"Missing accessible type {type(accessible)}")

        if callable_data is not None and callable_data.tree is not None:
            signature = accessible.inferred_signature
            tree = callable_data.tree
            name = f"{config.configuration.module_name}.{function_name}"
            signature_info = stats.signature_infos.get(name)
            parameter_jsons = []
            try:
                for parameter in signature.original_parameters:
                    param_json = convert_parameter(
                        file_name, tree, parameter, signature, function_name, signature_info
                    )
                    parameter_jsons.append(param_json)
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not convert parameter for %s: %s",
                    function_name,
                    e,
                )
            schema_elements.extend(parameter_jsons)
            if not accessible.is_constructor():
                return_json = convert_return(
                    file_name,
                    tree,
                    signature,
                    function_name,
                    is_function=accessible.is_function(),
                )
                schema_elements.append(return_json)

    return json.dumps([dataclasses.asdict(schema_element) for schema_element in schema_elements])


def _validate_all_type_preds(all_type_preds: typing.Any) -> list[list[str]] | None:
    """Validate and return all_type_preds if valid, None otherwise.

    Args:
        all_type_preds: The all_type_preds value to validate

    Returns:
        Valid all_type_preds or None if invalid
    """
    if all_type_preds is None:
        return None

    if not isinstance(all_type_preds, list):
        _LOGGER.warning(
            "all_type_preds field must be a list, got %s", type(all_type_preds).__name__
        )
        return None

    # Validate that all_type_preds is a list of lists of strings
    if not all(
        isinstance(pred, list) and all(isinstance(t, str) for t in pred) for pred in all_type_preds
    ):
        _LOGGER.warning("all_type_preds must be a list of lists of strings, skipping field")
        return None

    return all_type_preds


def _parse_schema_element(item: dict[str, typing.Any]) -> TypeEvalPySchemaElement | None:
    """Parse a single schema element from a dictionary.

    Args:
        item: Dictionary containing schema element data

    Returns:
        TypeEvalPySchemaElement if valid, None otherwise
    """
    # Check required fields
    required_fields = ["file", "line_number", "type"]
    missing_fields = [field for field in required_fields if field not in item]
    if missing_fields:
        _LOGGER.warning("Skipping item missing required fields %s: %s", missing_fields, item)
        return None

    type_list = item["type"]
    if not isinstance(type_list, list):
        _LOGGER.warning("Skipping item with non-list type field: %s", item)
        return None

    # Extract and validate all type predictions if present
    all_type_preds = _validate_all_type_preds(item.get("all_type_preds"))

    try:
        return TypeEvalPySchemaElement(
            file=item["file"],
            line_number=item["line_number"],
            type=type_list,
            col_offset=item.get("col_offset"),
            variable=item.get("variable"),
            function=item.get("function"),
            parameter=item.get("parameter"),
            all_type_preds=all_type_preds,
        )
    except (TypeError, ValueError) as e:
        _LOGGER.warning("Failed to create TypeEvalPySchemaElement from %s: %s", item, e)
        return None


def parse_json(json_path: str) -> ParsedTypeEvalPyData:
    """Parse a TypeEvalPy JSON file and extract type information.

    Args:
        json_path: Path to the TypeEvalPy JSON file

    Returns:
        ParsedTypeEvalPyData containing the extracted type information

    Raises:
        FileNotFoundError: If the JSON file does not exist
        json.JSONDecodeError: If the JSON file is malformed
        ValueError: If the JSON structure is not valid TypeEvalPy format
    """
    if not json_path:
        return ParsedTypeEvalPyData(elements=[])

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"TypeEvalPy JSON file not found: {json_path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in TypeEvalPy file {json_path}: {e.msg}", e.doc, e.pos
        ) from e

    if not isinstance(data, list):
        raise ValueError(f"TypeEvalPy JSON file must contain a list, got {type(data).__name__}")

    elements: list[TypeEvalPySchemaElement] = []

    for item in data:
        if not isinstance(item, dict):
            _LOGGER.warning("Skipping non-dict item in TypeEvalPy JSON: %s", item)
            continue

        element = _parse_schema_element(item)
        if element is not None:
            elements.append(element)

    _LOGGER.info("Parsed TypeEvalPy JSON with %d elements", len(elements))

    return ParsedTypeEvalPyData(elements=elements)
