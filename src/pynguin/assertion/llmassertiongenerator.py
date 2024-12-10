#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a Large Language Model (LLM) assertion generator."""

import logging
import re

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.statistics.statistics as stat

from pynguin.assertion.assertion import FloatAssertion
from pynguin.assertion.assertion import IsInstanceAssertion
from pynguin.assertion.assertion import ObjectAssertion
from pynguin.large_language_model.llmagent import OpenAIModel
from pynguin.large_language_model.parsing.deserializer import (
    deserialize_code_to_testcases,
)
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


_LOGGER = logging.getLogger(__name__)


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


def copy_test_case_references(  # noqa: C901
    original: tc.TestCase, target: tc.TestCase, refs_replacement_dict: dict
):
    """Copy references from the original test case to the target test case.

    Args:
        original (tc.TestCase): The original test case to copy references from.
        target (tc.TestCase): The target test case to update references in.
        refs_replacement_dict (dict): A dictionary mapping original references
        to replacements.
    """
    for target_statement in target.statements:
        original_statement = original.statements[target_statement.get_position()]

        if hasattr(target_statement, "ret_val") and hasattr(
            original_statement, "ret_val"
        ):
            target_ret_val = target_statement.ret_val
            original_ret_val = original_statement.ret_val
            refs_replacement_dict[target_ret_val] = original_ret_val
            target_statement.ret_val = original_ret_val

        if hasattr(target_statement, "callee") and hasattr(
            original_statement, "callee"
        ):
            target_callee = target_statement.callee
            original_callee = original_statement.callee
            # Check if already replaced
            if target_callee in refs_replacement_dict:
                target_statement.callee = refs_replacement_dict[target_callee]
            else:
                # Replace the whole instance and store in dictionary
                refs_replacement_dict[target_callee] = original_callee
                target_statement.callee = original_callee

        if hasattr(target_statement, "args") and hasattr(original_statement, "args"):
            for arg_key, target_arg_value in target_statement.args.items():
                original_arg_value = original_statement.args.get(arg_key)
                # Check if already replaced
                if target_arg_value in refs_replacement_dict:
                    target_statement.args[arg_key] = refs_replacement_dict[
                        target_arg_value
                    ]
                else:
                    # Replace the whole instance and store in dictionary
                    refs_replacement_dict[target_arg_value] = original_arg_value
                    target_statement.args[arg_key] = original_arg_value

        if hasattr(target_statement, "assertions"):
            new_assertions: OrderedSet = OrderedSet()
            for target_assertion in target_statement.assertions:
                target_source: vr.Reference | None = None
                if isinstance(target_assertion.source, vr.VariableReference):  # type: ignore[attr-defined]
                    target_source = target_assertion.source  # type: ignore[attr-defined]
                    if target_assertion.source in refs_replacement_dict:  # type: ignore[attr-defined]
                        target_source = refs_replacement_dict[target_assertion.source]  # type: ignore[attr-defined]
                if isinstance(target_assertion.source, vr.FieldReference):  # type: ignore[attr-defined]
                    ref = target_assertion.source  # type: ignore[attr-defined]
                    var_ref = ref.get_variable_reference()
                    if var_ref in refs_replacement_dict:
                        target_source = vr.FieldReference(
                            refs_replacement_dict[var_ref], ref.field
                        )
                # Check if already replaced
                if target_source:
                    # Replace the assertion with a new ObjectAssertion using
                    # the replaced source
                    if isinstance(target_assertion, FloatAssertion):
                        new_assertion = FloatAssertion(
                            target_source, target_assertion.value
                        )
                    elif isinstance(target_assertion, IsInstanceAssertion):
                        new_assertion = IsInstanceAssertion(  # type: ignore[assignment]
                            target_source, target_assertion.expected_type
                        )
                    else:
                        new_assertion = ObjectAssertion(  # type: ignore[assignment]
                            target_source, target_assertion.object  # type: ignore[attr-defined]
                        )
                    new_assertions.add(new_assertion)
                else:
                    # Keep the original assertion if no replacement is found
                    new_assertions.add(target_assertion)
            target_statement.assertions = new_assertions


class LLMAssertionGenerator(cv.ChromosomeVisitor):
    """An assertion generator using a Large Language Model (LLM).

    This class generates regression assertions for test cases using an LLM.
    """

    def __init__(self, test_cluster):
        """Initialize the LLMAssertionGenerator with the given test cluster.

        Args:
            test_cluster (TestCluster): The test cluster used for generating assertions.
        """
        self._model = OpenAIModel()
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
        self._add_assertions_for(
            [chrom.test_case for chrom in chromosome.test_case_chromosomes]
        )

    def _add_assertions_for(self, test_cases: list[tc.TestCase]):
        """Add assertions for the given list of test cases.

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
                    new_test_case_source_code = (
                        test_case_source_code + "\n" + indented_assertions
                    )
                    result = deserialize_code_to_testcases(
                        test_file_contents=new_test_case_source_code,
                        test_cluster=self._test_cluster,
                    )
                    if result is None:
                        logging.error(
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
                        copy_test_case_references(
                            test_case, deserialized_test_case, refs_replacement_dict
                        )
                        for statement in deserialized_test_case.statements:
                            if len(statement.assertions):
                                original_statement = test_case.statements[
                                    statement.get_position()
                                ]
                                total_assertions_added += len(statement.assertions)
                                original_statement.assertions = statement.assertions

        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalAssertionsAddedFromLLM, total_assertions_added
        )
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalAssertionsReceivedFromLLM, total_assertions_from_llm
        )
