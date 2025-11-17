# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module holds logic for converting LLM output to test cases and other utils."""

import datetime
import logging
from collections.abc import Iterable
from pathlib import Path

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.stats as stat
from pynguin.analyses.module import TestCluster
from pynguin.ga.computations import CoverageFunction, FitnessFunction
from pynguin.large_language_model.parsing.deserializer import (
    deserialize_code_to_testcases,
)
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.large_language_model.parsing.rewriter import rewrite_tests
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

_logger = logging.getLogger(__name__)


class LLMTestCaseHandler:
    """Class that holds logic for converting LLM output to test cases."""

    def __init__(self, model):
        """Initializes the LLMTestCaseHandler."""
        self._model = model

    def extract_test_cases_from_llm_output(self, llm_output: str) -> str:
        """Extracts test cases from the LLM output.

        Args:
            llm_output: The output from the LLM containing test cases.

        Returns:
            The extracted test cases.
        """
        python_code = self._model.extract_python_code_from_llm_output(llm_output)
        _logger.debug("Extracted Python code: %s.", python_code)
        generated_tests: dict[str, str] = rewrite_tests(python_code)
        tests_with_line_breaks = "\n\n".join(generated_tests.values())
        _logger.debug("Rewritten tests: %s.", tests_with_line_breaks)
        save_llm_tests_to_file(tests_with_line_breaks, "rewritten_llm_test_cases.py")
        return tests_with_line_breaks

    def get_test_case_chromosomes_from_llm_results(
        self,
        llm_query_results: str | None,
        test_cluster: TestCluster,
        test_factory: TestFactory,
        fitness_functions: Iterable[FitnessFunction],
        coverage_functions: Iterable[CoverageFunction],
    ) -> list[tcc.TestCaseChromosome]:
        """Process LLM query results into test case chromosomes.

        Args:
            llm_query_results: The raw string results returned from the LLM.
                If None, no processing will occur, and an empty list will be returned.
            test_cluster: The test cluster to which the generated test cases belong.
                Provides context for deserialization and test case generation.
            test_factory: A factory object used to create instances of `TestCaseChromosome`.
            fitness_functions: An iterable collection of fitness functions
            to attach to each generated chromosome.
                These define objectives for evolutionary algorithms.
            coverage_functions: An iterable collection of coverage functions
            to attach to each generated chromosome.
                These define metrics for evaluating test case coverage.

        Returns:
            A list of `TestCaseChromosome` objects created from the deserialized
             LLM test cases. Each chromosome is augmented with the provided
             fitness and coverage functions.
        """
        llm_test_case_chromosomes: list[tcc.TestCaseChromosome] = []
        if llm_query_results is None:
            return llm_test_case_chromosomes

        save_llm_tests_to_file(llm_query_results, "llm_query_results.txt")
        llm_test_cases_str = self.extract_test_cases_from_llm_output(llm_query_results)

        deserialized_code_to_testcases = deserialize_code_to_testcases(
            llm_test_cases_str, test_cluster=test_cluster
        )

        if deserialized_code_to_testcases is None:
            _logger.error(
                "Failed to deserialize test cases %s",
                llm_test_cases_str,
            )
            return []

        (
            test_cases,
            total_statements,
            parsed_statements,
            uninterpreted_statements,
        ) = deserialized_code_to_testcases

        tests_source_code = "\n\n".join(
            unparse_test_case(test_case) or "" for test_case in test_cases
        )
        save_llm_tests_to_file(tests_source_code, "deserializer_llm_test_cases.py")

        stat.track_output_variable(RuntimeVariable.LLMTotalParsedStatements, parsed_statements)
        stat.track_output_variable(RuntimeVariable.LLMTotalStatements, total_statements)
        stat.track_output_variable(
            RuntimeVariable.LLMUninterpretedStatements, uninterpreted_statements
        )

        for test_case in test_cases:
            test_case_chromosome = _create_test_case_chromosome(
                test_case, test_factory, fitness_functions, coverage_functions
            )
            llm_test_case_chromosomes.append(test_case_chromosome)

        return llm_test_case_chromosomes


def _create_test_case_chromosome(
    test_case,
    test_factory,
    fitness_functions,
    coverage_functions,
):
    test_case_chromosome = tcc.TestCaseChromosome(test_case=test_case, test_factory=test_factory)
    for fitness_function in fitness_functions:
        test_case_chromosome.add_fitness_function(fitness_function)
    for coverage_function in coverage_functions:
        test_case_chromosome.add_coverage_function(coverage_function)
    return test_case_chromosome


def save_llm_tests_to_file(test_cases: str, file_name: str):
    """Save extracted test cases to a Python (.py) file.

    Args:
        file_name: the file name
        test_cases: The test cases to save, formatted as Python code.

    Raises:
        OSError: If there is an issue writing to the file, logs the exception.
    """
    try:
        output_dir = Path(config.configuration.statistics_output.report_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / file_name
        with output_file.open(mode="w", encoding="utf-8") as file:
            file.write("# LLM generated and rewritten (in Pynguin format) test cases\n")
            file.write(
                "# Date and time: "
                + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                + "\n\n"
            )
            file.write(test_cases)
        _logger.info("Test cases saved successfully to %s", output_file)
    except OSError as error:
        _logger.exception("Error while saving LLM-generated test cases to file: %s", error)
