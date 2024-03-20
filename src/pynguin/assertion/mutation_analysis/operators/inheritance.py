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
from pynguin.assertion.mutation_analysis.operators.base import MutationResign, MutationOperator, copy_node


class AbstractOverriddenElementModification(MutationOperator):
    def is_overridden(self, node, name=None):
        if not isinstance(node.parent, ast.ClassDef):
            raise MutationResign()
        if not name:
            name = node.name
        parent = node.parent
        parent_names = []
        while parent:
            if not isinstance(parent, ast.Module):
                parent_names.append(parent.name)
            if not isinstance(parent, ast.ClassDef) and not isinstance(parent, ast.Module):
                raise MutationResign()
            parent = parent.parent
        getattr_rec = lambda obj, attr: functools.reduce(getattr, attr, obj)
        try:
            klass = getattr_rec(self.module, reversed(parent_names))
        except AttributeError:
            raise MutationResign()
        for base_klass in type.mro(klass)[1:-1]:
            if hasattr(base_klass, name):
                return True
        return False


class HidingVariableDeletion(AbstractOverriddenElementModification):
    def mutate_Assign(self, node):
        if len(node.targets) > 1:
            raise MutationResign()
        if isinstance(node.targets[0], ast.Name) and self.is_overridden(node, name=node.targets[0].id):
            return ast.Pass()
        elif isinstance(node.targets[0], ast.Tuple) and isinstance(node.value, ast.Tuple):
            return self.mutate_unpack(node)
        else:
            raise MutationResign()

    def mutate_unpack(self, node):
        target = node.targets[0]
        value = node.value
        new_targets = []
        new_values = []
        for target_element, value_element in zip(target.elts, value.elts):
            if not self.is_overridden(node, getattr(target_element, 'id', None)):
                new_targets.append(target_element)
                new_values.append(value_element)
        if len(new_targets) == len(target.elts):
            raise MutationResign()
        if not new_targets:
            return ast.Pass()
        elif len(new_targets) == 1:
            node.targets = new_targets
            node.value = new_values[0]
            return node
        else:
            target.elts = new_targets
            value.elts = new_values
            return node

    @classmethod
    def name(cls):
        return 'IHD'


class AbstractSuperCallingModification(MutationOperator):
    def is_super_call(self, node, stmt):
        return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and \
               isinstance(stmt.value.func, ast.Attribute) and isinstance(stmt.value.func.value, ast.Call) and \
               isinstance(stmt.value.func.value.func, ast.Name) and stmt.value.func.value.func.id == 'super' and \
               stmt.value.func.attr == node.name

    def should_mutate(self, node):
        return isinstance(node.parent, ast.ClassDef)

    def get_super_call(self, node):
        for index, stmt in enumerate(node.body):
            if self.is_super_call(node, stmt):
                break
        else:
            return None, None
        return index, stmt


class OverriddenMethodCallingPositionChange(AbstractSuperCallingModification):
    def should_mutate(self, node):
        return super().should_mutate(node) and len(node.body) > 1

    @copy_node
    def mutate_FunctionDef(self, node):
        if not self.should_mutate(node):
            raise MutationResign()
        index, stmt = self.get_super_call(node)
        if index is None:
            raise MutationResign()
        super_call = node.body[index]
        del node.body[index]
        if index == 0:
            self.set_lineno(super_call, node.body[-1].lineno)
            self.shift_lines(node.body, -1)
            node.body.append(super_call)
        else:
            self.set_lineno(super_call, node.body[0].lineno)
            self.shift_lines(node.body, 1)
            node.body.insert(0, super_call)
        return node

    @classmethod
    def name(cls):
        return 'IOP'


class OverridingMethodDeletion(AbstractOverriddenElementModification):
    def mutate_FunctionDef(self, node):
        if self.is_overridden(node):
            return ast.Pass()
        raise MutationResign()

    @classmethod
    def name(cls):
        return 'IOD'


class SuperCallingDeletion(AbstractSuperCallingModification):
    @copy_node
    def mutate_FunctionDef(self, node):
        if not self.should_mutate(node):
            raise MutationResign()
        index, _ = self.get_super_call(node)
        if index is None:
            raise MutationResign()
        node.body[index] = ast.Pass(lineno=node.body[index].lineno)
        return node


class SuperCallingInsertPython27(AbstractSuperCallingModification, AbstractOverriddenElementModification):
    __python_version__ = (2, 7)

    def should_mutate(self, node):
        return super().should_mutate(node) and self.is_overridden(node)

    @copy_node
    def mutate_FunctionDef(self, node):
        if not self.should_mutate(node):
            raise MutationResign()
        index, stmt = self.get_super_call(node)
        if index is not None:
            raise MutationResign()
        node.body.insert(0, self.create_super_call(node))
        self.shift_lines(node.body[1:], 1)
        return node

    @copy_node
    def create_super_call(self, node):
        super_call = utils.create_ast('super().{}()'.format(node.name)).body[0]
        for arg in node.args.args[1:-len(node.args.defaults) or None]:
            super_call.value.args.append(ast.Name(id=arg.arg, ctx=ast.Load()))
        for arg, default in zip(node.args.args[-len(node.args.defaults):], node.args.defaults):
            super_call.value.keywords.append(ast.keyword(arg=arg.arg, value=default))
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            super_call.value.keywords.append(ast.keyword(arg=arg.arg, value=default))
        if node.args.vararg:
            self.add_vararg_to_super_call(super_call, node.args.vararg)
        if node.args.kwarg:
            self.add_kwarg_to_super_call(super_call, node.args.kwarg)
        self.set_lineno(super_call, node.body[0].lineno)
        return super_call

    @staticmethod
    def add_kwarg_to_super_call(super_call, kwarg):
        super_call.value.kwargs = ast.Name(id=kwarg, ctx=ast.Load())

    @staticmethod
    def add_vararg_to_super_call(super_call, vararg):
        super_call.value.starargs = ast.Name(id=vararg, ctx=ast.Load())

    @classmethod
    def name(cls):
        return 'SCI'


class SuperCallingInsertPython35(SuperCallingInsertPython27):
    __python_version__ = (3, 5)

    @staticmethod
    def add_kwarg_to_super_call(super_call, kwarg):
        super_call.value.keywords.append(ast.keyword(arg=None, value=ast.Name(id=kwarg.arg, ctx=ast.Load())))

    @staticmethod
    def add_vararg_to_super_call(super_call, vararg):
        super_call.value.args.append(ast.Starred(ctx=ast.Load(), value=ast.Name(id=vararg.arg, ctx=ast.Load())))
