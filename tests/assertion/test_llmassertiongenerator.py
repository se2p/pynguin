from unittest.mock import MagicMock, patch

import pytest

from pynguin.analyses.module import generate_test_cluster
from pynguin.assertion.llmassertiongenerator import (extract_assertions,
                                                     indent_assertions, \
                                                     LLMAssertionGenerator,
                                                     copy_test_case_references)
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
from pynguin.large_language_model.llmagent import LLMAgent
import pynguin.testcase.statement as stmt
import pynguin.assertion.assertion as ass
import pynguin.testcase.variablereference as vr
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


# @pytest.fixture
# def test_case_chromosome() -> tcc.TestCaseChromosome:
#     chromosome = MagicMock(spec=tcc.TestCaseChromosome)
#
#     test_case = MagicMock(spec=tc.TestCase)
#     chromosome.test_case = test_case
#
#     test_case_statement = MagicMock(stmt.Statement)
#     test_case_statement.get_position.return_value = 0
#     test_case.statements = [test_case_statement]
#
#     test_case_statement_assertion = MagicMock(ass.Assertion)
#     test_case_statement.assertions = [test_case_statement_assertion]
#
#     test_case_statement_assertion_source = MagicMock(vr.VariableReference)
#     test_case_statement_assertion.source = test_case_statement_assertion_source
#
#     test_case_statement_assertion_object = MagicMock()
#     test_case_statement_assertion.object = test_case_statement_assertion_object
#
#     return chromosome
#
#
# @pytest.fixture
# def test_suite_chromosome() -> tsc.TestSuiteChromosome:
#     chromosome = MagicMock(tsc.TestSuiteChromosome)
#     return chromosome


@pytest.fixture
def llm_agent():
    model = MagicMock(LLMAgent)
    model.generate_assertions_for_test_case.return_value = """assert True
x = 1
assert x == 1"""
    return model


def test_llm_assertion_generator(llm_agent):
    test_case_chromosome = MagicMock(spec=tcc.TestCaseChromosome)

    test_case = MagicMock(spec=tc.TestCase)
    test_case_chromosome.test_case = test_case

    test_case_statement = MagicMock(stmt.Statement)
    test_case_statement.get_position.return_value = 0
    test_case.statements = [test_case_statement]

    test_case_statement_assertion = MagicMock(ass.Assertion)
    test_case_statement.assertions = [test_case_statement_assertion]

    test_case_statement_assertion_source = MagicMock(vr.VariableReference)
    test_case_statement_assertion.source = test_case_statement_assertion_source

    test_case_statement_assertion_object = MagicMock()
    test_case_statement_assertion.object = test_case_statement_assertion_object

    test_case_2 = MagicMock(spec=tc.TestCase)

    test_case_statement_2 = MagicMock(spec=stmt.Statement)
    test_case_statement_2.get_position.return_value = 0
    test_case_2.statements = [test_case_statement_2]

    test_case_statement_assertion_2 = MagicMock(ass.Assertion)
    test_case_statement_2.assertions = [test_case_statement_assertion_2]

    test_case_statement_assertion_source_2 = MagicMock(vr.VariableReference)
    test_case_statement_assertion_2.source = test_case_statement_assertion_source_2

    test_case_statement_assertion_object_2 = MagicMock()
    test_case_statement_assertion_2.object = test_case_statement_assertion_object_2

    test_cluster = generate_test_cluster("tests.fixtures.grammar.parameters")
    llm_assertion_generator = LLMAssertionGenerator(test_cluster, llm_agent)
    with (patch(
            'pynguin.assertion.llmassertiongenerator.deserialize_code_to_testcases') as
    deserialize_mock):
        deserialize_mock.return_value = ([test_case_2], None, None, None)
        llm_assertion_generator.visit_test_case_chromosome(test_case_chromosome)

        assert (test_case_statement.assertions[0].object ==
                test_case_statement_assertion_object_2)
        assert (test_case_statement.assertions[0].source
                == test_case_statement_assertion_source_2)


def test_copy_test_case_references():
    # Create mock original and target test cases
    original_test_case = MagicMock(spec=tc.TestCase)
    target_test_case = MagicMock(spec=tc.TestCase)

    # Create mock variable references
    original_var_ref = MagicMock(spec=vr.VariableReference)
    target_var_ref = MagicMock(spec=vr.VariableReference)

    # Create mock statements
    original_statement = MagicMock(spec=stmt.Statement)
    target_statement = MagicMock(spec=stmt.Statement)

    # Setup statements to return positions correctly
    original_statement.get_position.return_value = 0
    target_statement.get_position.return_value = 0

    # Assign return values (ret_val) to statements
    original_statement.ret_val = original_var_ref
    target_statement.ret_val = target_var_ref

    # Assign function call references (callee)
    original_statement.callee = original_var_ref
    target_statement.callee = target_var_ref

    # Assign function arguments
    original_statement.args = {"arg1": original_var_ref}
    target_statement.args = {"arg1": target_var_ref}

    # Assign assertions with references
    original_assertion = ass.ObjectAssertion(original_var_ref, object())
    target_assertion = ass.ObjectAssertion(target_var_ref, object())

    original_statement.assertions = OrderedSet([original_assertion])
    target_statement.assertions = OrderedSet([target_assertion])

    # Assign statements to test cases
    original_test_case.statements = [original_statement]
    target_test_case.statements = [target_statement]

    # Dictionary to track replacements
    refs_replacement_dict = {}

    # Call function to copy references
    copy_test_case_references(original_test_case, target_test_case, refs_replacement_dict)

    # Assertions to ensure references were copied correctly
    assert refs_replacement_dict[target_var_ref] == original_var_ref
    assert target_statement.ret_val == original_var_ref
    assert target_statement.callee == original_var_ref
    assert target_statement.args["arg1"] == original_var_ref
    assert len(target_statement.assertions) == 1
    assert next(iter(target_statement.assertions)).source == original_var_ref
