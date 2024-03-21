#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/inheritance.py.
"""

import ast
import functools

from pynguin.assertion.mutation_analysis import utils
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, copy_node


class AbstractOverriddenElementModification(MutationOperator):
    def is_overridden(self, node: ast.AST, name: str | None = None) -> bool | None:
        parent = getattr(node, "parent")

        if not isinstance(parent, ast.ClassDef) or not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None

        if not name:
            name = node.name

        parent_names: list[str] = []

        while parent is not None:
            if not isinstance(parent, ast.Module):
                parent_names.append(parent.name)
            if not isinstance(parent, ast.ClassDef) and not isinstance(parent, ast.Module):
                return None
            parent = getattr(parent, "parent")

        getattr_rec = lambda obj, attr: functools.reduce(getattr, attr, obj)

        try:
            klass = getattr_rec(self.module, reversed(parent_names))
        except AttributeError:
            return None

        for base_klass in type.mro(klass)[1:-1]:
            if hasattr(base_klass, name):
                return True

        return False


class HidingVariableDeletion(AbstractOverriddenElementModification):
    def mutate_Assign(self, node: ast.Assign) -> ast.stmt | None:
        if len(node.targets) != 1:
            return None

        first_expression = node.targets[0]

        if isinstance(first_expression, ast.Name):
            overridden = self.is_overridden(node, first_expression.id)

            if overridden is None or not overridden:
                return None

            return ast.Pass()
        elif isinstance(first_expression, ast.Tuple) and isinstance(node.value, ast.Tuple):
            return self.mutate_unpack(node)
        else:
            return None

    def mutate_unpack(self, node: ast.Assign) -> ast.stmt | None:
        if not node.targets:
            return None

        target = node.targets[0]
        value = node.value

        new_targets: list[ast.Name] = []
        new_values: list[ast.expr] = []
        for target_element, value_element in zip(target.elts, value.elts):
            if not isinstance(target_element, ast.Name) or not isinstance(value_element, ast.expr):
                continue

            overridden = self.is_overridden(node, target_element.id)

            if overridden is None:
                return None

            if not overridden:
                new_targets.append(target_element)
                new_values.append(value_element)

        if len(new_targets) == len(target.elts):
            return None

        if not new_targets:
            return ast.Pass()
        elif len(new_targets) == 1 and len(new_values) == 1:
            node.targets = new_targets
            node.value = new_values[0]
            return node
        else:
            target.elts = new_targets
            value.elts = new_values
            return node


class AbstractSuperCallingModification(MutationOperator):
    def is_super_call(self, node: ast.FunctionDef, stmt: ast.stmt) -> bool:
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Call)
            and isinstance(stmt.value.func.value.func, ast.Name)
            and stmt.value.func.value.func.id == 'super'
            and stmt.value.func.attr == node.name
        )

    def should_mutate(self, node: ast.FunctionDef) -> bool:
        parent = getattr(node, "parent")
        return isinstance(parent, ast.ClassDef)

    def get_super_call(self, node: ast.FunctionDef) -> tuple[int, ast.stmt] | None:
        for index, stmt in enumerate(node.body):
            if self.is_super_call(node, stmt):
                return index, stmt
        return None


class OverriddenMethodCallingPositionChange(AbstractSuperCallingModification):
    def should_mutate(self, node: ast.FunctionDef) -> bool:
        return super().should_mutate(node) and len(node.body) > 1

    @copy_node
    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef | None:
        if not self.should_mutate(node) or not node.body:
            return None

        super_call = self.get_super_call(node)

        if super_call is None:
            return None

        index, statement = super_call

        del node.body[index]

        if index == 0:
            self.set_lineno(statement, node.body[-1].lineno)
            self.shift_lines(node.body, -1)
            node.body.append(statement)
        else:
            self.set_lineno(statement, node.body[0].lineno)
            self.shift_lines(node.body, 1)
            node.body.insert(0, statement)

        return node


class OverridingMethodDeletion(AbstractOverriddenElementModification):
    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.Pass | None:
        overridden = self.is_overridden(node)

        if overridden is None or not overridden:
            return None

        return ast.Pass()


class SuperCallingDeletion(AbstractSuperCallingModification):
    @copy_node
    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef | None:
        if not self.should_mutate(node) or not node.body:
            return None

        super_call = self.get_super_call(node)

        if super_call is None:
            return None

        index, _ = super_call

        node.body[index] = ast.Pass(lineno=node.body[index].lineno)

        return node


class SuperCallingInsert(AbstractSuperCallingModification, AbstractOverriddenElementModification):

    @copy_node
    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef | None:
        overridden = self.is_overridden(node)

        if not self.should_mutate(node) or not node.body or overridden is None or not overridden:
            return None

        super_call = self.get_super_call(node)

        if super_call is not None:
            return None

        node.body.insert(0, self.create_super_call(node))
        self.shift_lines(node.body[1:], 1)

        return node

    @copy_node
    def create_super_call(self, node: ast.FunctionDef) -> ast.Expr:
        function_def: ast.FunctionDef = utils.create_ast(f"super().{node.name}()")

        super_call: ast.Expr = function_def.body[0]

        super_call_value: ast.Call = super_call.value

        for arg in node.args.args[1:-len(node.args.defaults) or None]:
            super_call_value.args.append(ast.Name(id=arg.arg, ctx=ast.Load()))

        for arg, default in zip(node.args.args[-len(node.args.defaults):], node.args.defaults):
            super_call_value.keywords.append(ast.keyword(arg=arg.arg, value=default))

        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            super_call_value.keywords.append(ast.keyword(arg=arg.arg, value=default))

        if node.args.vararg is not None:
            self.add_vararg_to_super_call(super_call_value, node.args.vararg)

        if node.args.kwarg is not None:
            self.add_kwarg_to_super_call(super_call_value, node.args.kwarg)

        self.set_lineno(super_call, node.body[0].lineno)

        return super_call

    @staticmethod
    def add_kwarg_to_super_call(super_call_value: ast.Call, kwarg: ast.arg) -> None:
        super_call_value.keywords.append(ast.keyword(arg=None, value=ast.Name(id=kwarg.arg, ctx=ast.Load())))

    @staticmethod
    def add_vararg_to_super_call(super_call_value: ast.Call, vararg: ast.arg) -> None:
        super_call_value.args.append(ast.Starred(ctx=ast.Load(), value=ast.Name(id=vararg.arg, ctx=ast.Load())))
