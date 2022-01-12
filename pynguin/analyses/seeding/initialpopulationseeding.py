#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements seeding of the initial population with previously existing testcases."""
from __future__ import annotations

import ast
import logging
import os
from typing import TYPE_CHECKING, Any, AnyStr

import pynguin.analyses.seeding.testimport.ast_to_statement as ats
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testfactory as tf
import pynguin.utils.statistics.statistics as stat
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.variablereference as vr
    from pynguin.setup.testcluster import TestCluster


class _InitialPopulationSeeding:
    """Class for seeding the initial population with previously existing testcases."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._testcases: list[dtc.DefaultTestCase] = []
        self._test_cluster: TestCluster

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
        self, module_path: AnyStr | os.PathLike[AnyStr]
    ) -> ast.Module | None:
        """Returns the ast tree from a module

        Args:
            module_path: The path to the project's root

        Returns:
            The ast tree of the given module.
        """
        module_name = config.configuration.module_name.rsplit(".", maxsplit=1)[-1]
        self._logger.debug("Module name: %s", module_name)
        result: list[AnyStr] = []
        for root, _, files in os.walk(module_path):
            for name in files:
                assert isinstance(name, str)
                if module_name in name and "test_" in name:
                    result.append(os.path.join(root, name))
                    break
        try:
            if len(result) > 0:
                self._logger.debug("Module name found: %s", result[0])
                stat.track_output_variable(RuntimeVariable.SuitableTestModule, True)
                with open(result[0], encoding="utf-8") as module_file:
                    return ast.parse(module_file.read())
            else:
                self._logger.debug("No suitable test module found.")
                stat.track_output_variable(RuntimeVariable.SuitableTestModule, False)
                return None
        except BaseException as exception:  # pylint: disable=broad-except
            self._logger.exception("Cannot read module: %s", exception)
            stat.track_output_variable(RuntimeVariable.SuitableTestModule, False)
            return None

    def collect_testcases(self, module_path: AnyStr | os.PathLike[AnyStr]) -> None:
        """Collect all test cases from a module.

        Args:
            module_path: Path to the module to collect the test cases from
        """
        tree = self.get_ast_tree(module_path)
        if tree is None:
            config.configuration.seeding.initial_population_seeding = False
            self._logger.info("Provided testcases are not used.")
            return
        transformer = _TestTransformer(self._test_cluster)
        transformer.visit(tree)
        self._testcases = transformer.testcases
        if not self._testcases:
            config.configuration.seeding.initial_population_seeding = False
            self._logger.info("None of the provided test cases can be parsed.")
        else:
            self._logger.info(
                "Number successfully collected test cases: %s", len(self._testcases)
            )
        stat.track_output_variable(
            RuntimeVariable.CollectedTestCases, len(self._testcases)
        )
        self._mutate_testcases_initially()

    def _mutate_testcases_initially(self):
        """Mutates the initial population."""
        test_factory = tf.TestFactory(self.test_cluster)
        for _ in range(0, config.configuration.seeding.initial_population_mutations):
            for testcase in self._testcases:
                testcase_wrapper = tcc.TestCaseChromosome(testcase, test_factory)
                testcase_wrapper.mutate()
                if not testcase_wrapper.test_case.statements:
                    self._testcases.remove(testcase)

    @property
    def seeded_testcase(self) -> dtc.DefaultTestCase:
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
    def __init__(self, test_cluster: TestCluster):
        self._current_testcase: dtc.DefaultTestCase = dtc.DefaultTestCase()
        self._current_parsable: bool = True
        self._var_refs: dict[str, vr.VariableReference] = {}
        self._testcases: list[dtc.DefaultTestCase] = []
        self._number_found_testcases: int = 0
        self._test_cluster = test_cluster

    def visit_Module(self, node: ast.Module) -> Any:
        self.generic_visit(node)
        stat.track_output_variable(
            RuntimeVariable.FoundTestCases, self._number_found_testcases
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._number_found_testcases += 1
        self._current_testcase = dtc.DefaultTestCase()
        self._current_parsable = True
        self._var_refs.clear()
        self.generic_visit(node)
        if self._current_parsable:
            self._testcases.append(self._current_testcase)

    def visit_Assign(self, node: ast.Assign) -> Any:
        if self._current_parsable:
            if (
                result := ats.create_assign_stmt(
                    node, self._current_testcase, self._var_refs, self._test_cluster
                )
            ) is None:
                self._current_parsable = False
            else:
                ref_id, stmt = result
                # TODO(fk) not every statement creates a variable.
                var_ref = self._current_testcase.add_variable_creating_statement(stmt)
                self._var_refs[ref_id] = var_ref

    def visit_Assert(self, node: ast.Assert) -> Any:
        if (
            self._current_parsable
            and config.configuration.test_case_output.assertion_generation
            != config.AssertionGenerator.NONE
        ):
            if (result := ats.create_assert_stmt(self._var_refs, node)) is not None:
                assertion, var_ref = result
                self._current_testcase.get_statement(
                    var_ref.get_statement_position()
                ).add_assertion(assertion)

    @property
    def testcases(self) -> list[dtc.DefaultTestCase]:
        """Provides the transformed testcases.

        Returns:
            The transformed testcases.
        """
        return self._testcases


initialpopulationseeding = _InitialPopulationSeeding()
