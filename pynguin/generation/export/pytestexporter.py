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
"""An exported implementation creating PyTest test cases from the statements."""
import ast
import numbers
import os
from typing import List, Any, Union

from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.utils.statements import (
    StatementVisitor,
    Expression,
    Name,
    Attribute,
    Call,
    Assignment,
    Sequence,
)


# pylint: disable=unsubscriptable-object, no-self-use
class _PyTestExportStatementVisitor(StatementVisitor["ast.AST"]):
    """A statement visitor that generates AST nodes for exporting PyTest-style tests."""

    def visit_expression(self, expression: Expression) -> ast.AST:
        """Generates AST nodes for an Expression.

        :param expression: The Expression node
        :return: The corresponding AST node
        """
        raise Exception("Not implemented handling for expression : " + str(expression))

    def visit_name(self, name: Name) -> ast.AST:
        """Generates AST nodes for a Name.

        :param name: The Name node
        :return: The corresponding AST node
        """
        identifier = name.identifier
        name_node = ast.Name(id=identifier, ctx=ast.Load())
        return name_node

    def visit_attribute(self, attribute: Attribute) -> ast.AST:
        """Generates AST nodes for an Attribute.

        :param attribute: The Attribute node
        :return: The corresponding AST node
        """
        name_node = self.visit_name(attribute.owner)
        attribute_name = attribute.attribute_name
        attribute_node = ast.Attribute(
            value=name_node, attr=attribute_name, ctx=ast.Load()
        )
        return attribute_node

    def visit_call(self, call: Call) -> ast.AST:
        """Generates AST nodes for a Call.

        :param call: The Call node
        :return: The corresponding AST node
        """
        # The simple Call node without assignment needs to be wrapped in an Expression
        expr_node = ast.Expr(value=self._visit_call(call))
        return expr_node

    def _visit_call(self, call: Call) -> ast.AST:
        if isinstance(call.function, Name):
            function_node = self.visit_name(call.function)
        elif isinstance(call.function, Attribute):
            function_node = self.visit_attribute(call.function)
        else:
            raise Exception("Unknown function type " + str(call.function))

        arguments = self._visit_function_arguments(call.arguments)

        call_node = ast.Call(func=function_node, args=arguments, keywords=[])
        return call_node

    def visit_assignment(self, assignment: Assignment) -> ast.AST:
        """Generates AST nodes for an Assignment.

        :param assignment: The Assignment node
        :return: The corresponding AST node
        """
        assert isinstance(assignment.lhs, Name)
        assert isinstance(assignment.rhs, Call)
        lhs = self.visit_name(assignment.lhs)
        rhs = self._visit_call(assignment.rhs)
        assign_node = ast.Assign(targets=[lhs], value=rhs)
        return assign_node

    def _visit_function_arguments(self, arguments: List[Any]) -> List[ast.AST]:
        result: List[ast.AST] = []
        for argument in arguments:
            if isinstance(argument, Name):
                node = self.visit_name(argument)
            else:
                # TODO(sl) this is not complete as it does not work for bytes; at the
                # moment the generator does not work with bytes anyway, so we skip
                # those for the moment
                node: ast.AST = None  # type: ignore
                if isinstance(argument, bool):
                    node = ast.NameConstant(value=argument)  # type: ignore
                elif isinstance(argument, str):
                    node = ast.Str(s=argument)  # type: ignore
                elif isinstance(argument, numbers.Number):
                    node = ast.Num(n=2)  # type: ignore
                else:
                    raise Exception("Missing case of argument " + repr(argument))
            result.append(node)
        return result


class PyTestExporter(AbstractTestExporter):
    """An exporter for PyTest-style test cases."""

    def __init__(
        self, module_names: List[str], path: Union[str, os.PathLike] = ""
    ) -> None:
        super().__init__(path)
        self._module_names = module_names

    def export_sequences(self, sequences: List[Sequence]) -> ast.Module:
        """Exports a list of sequences to files.

        :param sequences:
        :return:
        """
        import_node = self._create_ast_imports()
        functions = self._create_functions(sequences)
        module = ast.Module(body=[import_node] + functions)  # type: ignore
        if self._path:
            self.save_ast_to_file(module)
        return module

    def _create_ast_imports(self) -> ast.Import:
        imports = set()
        for module in self._module_names:
            alias_node = ast.alias(name=module, asname=None)
            imports.add(alias_node)
        import_node = ast.Import(names=imports)
        return import_node

    def _create_functions(self, sequences: List[Sequence]) -> List[ast.FunctionDef]:
        functions: List[ast.FunctionDef] = []
        for i, sequence in enumerate(sequences):
            nodes = self._create_statement_nodes(sequence)
            function_name = f"case_{i}"
            function_node = self._create_function_node(function_name, nodes)
            functions.append(function_node)
        return functions

    @staticmethod
    def _create_statement_nodes(sequence: Sequence) -> List[ast.AST]:
        statements: List[ast.AST] = []
        export_visitor = _PyTestExportStatementVisitor()
        for statement in sequence:
            nodes = statement.accept(export_visitor)
            statements.append(nodes)
        return statements

    @staticmethod
    def _create_function_node(
        function_name: str, nodes: List[ast.AST]
    ) -> ast.FunctionDef:
        function_node = ast.FunctionDef(
            name=f"test_{function_name}",
            args=ast.arguments(
                args=[],
                defaults=[],
                vararg=None,
                kwarg=None,
                kwonlyargs=[],
                kw_defaults=[],
            ),
            body=nodes,
            decorator_list=[],
            returns=None,
        )
        return function_node
