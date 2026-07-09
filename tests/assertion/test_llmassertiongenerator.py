#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.testcase as tc
import pynguin.utils.statistics.stats as stat
from pynguin.assertion.assertion import (
    CollectionLengthAssertion,
    FloatAssertion,
    IsInstanceAssertion,
    ObjectAssertion,
)
from pynguin.assertion.assertiongenerator import MutationAnalysisAssertionGenerator
from pynguin.assertion.llmassertiongenerator import (
    LLMAssertionGenerator,
    MutationAnalysisLLMAssertionGenerator,
    extract_assertions,
)
from pynguin.assertion.mutation_analysis.controller import MutationController
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from tests.conftest import _make_statement


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


def test_extract_assertions_no_matches():
    assert extract_assertions("x = 1\ny = 2\n") == []


@pytest.fixture
def test_cluster():
    cluster = MagicMock()
    cluster.accessible_objects_under_test = []
    return cluster


def _build_test_case() -> tc.TestCase:
    """A small hand-built test case: var_0 = 5; var_1 = var_0."""
    test_case = tc.TestCase()
    test_case.add_statement(_make_statement("var_0 = 5", bound_variable="var_0", bound_type=int))
    test_case.add_statement(
        _make_statement("var_1 = var_0", bound_variable="var_1", bound_type=int)
    )
    return test_case


@pytest.fixture
def llm_agent_mock():
    return MagicMock(spec=LLMAgent)


def test_add_assertions_for_test_case_chromosome(test_cluster, llm_agent_mock):
    test_case = _build_test_case()
    llm_agent_mock.generate_assertions_for_test_case.return_value = (
        "assert var_0 == 5\nassert True\nassert var_1 == 5"
    )
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = test_case

    with patch.object(stat, "set_output_variable_for_runtime_variable") as mock_set:
        generator.visit_test_case_chromosome(chromosome)

    llm_agent_mock.generate_assertions_for_test_case.assert_called_once()
    # The generated code that was sent to the model should reference the test
    # case's own var names.
    sent_code = llm_agent_mock.generate_assertions_for_test_case.call_args[0][0]
    assert "var_0" in sent_code
    assert "var_1" in sent_code

    # "assert True" is not a supported shape (test is a Constant, not a Name) and
    # must be skipped.
    assert test_case.get_statement(0).assertions == [ObjectAssertion("var_0", 5)]
    assert test_case.get_statement(1).assertions == [ObjectAssertion("var_1", 5)]

    mock_set.assert_any_call(RuntimeVariable.TotalAssertionsAddedFromLLM, 2)
    mock_set.assert_any_call(RuntimeVariable.TotalAssertionsReceivedFromLLM, 3)


def test_add_assertions_skips_empty_test_case(test_cluster, llm_agent_mock):
    empty_test_case = tc.TestCase()
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = empty_test_case

    generator.visit_test_case_chromosome(chromosome)

    llm_agent_mock.generate_assertions_for_test_case.assert_not_called()


def test_add_assertions_skips_none_response(test_cluster, llm_agent_mock):
    test_case = _build_test_case()
    llm_agent_mock.generate_assertions_for_test_case.return_value = None
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = test_case

    generator.visit_test_case_chromosome(chromosome)

    assert test_case.get_statement(0).assertions == []
    assert test_case.get_statement(1).assertions == []


def test_add_assertions_unparseable_line_is_skipped(test_cluster, llm_agent_mock):
    test_case = _build_test_case()
    llm_agent_mock.generate_assertions_for_test_case.return_value = (
        "assert not a valid python expression at all !!!"
    )
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = test_case

    generator.visit_test_case_chromosome(chromosome)

    assert test_case.get_statement(0).assertions == []
    assert test_case.get_statement(1).assertions == []


def test_add_assertions_unknown_variable_is_skipped(test_cluster, llm_agent_mock):
    test_case = _build_test_case()
    llm_agent_mock.generate_assertions_for_test_case.return_value = "assert unknown_var == 1"
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = test_case

    generator.visit_test_case_chromosome(chromosome)

    assert test_case.get_statement(0).assertions == []
    assert test_case.get_statement(1).assertions == []


def test_add_assertions_various_shapes(test_cluster, llm_agent_mock):
    test_case = tc.TestCase()
    test_case.add_statement(_make_statement("var_0 = 5", bound_variable="var_0", bound_type=int))
    test_case.add_statement(
        _make_statement("var_1 = 2.5", bound_variable="var_1", bound_type=float)
    )
    test_case.add_statement(_make_statement("var_2 = 'hi'", bound_variable="var_2", bound_type=str))
    test_case.add_statement(
        _make_statement("var_3 = [1, 2]", bound_variable="var_3", bound_type=list)
    )
    llm_agent_mock.generate_assertions_for_test_case.return_value = (
        "assert var_0 == 5\n"
        "assert var_1 == 2.5\n"
        "assert isinstance(var_2, str)\n"
        "assert len(var_3) == 2"
    )
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)
    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = test_case

    generator.visit_test_case_chromosome(chromosome)

    assert test_case.get_statement(0).assertions == [ObjectAssertion("var_0", 5)]
    assert test_case.get_statement(1).assertions == [FloatAssertion("var_1", 2.5)]
    assert test_case.get_statement(2).assertions == [
        IsInstanceAssertion("var_2", "builtins", "str")
    ]
    assert test_case.get_statement(3).assertions == [CollectionLengthAssertion("var_3", 2)]


def test_visit_test_suite_chromosome(test_cluster, llm_agent_mock):
    test_case = _build_test_case()
    llm_agent_mock.generate_assertions_for_test_case.return_value = "assert var_0 == 5"
    generator = LLMAssertionGenerator(test_cluster, llm_agent_mock)

    chromosome = MagicMock(spec=tcc.TestCaseChromosome)
    chromosome.test_case = test_case
    test_suite_chromosome = TestSuiteChromosome()
    test_suite_chromosome.add_test_case_chromosome(chromosome)

    generator.visit_test_suite_chromosome(test_suite_chromosome)

    assert test_case.get_statement(0).assertions == [ObjectAssertion("var_0", 5)]


def test_llm_assertion_generator_default_model(test_cluster):
    with patch("pynguin.assertion.llmassertiongenerator.LLMAgent") as mock_agent_cls:
        mock_agent_cls.return_value = MagicMock(spec=LLMAgent)
        generator = LLMAssertionGenerator(test_cluster)
    mock_agent_cls.assert_called_once()
    assert generator._model is mock_agent_cls.return_value


def test_mutation_analysis_llm_assertion_generator():
    plain_executor = MagicMock(spec=TestCaseExecutor)
    mutation_controller = MagicMock(spec=MutationController)

    with patch.object(
        MutationAnalysisAssertionGenerator, "_handle_add_assertions"
    ) as mock_handle_add_assertions:
        generator = MutationAnalysisLLMAssertionGenerator(
            plain_executor=plain_executor, mutation_controller=mutation_controller
        )

        test_case = MagicMock(spec=tc.TestCase)
        generator._add_assertions([test_case])

        mock_handle_add_assertions.assert_called_once_with([test_case])
