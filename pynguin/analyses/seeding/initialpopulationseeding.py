#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements seeding of the initial population with previously existing testcases."""
from __future__ import annotations

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Union

import pynguin.configuration as config
import pynguin.testcase.variable.variablereference as vr
from pynguin.analyses.seeding.testimport.ast_to_statement import AstToStatement as AtS
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.defaulttestcase import DefaultTestCase
from pynguin.utils import randomness


class _InitialPopulationSeeding:
    """Class for seeding the initial population with previously existing testcases."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._testcases: List[DefaultTestCase] = []
        self.test_cluster: TestCluster = TestCluster()

    @property
    def test_cluster(self) -> TestCluster:
        """Provides the test cluster.

        Returns:
            The test cluster
        """
        return self._test_cluster

    @test_cluster.setter
    def test_cluster(self, test_cluster: TestCluster):
        self._test_cluster = test_cluster

    def get_ast_tree(
        self, module_path: Union[str, os.PathLike]
    ) -> Optional[ast.Module]:
        """Returns the ast tree from a module

        Args:
            module_path: The path to the project's root

        Returns:
            The ast tree of the given module.
        """

        with open(os.path.abspath(module_path)) as module_file:
            try:
                return ast.parse(module_file.read())
            except BaseException as exception:  # pylint: disable=broad-except
                self._logger.info("Cannot read module: %s", exception)
                return None

    def collect_testcases(self, module_path: Union[str, os.PathLike]) -> None:
        """Collect all test cases from a module.

        Args:
            module_path: Path to the module to collect the test cases from
        """
        tree = self.get_ast_tree(module_path)
        if tree is None:
            config.configuration.initial_population_seeding = False
            self._logger.info("Provided testcases are not used.")
            return
        transformer = _TestTransformer()
        transformer.visit(tree)
        self._testcases = transformer.testcases

    @property
    def seeded_testcase(self) -> DefaultTestCase:
        """Provides a random seeded test case.

        Returns:
            A random test case
        """
        return self._testcases[randomness.next_int(0, len(self._testcases))]

    @property
    def has_tests(self) -> bool:
        """Whether or not test cases have been found.

        Returns:
            Whether or not test cases have been found
        """
        return len(self._testcases) > 0


# pylint: disable=invalid-name, missing-function-docstring
class _TestTransformer(ast.NodeVisitor):

    def __init__(self):
        self._current_testcase: DefaultTestCase = DefaultTestCase()
        self._var_refs: Dict[str, vr.VariableReference] = {}
        self._testcases: List[DefaultTestCase] = []

    def visit_Module(self, node: ast.Module) -> Any:
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._current_testcase = DefaultTestCase()
        self._var_refs.clear()
        self._testcases.append(self._current_testcase)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        ref_id, stmt = AtS.create_assign_stmt(
            node, self._current_testcase, self._var_refs
        )
        if stmt is not None:
            var_ref = self._current_testcase.add_statement(stmt)
            self._var_refs.update({ref_id: var_ref})

    def visit_Assert(self, node: ast.Assert) -> Any:
        if config.configuration.generate_assertions:
            assertion = AtS.create_assert_stmt(self._var_refs, node)
            self._current_testcase.get_statement(
                len(self._current_testcase.statements) - 1
            ).add_assertion(assertion)

    @property
    def testcases(self) -> List[DefaultTestCase]:
        """Provides the transformed testcases.

        Returns:
            The transformed testcases.
        """
        return self._testcases


initialpopulationseeding = _InitialPopulationSeeding()
