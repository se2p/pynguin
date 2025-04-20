#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock
from unittest.mock import create_autospec

import pynguin.configuration as config
import pynguin.ga.llmtestsuitechromosomefactory as tf

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.orderedset import OrderedSet


def test_llm_factory_get_chromosome_without_llm_cases():
    class SafeFakeLLMAgent:
        def generate_tests_for_module_under_test(self):
            return "dummy"

    # 🔧 This function will now accept any keyword arguments
    def fake_llm_handler(**_kwargs):
        mock_chrom = create_autospec(TestCaseChromosome)
        mock_chrom.clone.return_value = mock_chrom
        return [mock_chrom]

    # ✅ Attach the static method to a class and instantiate it
    SafeFakeLLMAgent.llm_test_case_handler = type(
        "LLMHandler",
        (),
        {"get_test_case_chromosomes_from_llm_results": staticmethod(fake_llm_handler)},
    )()

    tf.LLMAgent = SafeFakeLLMAgent

    mock_test_case = create_autospec(TestCaseChromosome)
    test_case_chromosome_factory = MagicMock()
    test_case_chromosome_factory.get_chromosome.return_value = mock_test_case

    factory = tf.LLMTestSuiteChromosomeFactory(
        test_case_chromosome_factory,
        MagicMock(TestFactory),
        MagicMock(),  # test_cluster
        OrderedSet(),  # fitness_functions
        OrderedSet(),  # coverage_functions
    )

    chromosome = factory.get_chromosome()

    assert isinstance(chromosome, TestSuiteChromosome)
    assert len(chromosome.test_case_chromosomes) == config.configuration.search_algorithm.population
