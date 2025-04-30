#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.assertion.assertion as ass
import pynguin.large_language_model.helpers.testcasereferencecopier as trc
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr

from pynguin.analyses.module import generate_test_cluster
from pynguin.assertion.assertiongenerator import InstrumentedMutationController
from pynguin.assertion.llmassertiongenerator import LLMAssertionGenerator
from pynguin.assertion.llmassertiongenerator import (
    MutationAnalysisLLMAssertionGenerator,
)
from pynguin.assertion.llmassertiongenerator import extract_assertions
from pynguin.assertion.llmassertiongenerator import indent_assertions
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.orderedset import OrderedSet


def test_extract_assertions():
    input_str = """
x = 5
assert x == 5

def foo():
    y = 10
    assert y > 5
    print("Done")
"""
    expected_assertions = ["assert x == 5", "    assert y > 5"]
    assert extract_assertions(input_str) == expected_assertions


def test_indent_assertions():
    assertions_list = ["assert x == 5", "assert y > 5"]
    expected_result = "    assert x == 5\n    assert y > 5"
    assert indent_assertions(assertions_list) == expected_result


@pytest.fixture
def llm_agent():
    model = MagicMock(LLMAgent)
    model.generate_assertions_for_test_case.return_value = """assert True
x = 1
assert x == 1"""
    return model


@pytest.fixture
def test_case_chromosome():
    test_case_chromosome = MagicMock()
    test_case_chromosome.test_case = MagicMock(spec=tc.TestCase)
    return test_case_chromosome


def create_test_case():
    """Helper function to create a mock TestCase with one statement and one assertion."""
    test_case = MagicMock(spec=tc.TestCase)
    test_case_statement = MagicMock(spec=stmt.Statement)
    test_case_statement.get_position.return_value = 0
    test_case.statements = [test_case_statement]

    test_case_statement.assertions = [MagicMock(spec=ass.Assertion)]
    test_case_statement.assertions[0].source = MagicMock(spec=vr.VariableReference)
    test_case_statement.assertions[0].object = MagicMock()

    return test_case


@pytest.fixture
def test_case_from_llm():
    return create_test_case()


@pytest.fixture
def llm_assertion_generator(llm_agent):
    test_cluster = generate_test_cluster("tests.fixtures.grammar.parameters")
    return LLMAssertionGenerator(test_cluster, llm_agent)


def test_llm_assertion_generator(llm_assertion_generator, test_case_chromosome, test_case_from_llm):
    with patch(
        "pynguin.assertion.llmassertiongenerator.deserialize_code_to_testcases"
    ) as deserialize_mock:
        deserialize_mock.return_value = ([test_case_from_llm], None, None, None)

        # Adds the assertion statements from test_case_from_llm to the
        # test_case_chromosome
        llm_assertion_generator.visit_test_case_chromosome(test_case_chromosome)

        # Assert that the assertions are added correctly
        assert (
            test_case_chromosome.test_case.statements[0].assertions[0].object
            == test_case_from_llm.statements[0].assertions[0].object
        )
        assert (
            test_case_chromosome.test_case.statements[0].assertions[0].source
            == test_case_from_llm.statements[0].assertions[0].source
        )


def test_visit_test_suite_chromosome(
    llm_assertion_generator, test_case_chromosome, test_case_from_llm
):
    with patch(
        "pynguin.assertion.llmassertiongenerator.deserialize_code_to_testcases"
    ) as deserialize_mock:
        deserialize_mock.return_value = ([test_case_from_llm], None, None, None)

        # Create a test suite chromosome with the test case chromosome
        test_suite_chromosome = TestSuiteChromosome()
        test_suite_chromosome.add_test_case_chromosome(test_case_chromosome)

        # Call the method to test
        llm_assertion_generator.visit_test_suite_chromosome(test_suite_chromosome)

        # Assert that the assertions are added correctly
        assert (
            test_case_chromosome.test_case.statements[0].assertions[0].object
            == test_case_from_llm.statements[0].assertions[0].object
        )
        assert (
            test_case_chromosome.test_case.statements[0].assertions[0].source
            == test_case_from_llm.statements[0].assertions[0].source
        )


def test_deserialize_failure(llm_assertion_generator, test_case_chromosome):
    with (
        patch(
            "pynguin.assertion.llmassertiongenerator.deserialize_code_to_testcases"
        ) as deserialize_mock,
        patch("pynguin.assertion.llmassertiongenerator._logger") as logger_mock,
    ):
        # Set up the mock to return None, simulating a deserialization failure
        deserialize_mock.return_value = None

        # Call the method to test
        llm_assertion_generator.visit_test_case_chromosome(test_case_chromosome)

        # Verify that the error was logged
        logger_mock.error.assert_called_once()

        # Verify that execution continued without raising an exception
        # This is implicit since we reached this point without an exception


def create_mock_test_case():
    test_case = MagicMock(spec=tc.TestCase)
    var_ref = MagicMock(spec=vr.VariableReference)
    statement = MagicMock(spec=stmt.Statement)

    statement.get_position.return_value = 0
    statement.ret_val = var_ref
    statement.callee = var_ref
    statement.args = {"arg1": var_ref}
    statement.assertions = OrderedSet([ass.ObjectAssertion(var_ref, object())])

    test_case.statements = [statement]

    return test_case, var_ref


def test_copy_test_case_references():
    original_test_case, original_var_ref = create_mock_test_case()
    target_test_case, target_var_ref = create_mock_test_case()

    refs_replacement_dict = {}
    trc.TestCaseReferenceCopier(original_test_case, target_test_case, refs_replacement_dict).copy()

    target_statement = target_test_case.statements[0]

    assert refs_replacement_dict[target_var_ref] == original_var_ref
    assert target_statement.ret_val == original_var_ref
    assert target_statement.callee == original_var_ref
    assert target_statement.args["arg1"] == original_var_ref
    assert len(target_statement.assertions) == 1
    assert next(iter(target_statement.assertions)).source == original_var_ref


def test_mutation_analysis_llm_assertion_generator():
    # Create mock objects for the required arguments
    plain_executor = MagicMock(spec=TestCaseExecutor)
    mutation_controller = MagicMock(spec=InstrumentedMutationController)

    # Create a mock for the parent class's _handle_add_assertions method
    with patch(
        "pynguin.assertion.assertiongenerator.MutationAnalysisAssertionGenerator._handle_add_assertions"
    ) as mock_handle_add_assertions:
        # Create an instance of MutationAnalysisLLMAssertionGenerator with the required arguments
        generator = MutationAnalysisLLMAssertionGenerator(
            plain_executor=plain_executor, mutation_controller=mutation_controller
        )

        # Create a mock test case
        test_case = MagicMock(spec=tc.TestCase)

        # Call the _add_assertions method
        generator._add_assertions([test_case])

        # Verify that the parent class's _handle_add_assertions method was called with the test case
        mock_handle_add_assertions.assert_called_once_with([test_case])
