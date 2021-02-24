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

import pynguin.analyses.seeding.testimport.ast_to_statement as ats
import pynguin.configuration as config
import pynguin.testcase.variable.variablereference as vr
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.defaulttestcase import DefaultTestCase
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils import randomness


class _InitialPopulationSeeding:
    """Class for seeding the initial population with previously existing testcases."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._testcases: List[DefaultTestCase] = []
        self.test_cluster: TestCluster

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
                self._logger.exception("Cannot read module: %s", exception)
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
        if not self._testcases:
            config.configuration.initial_population_seeding = False
            self._logger.info("None of the provided test cases can be parsed.")
        else:
            self._logger.info(
                "Number successfully collected test cases: %s", len(self._testcases)
            )
        self._mutate_testcases_initially()

    def _mutate_testcases_initially(self):
        """Mutates the initial population."""
        test_factory = TestFactory(self.test_cluster)
        for _ in range(0, config.configuration.initial_population_mutations):
            for testcase in self._testcases:
                testcase_wrapper = TestCaseChromosome(testcase, test_factory)
                testcase_wrapper.mutate()
                if not testcase_wrapper.test_case.statements:
                    self._testcases.remove(testcase)

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
        self._current_parsable: bool = True
        self._var_refs: Dict[str, vr.VariableReference] = {}
        self._testcases: List[DefaultTestCase] = []

    def visit_Module(self, node: ast.Module) -> Any:
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._current_testcase = DefaultTestCase()
        self._current_parsable = True
        self._var_refs.clear()
        self.generic_visit(node)
        if self._current_parsable:
            self._testcases.append(self._current_testcase)

    def visit_Assign(self, node: ast.Assign) -> Any:
        if self._current_parsable:
            ref_id, stmt, self._current_parsable = ats.create_assign_stmt(
                node, self._current_testcase, self._var_refs
            )
            if self._current_parsable:
                assert stmt
                assert ref_id
                var_ref = self._current_testcase.add_statement(stmt)
                self._var_refs[ref_id] = var_ref

    def visit_Assert(self, node: ast.Assert) -> Any:
        if self._current_parsable and config.configuration.generate_assertions:
            assertion, var_ref = ats.create_assert_stmt(self._var_refs, node)
            if assertion is not None:
                assert var_ref
                self._current_testcase.get_statement(
                    var_ref.get_statement_position()
                ).add_assertion(assertion)

    @property
    def testcases(self) -> List[DefaultTestCase]:
        """Provides the transformed testcases.

        Returns:
            The transformed testcases.
        """
        return self._testcases


initialpopulationseeding = _InitialPopulationSeeding()
