# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.utils import randomness


@pytest.fixture
def chromosome() -> tsc.TestSuiteChromosome:
    return tsc.TestSuiteChromosome()


def test_clone(chromosome):
    chromosome.add_test(dtc.DefaultTestCase())
    result = chromosome.clone()
    assert len(result._tests) == 1


def test_add_delete_tests(chromosome):
    test_1 = dtc.DefaultTestCase()
    test_2 = dtc.DefaultTestCase()
    chromosome.add_tests([test_1, test_2])
    chromosome.delete_test(test_2)
    assert chromosome.test_chromosomes == [test_1]


def test_delete_non_existing_test(chromosome):
    chromosome.changed = False
    chromosome.delete_test(dtc.DefaultTestCase())
    assert not chromosome.changed


def test_add_empty_tests(chromosome):
    chromosome.changed = False
    chromosome.add_tests([])
    assert not chromosome.changed


def test_set_get_test_chromosome(chromosome):
    test = dtc.DefaultTestCase()
    chromosome.add_test(MagicMock(dtc.DefaultTestCase))
    chromosome.set_test_chromosome(0, test)
    assert chromosome.get_test_chromosome(0) == test


def test_total_length_of_test_cases(chromosome):
    test_1 = MagicMock(tc.TestCase)
    test_1.size.return_value = 2
    test_2 = MagicMock(tc.TestCase)
    test_2.size.return_value = 3
    chromosome.add_tests([test_1, test_2])
    assert chromosome.total_length_of_test_cases == 5
    assert chromosome.size() == 2


def test_hash(chromosome):
    assert chromosome.__hash__() != 0


def test_eq_self(chromosome):
    assert chromosome.__eq__(chromosome)


def test_eq_other_type(chromosome):
    assert not chromosome.__eq__(MagicMock(tc.TestCase))


def test_eq_different_size(chromosome):
    chromosome.add_test(MagicMock(tc.TestCase))
    other = tsc.TestSuiteChromosome()
    other.add_test(MagicMock(tc.TestCase))
    other.add_test(MagicMock(tc.TestCase))
    assert not chromosome.__eq__(other)


def test_eq_different_tests(chromosome):
    test_1 = dtc.DefaultTestCase()
    test_2 = dtc.DefaultTestCase()
    test_3 = MagicMock(tc.TestCase)
    other = tsc.TestSuiteChromosome()
    chromosome.add_tests([test_1, test_2])
    other.add_tests([test_1, test_3])
    assert not chromosome.__eq__(other)


def test_eq_clone(chromosome):
    test = dtc.DefaultTestCase()
    chromosome.add_test(test)
    other = chromosome.clone()
    assert chromosome.__eq__(other)


def test_crossover_wrong_type(chromosome):
    with pytest.raises(RuntimeError):
        chromosome.cross_over(0, 0, 0)


def test_crossover(chromosome):
    cases_a = [dtc.DefaultTestCase() for _ in range(5)]
    cases_b = [dtc.DefaultTestCase() for _ in range(5)]

    chromosome.add_tests(cases_a)

    other = tsc.TestSuiteChromosome()
    other.add_tests(cases_b)
    pos1 = randomness.next_int(len(cases_a))
    pos2 = randomness.next_int(len(cases_b))

    chromosome.set_changed(False)
    chromosome.cross_over(other, pos1, pos2)
    assert chromosome.test_chromosomes == cases_a[:pos1] + cases_b[pos2:]
    assert chromosome.has_changed()


def test_mutate_no_test_case_factory(chromosome):
    with pytest.raises(AssertionError):
        chromosome.mutate()


def test_mutate_existing():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    chromosome = tsc.TestSuiteChromosome(test_case_factory)
    test_1 = MagicMock(tc.TestCase)
    test_1.size.return_value = 1
    test_1.has_changed.return_value = True
    test_2 = MagicMock(tc.TestCase)
    test_2.size.return_value = 1
    test_2.has_changed.return_value = False
    test_3 = MagicMock(tc.TestCase)
    test_3.size.return_value = 1
    chromosome.add_test(test_1)
    chromosome.add_test(test_2)
    chromosome.set_changed(False)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0, 0.0, 1.0, 1.0]
        chromosome.mutate()
    test_1.mutate.assert_called_once()
    test_2.mutate.assert_called_once()
    test_3.mutate.assert_not_called()
    assert chromosome.has_changed()


def test_mutate_add_new():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    test_case = MagicMock(tc.TestCase)
    test_case.size.return_value = 1
    test_case_factory.get_test_case.return_value = test_case
    chromosome = tsc.TestSuiteChromosome(test_case_factory)
    chromosome.set_changed(False)
    config.INSTANCE.test_insertion_probability = 0.5
    config.INSTANCE.max_size = 10
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.1, 0.1, 0.1, 0.1]
        chromosome.mutate()
    assert test_case_factory.get_test_case.call_count == 3
    assert chromosome.has_changed()


def test_mutate_add_new_max_size():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    test_case = MagicMock(tc.TestCase)
    test_case.size.return_value = 1
    test_case_factory.get_test_case.return_value = test_case
    chromosome = tsc.TestSuiteChromosome(test_case_factory)
    chromosome.set_changed(False)
    config.INSTANCE.test_insertion_probability = 0.5
    config.INSTANCE.max_size = 2
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.1, 0.1, 0.1]
        chromosome.mutate()
    assert test_case_factory.get_test_case.call_count == 2
    assert chromosome.has_changed()


def test_mutate_remove_empty():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    chromosome = tsc.TestSuiteChromosome(test_case_factory)
    test_1 = MagicMock(tc.TestCase)
    test_1.size.return_value = 1
    test_1.has_changed.return_value = True
    test_2 = MagicMock(tc.TestCase)
    test_2.size.return_value = 0
    chromosome.add_test(test_1)
    chromosome.add_test(test_2)
    chromosome.set_changed(False)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        # Prevent any other mutations/insertions.
        float_mock.side_effect = [1.0, 1.0, 1.0]
        chromosome.mutate()
    assert chromosome.test_chromosomes == [test_1]
    # A test case can only have a size of zero if it was mutated, but this already sets changed to True
    # So this check is valid
    assert not chromosome.has_changed()


def test_mutate_no_changes():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    chromosome = tsc.TestSuiteChromosome(test_case_factory)
    test_1 = MagicMock(tc.TestCase)
    test_1.size.return_value = 1
    test_1.has_changed.return_value = True
    chromosome.add_test(test_1)
    chromosome.set_changed(False)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        # Prevent any other mutations/insertions.
        float_mock.side_effect = [1.0, 1.0, 1.0]
        chromosome.mutate()
    assert chromosome.test_chromosomes == [test_1]
    assert not chromosome.has_changed()
