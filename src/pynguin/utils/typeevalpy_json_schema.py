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

import astroid

from astroid import Arguments
from astroid import AssignName

import pynguin.configuration as config

from pynguin.analyses.typesystem import AnyType
from pynguin.analyses.typesystem import InferredSignature
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import TupleType
from pynguin.analyses.typesystem import TypeVisitor
from pynguin.analyses.typesystem import UnionType
from pynguin.analyses.typesystem import Unsupported
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod


if typing.TYPE_CHECKING:
    from pynguin.analyses.module import CallableData
    from pynguin.analyses.module import SignatureInfo
    from pynguin.analyses.module import TypeGuessingStats
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
    from pynguin.utils.orderedset import OrderedSet

AstroidFunctionDef: typing.TypeAlias = astroid.AsyncFunctionDef | astroid.FunctionDef


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaElement(ABC):  # noqa: B024
    """A base class for all the TypeEvalPy schema element classes."""


@dataclasses.dataclass(frozen=True)
class TypeEvalPySchemaLocalVariable(TypeEvalPySchemaElement):
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
class TypeEvalPySchemaLocalVariableInsideFunction(TypeEvalPySchemaElement):
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
class TypeEvalPySchemaParameter(TypeEvalPySchemaElement):
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
class TypeEvalPySchemaFunctionReturn(TypeEvalPySchemaElement):
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
    schema_elements: list[TypeEvalPySchemaElement] = []

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
