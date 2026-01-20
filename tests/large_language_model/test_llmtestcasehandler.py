#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the LLMTestCaseHandler class."""

from unittest.mock import MagicMock, patch

import pytest

import pynguin.configuration as config
from pynguin.analyses.module import generate_test_cluster
from pynguin.ga.computations import BranchDistanceTestSuiteFitnessFunction
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.llmtestcasehandler import LLMTestCaseHandler
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.utils.openai_key_resolver import is_api_key_present


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


LLM_RESPONSE_2 = """
# LLM generated and rewritten (in Pynguin format) test cases
# Date and time: ...

To create unit tests for the `Queue` class in the provided module, ...

```python
import pytest
from queue_example import Queue  # Adjust the import based on the actual path.

def test_queue_initialization():
    # Test initialization with valid size
    q = Queue(5)
    assert q.max == 5
    assert q.size == 0
    assert q.head == 0
    assert q.tail == 0

    # Test initialization with invalid size
    with pytest.raises(AssertionError):
        Queue(0)
    with pytest.raises(AssertionError):
        Queue(-1)
```

### Explanation of Unit Tests
..."""

EXPECTED_2 = """def test_generated_function():
    int_0 = 5
    queue_0 = module_0.Queue(int_0)
    var_0 = queue_0.max
    var_1 = var_0 == int_0
    assert var_1 is True
    var_2 = queue_0.size
    int_1 = 0
    var_3 = var_2 == int_1
    assert var_3 is True
    var_4 = queue_0.head
    var_5 = var_4 == int_1
    assert var_5 is True
    var_6 = queue_0.tail
    var_7 = var_6 == int_1
    assert var_7 is True
    int_2 = 0
    queue_1 = module_0.Queue(int_2)
    int_3 = -1
    queue_2 = module_0.Queue(int_3)"""


@pytest.mark.skipif(
    not is_api_key_present(),
    reason="OpenAI API key is not provided in the configuration.",
)
@pytest.mark.parametrize(
    ("llm_response", "expected_unparsed"), [(LLM_RESPONSE, EXPECTED), (LLM_RESPONSE_2, EXPECTED_2)]
)
def test_integration_get_test_case_chromosomes(executor_mock, llm_response, expected_unparsed):
    test_cluster = generate_test_cluster("tests.fixtures.examples.queue")
    test_factory = MagicMock()
    fitness_function = BranchDistanceTestSuiteFitnessFunction(executor_mock)
    coverage_function = MagicMock()
    model = LLMAgent()
    handler = LLMTestCaseHandler(model)
    config.configuration.test_case_output.assertion_generation = config.AssertionGenerator.LLM

    test_case_crs = handler.get_test_case_chromosomes_from_llm_results(
        llm_response,
        test_cluster,
        test_factory,
        [fitness_function],
        [coverage_function],
    )

    unparsed = unparse_test_case(test_case_crs[0].test_case)

    assert unparsed == expected_unparsed
