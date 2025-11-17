#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
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
import pynguin.large_language_model.helpers.testcasereferencecopier as trc
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.statistics.stats as stat
from pynguin.assertion.assertiongenerator import MutationAnalysisAssertionGenerator
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.parsing.deserializer import (
    deserialize_code_to_testcases,
)
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.testcase.statement import Statement
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


def indent_assertions(assertions_list: list[str]) -> str:
    """Indent each line of the given assertions list.

    Args:
        assertions_list (list[str]): The list containing assertion strings.

    Returns:
        str: The indented assertions string.
    """
    return "\n".join("    " + assertion.strip() for assertion in assertions_list)


def add_assertions_for_test_case(statement: Statement, test_case: tc.TestCase):
    """Adds assertion to testcase if they exist on the statement."""
    if statement.assertions:
        original_statement = test_case.statements[statement.get_position()]
        original_statement.assertions = statement.assertions


class LLMAssertionGenerator(cv.ChromosomeVisitor):
    """An assertion generator using a Large Language Model (LLM).

    This class generates regression assertions for test cases using an LLM.
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

    def _add_assertions_for(self, test_cases: list[tc.TestCase]):
        """Add assertions for the given list of test cases.

        Generates assertions using the _model. Extracts assertions from the retrieved code
        and deserializes the code into TestCase objects. Copies references from the original
        test cases to the LLM-generated-deserialized ones. Replaces the original assertions
        with the deserialized ones.

        Args:
            test_cases (list[tc.TestCase]): The test cases to add assertions for.
        """
        total_assertions_added = 0
        total_assertions_from_llm = 0
        refs_replacement_dict: dict[vr.Reference, vr.Reference] = {}
        for test_case in test_cases:  # noqa: PLR1702
            test_case_source_code = unparse_test_case(test_case)
            if test_case_source_code is not None:
                python_code: str | None = self._model.generate_assertions_for_test_case(
                    test_case_source_code
                )
                if python_code is not None:
                    extracted_assertions = extract_assertions(python_code)
                    total_assertions_from_llm += len(extracted_assertions)
                    indented_assertions = indent_assertions(extracted_assertions)
                    new_test_case_source_code = test_case_source_code + "\n" + indented_assertions
                    result = deserialize_code_to_testcases(
                        test_file_contents=new_test_case_source_code,
                        test_cluster=self._test_cluster,
                    )
                    if result is None:
                        _logger.error(
                            "Failed to deserialize test case %s",
                            new_test_case_source_code,
                        )
                        continue

                    (
                        tcs,
                        _,
                        _,
                        _,
                    ) = result

                    if tcs and len(tcs) > 0:
                        deserialized_test_case: tc.TestCase = tcs[0]
                        trc.TestCaseReferenceCopier(
                            original=test_case,
                            target=deserialized_test_case,
                            refs_replacement_dict=refs_replacement_dict,
                        ).copy()
                        for statement in deserialized_test_case.statements:
                            if len(statement.assertions):
                                add_assertions_for_test_case(statement, test_case)
                                total_assertions_added += len(statement.assertions)

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
