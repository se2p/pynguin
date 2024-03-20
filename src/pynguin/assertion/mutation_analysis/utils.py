#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py.
"""

import ast
import copy
import importlib
import inspect
import os
import pkgutil
import random
import sys
import time
import types
from collections import defaultdict

from importlib._bootstrap_external import EXTENSION_SUFFIXES, ExtensionFileLoader


def create_module(ast_node, module_name='mutant', module_dict=None):
    code = compile(ast_node, module_name, 'exec')
    module = types.ModuleType(module_name)
    module.__dict__.update(module_dict or {})
    exec(code, module.__dict__)
    return module


def notmutate(sth):
    return sth


class ModulesLoaderException(Exception):
    def __init__(self, name, exception):
        self.name = name
        self.exception = exception

    def __str__(self):
        return "can't load {}".format(self.name)


class ModulesLoader:
    def __init__(self, names, path):
        self.names = names
        self.path = path or '.'
        self.ensure_in_path(self.path)

    def load(self, without_modules=None, exclude_c_extensions=True):
        results = []
        without_modules = without_modules or []
        for name in self.names:
            results += self.load_single(name)
        for module, to_mutate in results:
            # yield only if module is not explicitly excluded and only source modules (.py) if demanded
            if module not in without_modules and not (exclude_c_extensions and self._is_c_extension(module)):
                yield module, to_mutate

    def load_single(self, name):
        full_path = self.get_full_path(name)
        if os.path.exists(full_path):
            if self.is_file(full_path):
                return self.load_file(full_path)
            elif self.is_directory(full_path):
                return self.load_directory(full_path)
        if self.is_package(name):
            return self.load_package(name)
        else:
            return self.load_module(name)

    def get_full_path(self, name):
        if os.path.isabs(name):
            return name
        return os.path.abspath(os.path.join(self.path, name))

    @staticmethod
    def is_file(name):
        return os.path.isfile(name)

    @staticmethod
    def is_directory(name):
        return os.path.exists(name) and os.path.isdir(name)

    @staticmethod
    def is_package(name):
        try:
            module = importlib.import_module(name)
            return hasattr(module, '__file__') and module.__file__.endswith('__init__.py')
        except ImportError:
            return False
        finally:
            sys.path_importer_cache.clear()

    def load_file(self, name):
        if name.endswith('.py'):
            dirname = os.path.dirname(name)
            self.ensure_in_path(dirname)
            module_name = self.get_filename_without_extension(name)
            return self.load_module(module_name)

    def ensure_in_path(self, directory):
        if directory not in sys.path:
            sys.path.insert(0, directory)

    @staticmethod
    def get_filename_without_extension(path):
        return os.path.basename(os.path.splitext(path)[0])

    @staticmethod
    def load_package(name):
        result = []
        try:
            package = importlib.import_module(name)
            for _, module_name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
                if not ispkg:
                    try:
                        module = importlib.import_module(module_name)
                        result.append((module, None))
                    except ImportError as _:
                        pass
        except ImportError as _:
            pass
        return result

    def load_directory(self, name):
        if os.path.isfile(os.path.join(name, '__init__.py')):
            parent_dir = self._get_parent_directory(name)
            self.ensure_in_path(parent_dir)
            return self.load_package(os.path.basename(name))
        else:
            result = []
            for file in os.listdir(name):
                modules = self.load_single(os.path.join(name, file))
                if modules:
                    result += modules
            return result

    def load_module(self, name):
        module, remainder_path, last_exception = self._split_by_module_and_remainder(name)
        if not self._module_has_member(module, remainder_path):
            raise ModulesLoaderException(name, last_exception)
        return [(module, '.'.join(remainder_path) if remainder_path else None)]

    @staticmethod
    def _get_parent_directory(name):
        parent_dir = os.path.abspath(os.path.join(name, os.pardir))
        return parent_dir

    @staticmethod
    def _split_by_module_and_remainder(name):
        """Takes a path string and returns the contained module and the remaining path after it.

        Example: "mymodule.mysubmodule.MyClass.my_func" -> mysubmodule, "MyClass.my_func"
        """
        module_path = name.split('.')
        member_path = []
        last_exception = None
        while True:
            try:
                module = importlib.import_module('.'.join(module_path))
                break
            except ImportError as error:
                member_path = [module_path.pop()] + member_path
                last_exception = error
                if not module_path:
                    raise ModulesLoaderException(name, last_exception)
        return module, member_path, last_exception

    @staticmethod
    def _module_has_member(module, member_path):
        attr = module
        for part in member_path:
            if hasattr(attr, part):
                attr = getattr(attr, part)
            else:
                return False
        return True

    @staticmethod
    def _is_c_extension(module):
        if isinstance(getattr(module, '__loader__', None), ExtensionFileLoader):
            return True
        module_filename = inspect.getfile(module)
        module_filetype = os.path.splitext(module_filename)[1]
        return module_filetype in EXTENSION_SUFFIXES


class Timer:
    time_provider = time.time

    def __init__(self):
        self.duration = 0
        self.start = self.time_provider()

    def stop(self):
        self.duration = self.time_provider() - self.start
        return self.duration


class TimeRegister:
    executions = defaultdict(float)
    timer_class = Timer
    stack = []

    def __init__(self, method):
        self.method = method

    def __get__(self, obj, ownerClass=None):
        return types.MethodType(self, obj)

    def __call__(self, *args, **kwargs):
        if self.stack and self.stack[-1] == self.method:
            return self.method(*args, **kwargs)

        self.stack.append(self.method)
        time_reg = self.timer_class()
        result = self.method(*args, **kwargs)

        self.executions[self.method.__name__] += time_reg.stop()
        self.stack.pop()
        return result

    @classmethod
    def clean(cls):
        cls.executions.clear()
        cls.stack = []


class RandomSampler:
    def __init__(self, percentage):
        self.percentage = percentage if 0 < percentage < 100 else 100

    def is_mutation_time(self):
        return random.randrange(100) < self.percentage


class ParentNodeTransformer(ast.NodeTransformer):
    def visit(self, node):
        if getattr(node, 'parent', None):
            node = copy.copy(node)
            if hasattr(node, 'lineno'):
                del node.lineno
        node.parent = getattr(self, 'parent', None)
        node.children = []
        self.parent = node
        result_node = super().visit(node)
        self.parent = node.parent
        if self.parent:
            self.parent.children += [node] + node.children
        return result_node


def create_ast(code):
    return ParentNodeTransformer().visit(ast.parse(code))


def is_docstring(node):
    def_node = node.parent.parent
    return (isinstance(def_node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and def_node.body and
            isinstance(def_node.body[0], ast.Expr) and isinstance(def_node.body[0].value, ast.Str) and
            def_node.body[0].value == node)


def get_by_python_version(classes, python_version=sys.version_info):
    candidates = [cls for cls in classes if cls.__python_version__ <= python_version]
    if not candidates:
        raise NotImplementedError('MutPy does not support Python {}.'.format(sys.version))
    return max([candidate for candidate in candidates], key=lambda cls: cls.__python_version__)


def sort_operators(operators):
    return sorted(operators, key=lambda cls: cls.name())
