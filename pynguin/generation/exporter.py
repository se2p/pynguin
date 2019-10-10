# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Implements a very simple exporter for the generated tests."""
import ast
import logging
import numbers
import os
from typing import List, Union, Any

import astor  # type: ignore

from pynguin.utils.statements import Sequence, Assignment, Name, Call, Attribute

LOGGER = logging.getLogger(__name__)


def export_sequences(
    sequences: List[Sequence],
    module_names: List[str],
    path: Union[str, os.PathLike] = "",
) -> ast.Module:
    """Exports a list of sequences to files.

    :param sequences:
    :param module_names:
    :param path:
    :return:
    """
    import_node = _create_ast_imports(module_names)
    functions = _create_functions(sequences)

    module = ast.Module(body=[import_node] + functions)
    if path:
        _save_ast_to_file(module, path)
    return module


def _create_ast_imports(module_names: List[str]) -> ast.Import:
    imports = set()
    for module in module_names:
        alias_node = ast.alias(name=module, asname=None)
        imports.add(alias_node)
    import_node = ast.Import(names=imports)
    return import_node


def _create_functions(sequences: List[Sequence]):
    functions = []
    for i, sequence in enumerate(sequences):
        nodes = _create_statement_nodes(sequence)
        function_name = f"test_case_{i}"
        function_node = _create_function_node(function_name, nodes)
        functions.append(function_node)
    return functions


def _create_statement_nodes(sequence: Sequence) -> List[ast.AST]:
    statements: List[ast.AST] = []
    for statement in sequence:
        if isinstance(statement, Assignment):
            assert isinstance(statement.rhs, Call)
            assert isinstance(statement.lhs, Name)
            if isinstance(statement.rhs.function, Name):
                function_name = statement.rhs.function.identifier
                identifier = statement.lhs.identifier
                arguments = _get_function_arguments(statement.rhs.arguments)

                function_name_node = ast.Name(id=function_name, ctx=ast.Load())
                call_node = ast.Call(
                    func=function_name_node, args=arguments, keywords=[]
                )
                ident_node = ast.Name(id=identifier, ctx=ast.Store())
                assign_node = ast.Assign(targets=[ident_node], value=call_node)
                statements.append(assign_node)
            else:
                assert isinstance(statement.rhs.function, Attribute)
                function_name = statement.rhs.function.attribute_name
                callee_name = statement.rhs.function.owner.identifier
                arguments = _get_function_arguments(statement.rhs.arguments)

                object_name = ast.Name(id=callee_name, ctx=ast.Load())
                attribute_node = ast.Attribute(
                    value=object_name, attr=function_name, ctx=ast.Load()
                )
                call_node = ast.Call(func=attribute_node, args=arguments, keywords=[])
                expression_node = ast.Expr(value=call_node)
                statements.append(expression_node)

        elif isinstance(statement, Call):
            if isinstance(statement.function, Name):
                identifier = statement.function.identifier
                arguments = _get_function_arguments(statement.arguments)

                object_name = ast.Name(id=identifier, ctx=ast.Load())
                call_node = ast.Call(func=object_name, args=arguments, keywords=[])
                expression_node = ast.Expr(value=call_node)
            else:
                assert isinstance(statement.function, Attribute)
                identifier = statement.function.owner.identifier
                method_name = statement.function.attribute_name
                arguments = _get_function_arguments(statement.arguments)

                object_name = ast.Name(id=identifier, ctx=ast.Load())
                attribute_node = ast.Attribute(
                    value=object_name, attr=method_name, ctx=ast.Load()
                )
                call_node = ast.Call(func=attribute_node, args=arguments, keywords=[])
                expression_node = ast.Expr(value=call_node)
            statements.append(expression_node)
        else:
            LOGGER.debug("Found un-exportable constructs: %s", statement)
    return statements


def _get_function_arguments(arguments: List[Any]) -> List[ast.AST]:
    result: List[ast.AST] = []
    for argument in arguments:
        if isinstance(argument, Name):
            new_value = ast.Name(id=argument.identifier, ctx=ast.Load())
            result.append(new_value)
        else:
            # TODO(sl) this is not complete as it does not work for bytes, at the
            # moment the generator does not work with bytes either, so we skip those
            # for the moment
            new_value: ast.AST = None  # type: ignore
            if isinstance(argument, bool):
                new_value = ast.NameConstant(value=argument)  # type: ignore
            elif isinstance(argument, str):
                new_value = ast.Str(s=argument)  # type: ignore
            elif isinstance(argument, numbers.Number):
                new_value = ast.Num(n=2)  # type: ignore
            else:
                LOGGER.debug("Missing case of argument %s", repr(argument))
            result.append(new_value)
    return result


def _create_function_node(function_name: str, nodes: List[ast.AST]) -> ast.FunctionDef:
    function_node = ast.FunctionDef(
        name="test_" + function_name,
        args=ast.arguments(
            args=[], defaults=[], vararg=None, kwarg=None, kwonlyargs=[], kw_defaults=[]
        ),
        body=nodes,
        decorator_list=[],
        returns=None,
    )
    return function_node


def _save_ast_to_file(module: ast.Module, path: Union[str, os.PathLike]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode="w") as file:
        file.write(astor.to_source(module))
