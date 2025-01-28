#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc


@pytest.fixture
def chromosome() -> tsc.TestSuiteChromosome:
    return tsc.TestSuiteChromosome()


def test_clone(chromosome, default_test_case):
    chromosome.add_test_case_chromosome(tcc.TestCaseChromosome(default_test_case))
    result = chromosome.clone()
    assert result == chromosome
    assert result is not chromosome


def test_add_delete_tests(chromosome):
    test_1 = MagicMock()
    test_2 = MagicMock()
    chromosome.add_test_case_chromosomes([test_1, test_2])
    chromosome.delete_test_case_chromosome(test_2)
    assert chromosome.test_case_chromosomes == [test_1]


def test_delete_non_existing_test(chromosome):
    chromosome.changed = False
    chromosome.delete_test_case_chromosome(MagicMock())
    assert not chromosome.changed


def test_add_empty_tests(chromosome):
    chromosome.changed = False
    chromosome.add_test_case_chromosomes([])
    assert not chromosome.changed


def test_set_get_test_chromosome(chromosome):
    test = MagicMock()
    chromosome.add_test_case_chromosome(MagicMock())
    chromosome.set_test_case_chromosome(0, test)
    assert chromosome.get_test_case_chromosome(0) == test


def test_total_length_of_test_cases(chromosome):
    test_1 = MagicMock(tcc.TestCaseChromosome)
    test_1.length.return_value = 2
    test_2 = MagicMock(tcc.TestCaseChromosome)
    test_2.length.return_value = 3
    chromosome.add_test_case_chromosomes([test_1, test_2])
    assert chromosome.length() == 5
    assert chromosome.size() == 2


def test_hash(chromosome):
    assert (hash(chromosome)) != 0


def test_eq_self(chromosome):
    assert chromosome == chromosome  # noqa: PLR0124


def test_eq_other_type(chromosome):
    assert chromosome != MagicMock(tc.TestCase)


def test_eq_different_size(chromosome):
    chromosome.add_test_case_chromosome(MagicMock(tcc.TestCaseChromosome))
    other = tsc.TestSuiteChromosome()
    other.add_test_case_chromosome(MagicMock(tcc.TestCaseChromosome))
    other.add_test_case_chromosome(MagicMock(tcc.TestCaseChromosome))
    assert chromosome != other


def test_eq_different_tests(chromosome):
    test_1 = MagicMock(tcc.TestCaseChromosome)
    test_2 = MagicMock(tcc.TestCaseChromosome)
    test_3 = MagicMock(tcc.TestCaseChromosome)
    other = tsc.TestSuiteChromosome()
    chromosome.add_test_case_chromosomes([test_1, test_2])
    other.add_test_case_chromosomes([test_1, test_3])
    assert chromosome != other


def test_crossover_wrong_type(chromosome):
    with pytest.raises(AssertionError):
        chromosome.cross_over(0, 0, 0)


def test_crossover(chromosome, default_test_case):
    cases_a = [tcc.TestCaseChromosome(default_test_case.clone()) for _ in range(5)]
    cases_b = [tcc.TestCaseChromosome(default_test_case.clone()) for _ in range(5)]

    chromosome.add_test_case_chromosomes(cases_a)

    other = tsc.TestSuiteChromosome()
    other.add_test_case_chromosomes(cases_b)
    pos1 = 3
    pos2 = 2

    chromosome.changed = False
    chromosome.cross_over(other, pos1, pos2)
    assert chromosome.test_case_chromosomes == cases_a[:pos1] + cases_b[pos2:]
    assert chromosome.changed


def test_mutate_no_test_case_factory(chromosome):
    with pytest.raises(AssertionError):
        chromosome.mutate()


def test_mutate_existing():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    chromosome = tsc.TestSuiteChromosome(test_case_chromosome_factory)
    test_1 = MagicMock(tcc.TestCaseChromosome)
    test_1.size.return_value = 1
    test_1.changed = True
    test_2 = MagicMock(tcc.TestCaseChromosome)
    test_2.size.return_value = 1
    test_2.changed = False
    test_3 = MagicMock(tcc.TestCaseChromosome)
    test_3.size.return_value = 1
    chromosome.add_test_case_chromosome(test_1)
    chromosome.add_test_case_chromosome(test_2)
    chromosome.changed = False
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0, 0.0, 1.0, 1.0]
        chromosome.mutate()
    test_1.mutate.assert_called_once()
    test_2.mutate.assert_called_once()
    test_3.mutate.assert_not_called()
    assert chromosome.changed


def test_mutate_add_new():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    test_case = MagicMock(tcc.TestCaseChromosome)
    test_case.size.return_value = 1
    test_case_chromosome_factory.get_chromosome.return_value = test_case
    chromosome = tsc.TestSuiteChromosome(test_case_chromosome_factory)
    chromosome.changed = False
    config.configuration.search_algorithm.test_insertion_probability = 0.5
    config.configuration.test_creation.max_size = 10
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.1, 0.1, 0.1, 0.1]
        chromosome.mutate()
    assert test_case_chromosome_factory.get_chromosome.call_count == 3
    assert chromosome.changed


def test_mutate_add_new_max_size():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    test_case = MagicMock(tcc.TestCaseChromosome)
    test_case.size.return_value = 1
    test_case_chromosome_factory.get_chromosome.return_value = test_case
    chromosome = tsc.TestSuiteChromosome(test_case_chromosome_factory)
    chromosome.changed = False
    config.configuration.search_algorithm.test_insertion_probability = 0.5
    config.configuration.test_creation.max_size = 2
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.1, 0.1, 0.1]
        chromosome.mutate()
    assert test_case_chromosome_factory.get_chromosome.call_count == 2
    assert chromosome.changed


def test_mutate_remove_empty():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    chromosome = tsc.TestSuiteChromosome(test_case_chromosome_factory)
    test_1 = MagicMock(tcc.TestCaseChromosome)
    test_1.size.return_value = 1
    test_1.changed = True
    test_2 = MagicMock(tcc.TestCaseChromosome)
    test_2.size.return_value = 0
    chromosome.add_test_case_chromosome(test_1)
    chromosome.add_test_case_chromosome(test_2)
    chromosome.changed = False
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        # Prevent any other mutations/insertions.
        float_mock.side_effect = [1.0, 1.0, 1.0]
        chromosome.mutate()
    assert chromosome.test_case_chromosomes == [test_1]
    # A test case can only have a size of zero if it was mutated, but this already sets
    # changed to True; so, this check is valid
    assert not chromosome.changed


def test_mutate_no_changes():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    chromosome = tsc.TestSuiteChromosome(test_case_chromosome_factory)
    test_1 = MagicMock(tcc.TestCaseChromosome)
    test_1.size.return_value = 1
    test_1.changed = True
    chromosome.add_test_case_chromosome(test_1)
    chromosome.changed = False
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        # Prevent any other mutations/insertions.
        float_mock.side_effect = [1.0, 1.0, 1.0]
        chromosome.mutate()
    assert chromosome.test_case_chromosomes == [test_1]
    assert not chromosome.changed


def test_accept(chromosome):
    visitor = MagicMock()
    chromosome.accept(visitor)
    visitor.visit_test_suite_chromosome.assert_called_once_with(chromosome)
