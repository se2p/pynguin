#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Implements initial-population seeding from previously existing test cases.

Turning a test module's source into ``TestCase`` objects is the same problem the
LLM subsystem solves when deserializing LLM-emitted code, so this module reuses
:class:`~pynguin.large_language_model.parsing.deserializer.CstStatementDeserializer`
for the per-function parse/validate/normalize core instead of duplicating it.

Unlike LLM-flattened code -- where a rewriter pre-pass hoists the SUT import into
every function -- a seed module (or a Pynguin-exported test suite) imports the
module under test once at module level. Because ``CstStatementDeserializer`` only
looks for SUT imports within each function body, this module first normalizes SUT
references across the whole module via
:func:`~pynguin.large_language_model.parsing.deserializer.normalize_sut_references`
before handing each ``FunctionDef`` to
:meth:`CstStatementDeserializer.deserialize_function`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, AnyStr

import libcst as cst

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.testcase as tc
import pynguin.utils.statistics.stats as stat
from pynguin.large_language_model.parsing.deserializer import (
    CstStatementDeserializer,
    normalize_sut_references,
)
from pynguin.utils import randomness
from pynguin.utils.naming import get_module_alias
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.testfactory as tf
    from pynguin.analyses.module import ModuleTestCluster

logger = logging.getLogger(__name__)


class InitialPopulationProvider:
    """Class for seeding the initial population with previously existing testcases."""

    def __init__(
        self,
        test_cluster: ModuleTestCluster,
        test_factory: tf.TestFactory,
    ):
        """Create new population provider.

        Args:
            test_cluster: Test cluster used to construct test cases
            test_factory: Test factory used to construct test cases
        """
        self._testcases: list[tc.TestCase] = []
        self._test_cluster: ModuleTestCluster = test_cluster
        self._test_factory: tf.TestFactory = test_factory

    @staticmethod
    def _read_module_source(module_path: AnyStr | os.PathLike[AnyStr]) -> str | None:
        """Locate and read the source of a suitable seed/test module.

        Args:
            module_path: The path to the project's root

        Returns:
            The source code of the matching module, or ``None`` if none was found.
        """
        module_name = config.configuration.module_name.rsplit(".", maxsplit=1)[-1]
        logger.debug("Module name: %s", module_name)
        result: list[Path] = []
        for root, _, files in os.walk(module_path):
            root_path = Path(root).resolve()  # type: ignore[arg-type]
            for name in files:
                assert isinstance(name, str)
                if module_name in name and "test_" in name:
                    result.append(root_path / name)
                    break
        try:
            if len(result) > 0:
                logger.debug("Module name found: %s", result[0])
                stat.track_output_variable(RuntimeVariable.SuitableTestModule, value=True)
                with result[0].open(mode="r", encoding="utf-8") as module_file:
                    return module_file.read()
            logger.debug("No suitable test module found.")
            stat.track_output_variable(RuntimeVariable.SuitableTestModule, value=False)
            return None
        except BaseException as exception:
            logger.exception("Cannot read module: %s", exception)
            stat.track_output_variable(RuntimeVariable.SuitableTestModule, value=False)
            return None

    def collect_testcases(self, module_path: AnyStr | os.PathLike[AnyStr]) -> None:
        """Collect all test cases from a module.

        Args:
            module_path: Path to the module to collect the test cases from
        """
        source = self._read_module_source(module_path)
        if source is None:
            logger.info("Provided testcases are not used.")
            return
        create_assertions = (
            config.configuration.test_case_output.assertion_generation
            != config.AssertionGenerator.NONE
        )
        self._testcases = parse_seed_module(
            source, self._test_cluster, create_assertions=create_assertions
        )
        stat.track_output_variable(RuntimeVariable.FoundTestCases, len(self._testcases))
        stat.track_output_variable(RuntimeVariable.CollectedTestCases, len(self._testcases))
        self._mutate_testcases_initially()

    def _mutate_testcases_initially(self) -> None:
        """Mutates the initial population."""
        for _ in range(config.configuration.seeding.initial_population_mutations):
            for testcase in list(self._testcases):
                testcase_wrapper = tcc.TestCaseChromosome(testcase, self._test_factory)
                testcase_wrapper.mutate()
                if not testcase_wrapper.test_case.statements():
                    self._testcases.remove(testcase)

    def random_testcase(self) -> tc.TestCase:
        """Provides a random seeded test case.

        Returns:
            A random test case
        """
        return randomness.choice(self._testcases)

    def __len__(self) -> int:
        """Number of parsed test cases.

        Returns:
            Number of parsed test cases
        """
        return len(self._testcases)


def parse_seed_module(
    source: str,
    test_cluster: ModuleTestCluster,
    *,
    create_assertions: bool,
) -> list[tc.TestCase]:
    """Parse a whole test module's source into ``TestCase`` objects.

    Every top-level ``FunctionDef`` named ``test_*``/``seed_test_*`` is parsed
    independently via :class:`CstStatementDeserializer`; a function contributes
    a test case only if at least one of its statements could be admitted. A
    function is not required to be *fully* parsable to contribute a partial
    test case -- see ``CstStatementDeserializer`` for the admission rules.

    Args:
        source: The source code of the module to parse.
        test_cluster: The test cluster used to resolve calls into the module
            under test.
        create_assertions: Whether to lift ``assert`` statements into
            ``Assertion`` objects.

    Returns:
        The list of parsed test cases (possibly empty).
    """
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError:
        logger.exception("Could not parse provided test module.")
        return []

    module_name = config.configuration.module_name
    module_alias = get_module_alias(module_name)
    normalized = normalize_sut_references(module, module_name, module_alias)

    deserializer = CstStatementDeserializer(test_cluster, create_assertions=create_assertions)
    testcases: list[tc.TestCase] = []
    for node in normalized.body:
        if not isinstance(node, cst.FunctionDef):
            continue
        if not node.name.value.startswith(("test_", "seed_test_")):
            continue
        testcase, _total, _parsed, _uninterpreted = deserializer.deserialize_function(node)
        if testcase.size() > 0:
            testcases.append(testcase)
            logger.debug("Successfully imported %s.", node.name.value)
        else:
            logger.debug("Failed to parse %s.", node.name.value)
    return testcases
