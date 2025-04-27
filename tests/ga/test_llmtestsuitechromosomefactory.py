#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock

import pytest

import pynguin.configuration as config

from pynguin.ga.chromosomefactory import ChromosomeFactory
from pynguin.ga.llmtestsuitechromosomefactory import LLMTestSuiteChromosomeFactory
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def mock_test_case_chromosome():
    chromosome = mock.create_autospec(TestCaseChromosome, instance=True)
    chromosome.clone.return_value = mock.create_autospec(TestCaseChromosome, instance=True)
    return chromosome


@pytest.fixture
def mock_test_case_chromosome_factory(mock_test_case_chromosome):
    factory = mock.create_autospec(ChromosomeFactory, instance=True)
    factory.get_chromosome.return_value = mock_test_case_chromosome
    return factory


@pytest.fixture
def mock_test_factory():
    return mock.create_autospec(TestFactory, instance=True)


@pytest.fixture
def mock_test_cluster():
    return mock.Mock()


@pytest.fixture
def mock_fitness_functions():
    return OrderedSet([mock.Mock(), mock.Mock()])


@pytest.fixture
def mock_coverage_functions():
    return OrderedSet([mock.Mock()])


@pytest.fixture
def llm_factory(
    mock_test_case_chromosome_factory,
    mock_test_factory,
    mock_test_cluster,
    mock_fitness_functions,
    mock_coverage_functions,
):
    return LLMTestSuiteChromosomeFactory(
        test_case_chromosome_factory=mock_test_case_chromosome_factory,
        test_factory=mock_test_factory,
        test_cluster=mock_test_cluster,
        fitness_functions=mock_fitness_functions,
        coverage_functions=mock_coverage_functions,
    )


@pytest.fixture
def patch_llm_agent(monkeypatch):
    mock_agent = mock.create_autospec(LLMAgent, instance=True)
    monkeypatch.setattr("pynguin.ga.llmtestsuitechromosomefactory.LLMAgent", lambda: mock_agent)
    return mock_agent


def test_test_case_chromosome_factory_property(llm_factory, mock_test_case_chromosome_factory):
    assert llm_factory.test_case_chromosome_factory == mock_test_case_chromosome_factory


def test_generate_llm_test_cases_with_results(llm_factory, patch_llm_agent):
    fake_chromosome = mock.create_autospec(TestCaseChromosome, instance=True)
    patch_llm_agent.generate_tests_for_module_under_test.return_value = "fake_results"
    patch_llm_agent.llm_test_case_handler.get_test_case_chromosomes_from_llm_results.return_value = [
        fake_chromosome
    ]

    result = llm_factory._generate_llm_test_cases()
    assert result == [fake_chromosome]
    patch_llm_agent.generate_tests_for_module_under_test.assert_called_once()


def test_generate_llm_test_cases_without_results(llm_factory, patch_llm_agent):
    patch_llm_agent.generate_tests_for_module_under_test.return_value = None

    result = llm_factory._generate_llm_test_cases()
    assert result == []


@pytest.mark.parametrize(
    "llm_count, population, llm_test_cases_length",
    [
        (0.5, 4, 2),  # 50% LLM, 2 LLM cases
        (0.2, 5, 1),  # 20% LLM, 1 LLM case
        (1.0, 2, 2),  # 100% LLM, 2 LLM cases
    ],
)
def test_get_chromosome_with_llm_tests(
    llm_factory,
    patch_llm_agent,
    mock_test_case_chromosome,
    llm_count,
    population,
    llm_test_cases_length,
):
    # Patch configuration
    config.configuration.large_language_model.llm_test_case_percentage = llm_count
    config.configuration.search_algorithm.population = population

    # Patch LLM agent to return some fake test cases
    llm_cases = [
        mock.create_autospec(TestCaseChromosome, instance=True)
        for _ in range(llm_test_cases_length)
    ]
    patch_llm_agent.generate_tests_for_module_under_test.return_value = "results"
    patch_llm_agent.llm_test_case_handler.get_test_case_chromosomes_from_llm_results.return_value = llm_cases

    chromosome = llm_factory.get_chromosome()

    # Check that the chromosome contains the correct number of test cases
    assert isinstance(chromosome, TestSuiteChromosome)
    assert len(chromosome.test_case_chromosomes) == population


def test_get_chromosome_no_llm_tests(llm_factory, patch_llm_agent, mock_test_case_chromosome):
    config.configuration.large_language_model.llm_test_case_percentage = 0.0
    config.configuration.search_algorithm.population = 3

    patch_llm_agent.generate_tests_for_module_under_test.return_value = None

    chromosome = llm_factory.get_chromosome()

    assert isinstance(chromosome, TestSuiteChromosome)
    assert len(chromosome.test_case_chromosomes) == 3


def test_logging_info_when_merging(llm_factory, patch_llm_agent, caplog):
    config.configuration.large_language_model.llm_test_case_percentage = 0.0
    config.configuration.search_algorithm.population = 1

    with caplog.at_level("INFO"):
        llm_factory.get_chromosome()

    assert "Merged" in caplog.text
