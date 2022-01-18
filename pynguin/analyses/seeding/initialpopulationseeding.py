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
from typing import TYPE_CHECKING, AnyStr

import pynguin.analyses.seeding.testimport.ast_to_statement as ats
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testfactory as tf
import pynguin.utils.statistics.statistics as stat
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
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
        self, module_path: AnyStr | "os.PathLike[AnyStr]"
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

    def collect_testcases(self, module_path: AnyStr | "os.PathLike[AnyStr]") -> None:
        """Collect all test cases from a module.

        Args:
            module_path: Path to the module to collect the test cases from
        """
        tree = self.get_ast_tree(module_path)
        if tree is None:
            config.configuration.seeding.initial_population_seeding = False
            self._logger.info("Provided testcases are not used.")
            return
        transformer = ats.AstToTestCaseTransformer(
            self._test_cluster,
            config.configuration.test_case_output.assertion_generation
            != config.AssertionGenerator.NONE,
        )
        transformer.visit(tree)
        self._testcases = transformer.testcases
        stat.track_output_variable(RuntimeVariable.FoundTestCases, len(self._testcases))
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


initialpopulationseeding = _InitialPopulationSeeding()
