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
import pynguin.ga.testcasechromosome as tcc
from pynguin.large_language_model.llmtestcasehandler import LLMTestCaseHandler


@pytest.fixture
def mock_model():
    return MagicMock()


@pytest.fixture
def handler(mock_model):
    return LLMTestCaseHandler(mock_model)


@pytest.fixture
def test_cluster():
    cluster = MagicMock()
    cluster.accessible_objects_under_test = []
    return cluster


@pytest.fixture(autouse=True)
def _report_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.configuration.statistics_output, "report_dir", str(tmp_path))
    return tmp_path


def test_extract_test_cases_from_llm_output(handler, mock_model, tmp_path):
    mock_model.extract_python_code_from_llm_output.return_value = (
        "def test_something():\n    x = 1\n"
    )

    result = handler.extract_test_cases_from_llm_output("LLM raw output")

    assert "def test_something" in result
    mock_model.extract_python_code_from_llm_output.assert_called_once_with("LLM raw output")
    assert (tmp_path / "rewritten_llm_test_cases.py").exists()


def test_get_test_case_chromosomes_from_llm_results_none_returns_empty(handler):
    result = handler.get_test_case_chromosomes_from_llm_results(
        None, MagicMock(), MagicMock(), [], []
    )
    assert result == []


def test_get_test_case_chromosomes_from_llm_results_deserialization_none(
    handler, mock_model, test_cluster
):
    mock_model.extract_python_code_from_llm_output.return_value = "def test_x():\n    x = 1\n"

    with patch(
        "pynguin.large_language_model.llmtestcasehandler.deserialize_code_to_testcases",
        return_value=None,
    ):
        result = handler.get_test_case_chromosomes_from_llm_results(
            "some LLM output", test_cluster, MagicMock(), [], []
        )
    assert result == []


def test_get_test_case_chromosomes_from_llm_results_success(
    handler, mock_model, test_cluster, tmp_path
):
    mock_model.extract_python_code_from_llm_output.return_value = """def test_something():
    x = 1
    y = 2
"""
    test_factory = MagicMock()
    fitness_function = MagicMock()
    fitness_function.is_maximisation_function.return_value = False
    coverage_function = MagicMock()

    result = handler.get_test_case_chromosomes_from_llm_results(
        "raw llm output",
        test_cluster,
        test_factory,
        [fitness_function],
        [coverage_function],
    )

    assert len(result) == 1
    chromosome = result[0]
    assert isinstance(chromosome, tcc.TestCaseChromosome)
    assert chromosome.test_case.size() == 2
    assert fitness_function in chromosome.get_fitness_functions()
    assert coverage_function in chromosome.get_coverage_functions()
    assert (tmp_path / "llm_query_results.txt").exists()
    assert (tmp_path / "deserializer_llm_test_cases.py").exists()


def test_get_test_case_chromosomes_from_llm_results_multiple_test_functions(
    handler, mock_model, test_cluster
):
    mock_model.extract_python_code_from_llm_output.return_value = """def test_one():
    x = 1

def test_two():
    y = 2
"""
    result = handler.get_test_case_chromosomes_from_llm_results(
        "raw", test_cluster, MagicMock(), [], []
    )
    assert len(result) == 2


def test_get_test_case_chromosomes_from_llm_results_no_test_functions(
    handler, mock_model, test_cluster
):
    mock_model.extract_python_code_from_llm_output.return_value = "x = 1\n"
    result = handler.get_test_case_chromosomes_from_llm_results(
        "raw", test_cluster, MagicMock(), [], []
    )
    assert result == []
