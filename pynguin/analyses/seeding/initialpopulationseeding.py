#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements seeding of the initial population with previously existing testcases."""
from __future__ import annotations

import ast
import logging
import os
import pynguin.configuration as config
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.analyses.seeding.testimport.ast_to_statement import AstToStatement as ats
from pkgutil import iter_modules
from typing import Any, Optional, Set, Union, List, Dict

from setuptools import find_packages

from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.defaulttestcase import DefaultTestCase
from pynguin.utils import randomness

Types = Union[float, int, str]


class InitialPopulationSeeding:
    """Class for seeding the initial population with previously existing testcases.
    """

    _logger = logging.getLogger(__name__)
    _instance: Optional[InitialPopulationSeeding] = None
    _testcases: List[DefaultTestCase] = []
    _test_cluster: TestCluster = None

    def __new__(cls) -> InitialPopulationSeeding:
        if cls._instance is None:
            cls._instance = super(InitialPopulationSeeding, cls).__new__(cls)
        return cls._instance

    def set_test_cluster(self, test_cluster: TestCluster):
        self._test_cluster = test_cluster

    def get_test_cluster(self) -> TestCluster:
        return self._test_cluster

    @staticmethod
    def _find_modules(project_path: Union[str, os.PathLike]) -> Set[str]:
        modules: Set[str] = set()
        for package in find_packages(
            project_path,
            exclude=[
                "*.tests",
                "*.tests.*",
                "tests.*",
                "tests",
                "test",
                "test.*",
                "*.test.*",
                "*.test",
            ],
        ):
            pkg_path = "{}/{}".format(project_path, package.replace(".", "/"))
            for info in iter_modules([pkg_path]):
                if not info.ispkg:
                    name = info.name.replace(".", "/")
                    package_path = package.replace(".", "/")
                    modules.add(f"{package_path}/{name}.py")
        return modules

    def get_ast_tree(
        self, module_path: Union[str, os.PathLike]
    ) -> ast.Module:
        """Returns the ast tree from a module

        Args:
            module_path: The path to the project's root

        Returns:
            The ast tree of the given module.
        """

        with open(os.path.abspath(module_path)) as module_file:
            try:
                tree = ast.parse(module_file.read())
            except BaseException as exception:  # pylint: disable=broad-except
                self._logger.info("Cannot read module: %s", exception)
                tree = None
        return tree

    def collect_testcases(self, module_path: Union[str, os.PathLike]):
        tree = self.get_ast_tree(module_path)
        if tree is None:
            config.INSTANCE.initial_population_seeding = False
            self._logger.info("Provided testcases are not used.")
            return
        transformer = _TestTransformer()
        transformer.visit(tree)
        self._testcases = transformer.testcases

    @property
    def random_testcase(self) -> DefaultTestCase:
        return self._testcases[randomness.next_int(0, len(self._testcases))]

    @property
    def has_tests(self) -> bool:
        return len(self._testcases) > 0


class _TestTransformer(ast.NodeVisitor):

    _current_testcase: DefaultTestCase = None
    _var_refs: Dict[str, vr.VariableReference] = {}

    def __init__(self):
        self._testcases: List[DefaultTestCase] = []

    def visit_Module(self, node: ast.Module) -> Any:
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._current_testcase = DefaultTestCase()
        self._var_refs = {}
        self._testcases.append(self._current_testcase)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        ref_id, stmt = ats.create_prim_stmt(node, self._current_testcase)
        var_ref = self._current_testcase.add_statement(stmt)
        self._var_refs.update({ref_id: var_ref})

    def visit_Expr(self, node: ast.Expr) -> Any:
        objs_under_test = InitialPopulationSeeding().get_test_cluster().accessible_objects_under_test
        stmt = ats.create_function_stmt(node, self._current_testcase, objs_under_test, self._var_refs)
        self._current_testcase.add_statement(stmt)

    @property
    def testcases(self) -> List[DefaultTestCase]:
        """Provides the transformed testcases.

        Returns:
            The transformed testcases.
        """
        return self._testcases
