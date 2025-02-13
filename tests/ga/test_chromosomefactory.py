#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testsuitechromosome as tsc
import pynguin.ga.testsuitechromosomefactory as tscf

from pynguin.utils.orderedset import OrderedSet


def test_suite_factory_get_chromosome():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    factory = tscf.TestSuiteChromosomeFactory(
        test_case_chromosome_factory, OrderedSet(), OrderedSet()
    )
    config.configuration.search_algorithm.min_initial_tests = 5
    config.configuration.search_algorithm.max_initial_tests = 5
    chromosome = factory.get_chromosome()
    assert (
        config.configuration.search_algorithm.min_initial_tests
        <= test_case_chromosome_factory.get_chromosome.call_count
        <= config.configuration.search_algorithm.max_initial_tests
    )
    assert isinstance(chromosome, tsc.TestSuiteChromosome)
    assert chromosome.get_fitness_functions() == []


def test_archive_reuse_case_factory_get_chromosome():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    archive = MagicMock()
    chromosome_from_archive = MagicMock()
    clone_chromosome_from_archive = MagicMock()
    chromosome_from_archive.clone.return_value = clone_chromosome_from_archive
    archive.solutions = [chromosome_from_archive]
    factory = tccf.ArchiveReuseTestCaseChromosomeFactory(test_case_chromosome_factory, archive)
    config.configuration.seeding.seed_from_archive_probability = 1.0
    sampled = factory.get_chromosome()
    assert sampled == clone_chromosome_from_archive
    assert test_case_chromosome_factory.get_chromosome.call_count == 0


def test_archive_reuse_case_factory_get_chromosome_mutation_count():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    archive = MagicMock()
    chromosome_from_archive = MagicMock()
    clone_chromosome_from_archive = MagicMock()
    chromosome_from_archive.clone.return_value = clone_chromosome_from_archive
    archive.solutions = [chromosome_from_archive]
    factory = tccf.ArchiveReuseTestCaseChromosomeFactory(test_case_chromosome_factory, archive)
    config.configuration.seeding.seed_from_archive_probability = 1.0
    config.configuration.seeding.seed_from_archive_mutations = 42
    sampled = factory.get_chromosome()
    assert sampled == clone_chromosome_from_archive
    assert clone_chromosome_from_archive.mutate.call_count == 42


def test_archive_reuse_case_factory_get_chromosome_empty_archive():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    archive = MagicMock()
    chromosome_from_factory = MagicMock()
    archive.solutions = []
    test_case_chromosome_factory.get_chromosome.return_value = chromosome_from_factory
    factory = tccf.ArchiveReuseTestCaseChromosomeFactory(test_case_chromosome_factory, archive)
    config.configuration.seeding.seed_from_archive_probability = 1.0
    sampled = factory.get_chromosome()
    assert sampled == chromosome_from_factory


def test_archive_reuse_case_factory_get_chromosome_no_reuse():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    archive = MagicMock()
    chromosome_from_factory = MagicMock()
    archive.solutions = [MagicMock()]
    test_case_chromosome_factory.get_chromosome.return_value = chromosome_from_factory
    factory = tccf.ArchiveReuseTestCaseChromosomeFactory(test_case_chromosome_factory, archive)
    config.configuration.seeding.seed_from_archive_probability = 0.0
    sampled = factory.get_chromosome()
    assert sampled == chromosome_from_factory
