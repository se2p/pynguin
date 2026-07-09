#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a Large Language Model (LLM) assertion generator."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat
from pynguin.assertion.assertiongenerator import MutationAnalysisAssertionGenerator
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.parsing.deserializer import parse_assertion
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import ModuleTestCluster

_logger = logging.getLogger(__name__)


def extract_assertions(input_str: str) -> list[str]:
    """Extract assertions from the input string.

    Args:
        input_str (str): The input string containing multiple lines,
        some of which may be assertions.

    Returns:
        list[str]: A list of strings, each containing an extracted assertion.
    """
    # Use regex to find all lines starting with 'assert' (ignoring leading whitespace)
    return re.findall(r"^\s*assert.*", input_str, flags=re.MULTILINE)


def _binding_index(test_case: tc.TestCase) -> dict[str, type | None]:
    """Map bound variable names to their (best-effort) type, last binding wins.

    Args:
        test_case: The test case to index.

    Returns:
        The mapping from bound variable name to type.
    """
    index: dict[str, type | None] = {}
    for statement in test_case.statements():
        if statement.bound_variable is not None:
            index[statement.bound_variable] = statement.bound_type
    return index


def _last_binding_index(test_case: tc.TestCase, var: str) -> int | None:
    """Return the index of the last statement binding *var*, if any.

    Args:
        test_case: The test case to search.
        var: The variable name to look for.

    Returns:
        The statement index, or ``None`` if *var* is never bound.
    """
    for index in range(test_case.size() - 1, -1, -1):
        if test_case.get_statement(index).bound_variable == var:
            return index
    return None


class LLMAssertionGenerator(cv.ChromosomeVisitor):
    """An assertion generator using a Large Language Model (LLM).

    This class generates regression assertions for test cases using an LLM.
    Because the internal representation renders statements back to their
    actual ``var_N`` source, the LLM's returned ``assert`` lines refer to the
    same names already used in the test case: no re-deserialization of the
    whole test and no reference-copying is required.
    """

    def __init__(self, test_cluster: ModuleTestCluster, model: LLMAgent | None = None):
        """Initialize the LLMAssertionGenerator with the given test cluster.

        Args:
            test_cluster (TestCluster): The test cluster used for generating assertions.
            model (LLMAgent): The LLM model to use for generating assertions.
        """
        self._model = model if model is not None else LLMAgent()
        self._test_cluster = test_cluster

    def visit_test_case_chromosome(self, chromosome: tcc.TestCaseChromosome) -> None:
        """Process a test case chromosome to add assertions.

        Args:
            chromosome (tcc.TestCaseChromosome): The test case chromosome to process.
        """
        self._add_assertions_for([chromosome.test_case])

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        """Process a test suite chromosome to add assertions.

        Args:
            chromosome (tsc.TestSuiteChromosome): The test suite chromosome to process.
        """
        self._add_assertions_for([chrom.test_case for chrom in chromosome.test_case_chromosomes])

    def _add_assertions_for(self, test_cases: list[tc.TestCase]) -> None:
        """Add assertions for the given list of test cases.

        Queries the LLM with the rendered test-case source, extracts
        ``assert`` lines from the response, and attaches each parseable one
        to the statement that (last) bound the referenced variable.

        Args:
            test_cases (list[tc.TestCase]): The test cases to add assertions for.
        """
        total_assertions_added = 0
        total_assertions_from_llm = 0
        for test_case in test_cases:
            if test_case.size() == 0:
                continue
            code = test_case.to_test_function().code
            response = self._model.generate_assertions_for_test_case(code)
            if response is None:
                continue
            extracted_assertions = extract_assertions(response)
            total_assertions_from_llm += len(extracted_assertions)
            known_vars = _binding_index(test_case)
            for line in extracted_assertions:
                parsed = parse_assertion(line, known_vars)
                if parsed is None:
                    continue
                var, assertion = parsed
                index = _last_binding_index(test_case, var)
                if index is None:
                    continue
                test_case.get_statement(index).assertions.append(assertion)
                total_assertions_added += 1

        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalAssertionsAddedFromLLM, total_assertions_added
        )
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalAssertionsReceivedFromLLM, total_assertions_from_llm
        )


class MutationAnalysisLLMAssertionGenerator(MutationAnalysisAssertionGenerator):
    """Uses mutation analysis to filter out less relevant assertions."""

    def _add_assertions(self, test_cases: list[tc.TestCase]):
        super()._handle_add_assertions(test_cases)
