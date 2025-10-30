#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the LLMTestCaseHandler class."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.analyses.module import generate_test_cluster
from pynguin.ga.computations import BranchDistanceTestSuiteFitnessFunction
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.llmagent import is_api_key_present
from pynguin.large_language_model.llmagent import is_api_key_valid
from pynguin.large_language_model.llmtestcasehandler import LLMTestCaseHandler
from pynguin.large_language_model.parsing.helpers import unparse_test_case


@pytest.fixture
def mock_model():
    return MagicMock()


@pytest.fixture
def handler(mock_model):
    return LLMTestCaseHandler(mock_model)


def test_extract_test_cases_from_llm_output(handler, mock_model):
    mock_model.extract_python_code_from_llm_output.return_value = "some_code"
    with (
        patch("pynguin.large_language_model.llmtestcasehandler.rewrite_tests") as mock_rewrite,
        patch(
            "pynguin.large_language_model.llmtestcasehandler.save_llm_tests_to_file"
        ) as mock_save,
    ):
        mock_rewrite.return_value = {"test1": "def test_something(): pass"}

        result = handler.extract_test_cases_from_llm_output("LLM raw output")

        assert "def test_something()" in result
        mock_model.extract_python_code_from_llm_output.assert_called_once()
        mock_rewrite.assert_called_once_with("some_code")
        mock_save.assert_called_once()


def test_get_test_case_chromosomes_from_llm_results_none_returns_empty(handler):
    result = handler.get_test_case_chromosomes_from_llm_results(
        None, MagicMock(), MagicMock(), [], []
    )
    assert result == []


def test_get_test_case_chromosomes_from_llm_results_deserialization_none(handler, mock_model):
    mock_model.extract_python_code_from_llm_output.return_value = "some_code"

    with (
        patch(
            "pynguin.large_language_model.llmtestcasehandler.rewrite_tests",
            return_value={"test": "code"},
        ),
        patch(
            "pynguin.large_language_model.llmtestcasehandler.deserialize_code_to_testcases",
            return_value=None,
        ),
        patch("pynguin.large_language_model.llmtestcasehandler.save_llm_tests_to_file"),
    ):
        result = handler.get_test_case_chromosomes_from_llm_results(
            "some LLM output", MagicMock(), MagicMock(), [], []
        )
        assert result == []


def test_get_test_case_chromosomes_from_llm_results_success(handler, mock_model):
    mock_model.extract_python_code_from_llm_output.return_value = "some_code"
    test_case = MagicMock()
    test_factory = MagicMock()
    fitness_function = MagicMock()
    coverage_function = MagicMock()
    mock_chromosome = MagicMock()

    with (
        patch(
            "pynguin.large_language_model.llmtestcasehandler.rewrite_tests",
            return_value={"test": "code"},
        ),
        patch(
            "pynguin.large_language_model.llmtestcasehandler.deserialize_code_to_testcases"
        ) as mock_deserialize,
        patch(
            "pynguin.large_language_model.llmtestcasehandler.unparse_test_case", return_value="code"
        ),
        patch("pynguin.large_language_model.llmtestcasehandler.save_llm_tests_to_file"),
        patch(
            "pynguin.large_language_model.llmtestcasehandler.tcc.TestCaseChromosome",
            return_value=mock_chromosome,
        ),
    ):
        mock_deserialize.return_value = ([test_case], 10, 5, 1)

        result = handler.get_test_case_chromosomes_from_llm_results(
            "output",
            MagicMock(),
            test_factory,
            [fitness_function],
            [coverage_function],
        )

        assert len(result) == 1
        assert result[0] == mock_chromosome
        mock_chromosome.add_fitness_function.assert_called_once_with(fitness_function)
        mock_chromosome.add_coverage_function.assert_called_once_with(coverage_function)


LLM_RESPONSE = """
Some LLM text:

```python
import pytest
from queue_example import Queue

def test_initialization():
    queue = Queue(5)
    assert queue.max == 5
```

### Some LLM explanations"""

EXPECTED = """def test_generated_function():
    int_0 = 5
    queue_0 = module_0.Queue(int_0)
    var_0 = queue_0.max
    var_1 = var_0 == int_0
    assert var_1 is True"""


@pytest.mark.skipif(
    not is_api_key_present() or not is_api_key_valid(),
    reason="OpenAI API key is not provided in the configuration.",
)
def test_integration_get_test_case_chromosomes(executor_mock):
    test_cluster = generate_test_cluster("tests.fixtures.examples.queue")
    test_factory = MagicMock()
    fitness_function = BranchDistanceTestSuiteFitnessFunction(executor_mock)
    coverage_function = MagicMock()
    model = LLMAgent()
    handler = LLMTestCaseHandler(model)
    config.configuration.test_case_output.assertion_generation = config.AssertionGenerator.LLM

    result = handler.get_test_case_chromosomes_from_llm_results(
        LLM_RESPONSE,
        test_cluster,
        test_factory,
        [fitness_function],
        [coverage_function],
    )

    unparsed = unparse_test_case(result[0].test_case)

    assert unparsed == EXPECTED
