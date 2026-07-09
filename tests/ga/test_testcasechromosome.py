#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock
from unittest.mock import MagicMock, call

import pytest

import pynguin.configuration as config
import pynguin.ga.computations as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.testcase.execution import ExecutionResult
from tests.testcase._builders import call_stmt, int_stmt, stmt


@pytest.fixture
def test_case_chromosome(default_test_case):
    return tcc.TestCaseChromosome(default_test_case)


@pytest.fixture
def test_case_chromosome_with_test(default_test_case):
    return tcc.TestCaseChromosome(default_test_case), default_test_case


# --------------------------------------------------------------------------------
# Basic attributes
# --------------------------------------------------------------------------------


def test_has_changed_default(test_case_chromosome):
    assert test_case_chromosome.changed


@pytest.mark.parametrize("value", [True, False])
def test_has_changed(test_case_chromosome, value):
    test_case_chromosome.changed = value
    assert test_case_chromosome.changed == value


def test_test_case_getter(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    assert chromosome.test_case is test_case


def test_test_case_setter(test_case_chromosome):
    new_test_case = tc.TestCase()
    test_case_chromosome.test_case = new_test_case
    assert test_case_chromosome.test_case is new_test_case


def test_num_mutations_default(test_case_chromosome):
    assert test_case_chromosome.num_mutations() == 0


def test_num_mutations_incremented_on_change(default_test_case):
    test_factory = MagicMock(tf.TestFactory)
    test_factory.has_call_on_sut.return_value = True
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    config.configuration.search_algorithm.test_delete_probability = 1.0
    config.configuration.search_algorithm.test_change_probability = 0.0
    config.configuration.search_algorithm.test_insert_probability = 0.0
    with (
        mock.patch("pynguin.utils.randomness.next_float", side_effect=[0.0, 1.0, 1.0]),
        mock.patch.object(chromosome, "_mutation_delete", return_value=True),
    ):
        chromosome.mutate()
    assert chromosome.num_mutations() == 1


def test_get_last_execution_last_result_default(test_case_chromosome):
    assert test_case_chromosome.get_last_execution_result() is None


def test_set_last_execution_result(test_case_chromosome):
    result = MagicMock(ExecutionResult)
    test_case_chromosome.set_last_execution_result(result)
    assert test_case_chromosome.get_last_execution_result() == result


def test_remove_last_execution_result(test_case_chromosome):
    result = MagicMock(ExecutionResult)
    test_case_chromosome.set_last_execution_result(result)
    test_case_chromosome.remove_last_execution_result()
    assert test_case_chromosome.get_last_execution_result() is None


# --------------------------------------------------------------------------------
# size / length
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("num_statements", [0, 1, 3])
def test_size_and_length(default_test_case, num_statements):
    for i in range(num_statements):
        default_test_case.add_statement(int_stmt(f"var_{i}", i))
    chromosome = tcc.TestCaseChromosome(default_test_case)
    assert chromosome.size() == num_statements
    assert chromosome.length() == chromosome.size()


# --------------------------------------------------------------------------------
# get_last_mutatable_statement
# --------------------------------------------------------------------------------


def test_get_last_mutatable_statement_empty(test_case_chromosome):
    assert test_case_chromosome.get_last_mutatable_statement() is None


def test_get_last_mutatable_statement_max(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    test_case.add_statement(int_stmt("var_0", 5))
    assert chromosome.get_last_mutatable_statement() == 0


def test_get_last_mutatable_statement_mid(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    test_case.add_statement(int_stmt("var_0", 5))
    test_case.add_statement(int_stmt("var_1", 5))
    test_case.add_statement(int_stmt("var_2", 5))
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = True
    result.get_first_position_of_thrown_exception.return_value = 1
    chromosome.set_last_execution_result(result)
    assert chromosome.get_last_mutatable_statement() == 1


def test_get_last_mutatable_statement_too_large(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    test_case.add_statement(int_stmt("var_0", 5))
    test_case.add_statement(int_stmt("var_1", 5))
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = True
    result.get_first_position_of_thrown_exception.return_value = 4
    chromosome.set_last_execution_result(result)
    assert chromosome.get_last_mutatable_statement() == chromosome.size() - 1


# --------------------------------------------------------------------------------
# _mutation_insert
# --------------------------------------------------------------------------------


def test_mutation_insert_none(test_case_chromosome):
    config.configuration.search_algorithm.statement_insertion_probability = 0.0
    with mock.patch("pynguin.utils.randomness.next_float", return_value=0.5):
        assert not test_case_chromosome._mutation_insert()


def test_mutation_insert_two(default_test_case):
    test_factory = MagicMock(tf.TestFactory)

    def side_effect(test_case_arg, _):
        test_case_arg.add_statement(int_stmt(f"var_{test_case_arg.size()}", 5))
        return 0

    test_factory.insert_random_statement.side_effect = side_effect
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    config.configuration.search_algorithm.statement_insertion_probability = 0.5
    config.configuration.search_algorithm.chromosome_length = 10
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.2, 0.2, 0.2]
        assert chromosome._mutation_insert()
    test_factory.insert_random_statement.assert_has_calls([
        call(default_test_case, 0),
        call(default_test_case, 1),
    ])


def test_mutation_insert_twice_no_success_uses_position_zero(default_test_case):
    """Covers the "no mutatable statement found" branch (start at position 0)."""
    test_factory = MagicMock(tf.TestFactory)

    def side_effect(_test_case_arg, _position):
        return -1

    test_factory.insert_random_statement.side_effect = side_effect
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    config.configuration.search_algorithm.statement_insertion_probability = 0.5
    config.configuration.search_algorithm.chromosome_length = 10
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.2, 0.2, 0.2]
        assert not chromosome._mutation_insert()
    test_factory.insert_random_statement.assert_has_calls([
        call(default_test_case, 0),
        call(default_test_case, 0),
    ])


def test_mutation_insert_max_length(default_test_case):
    test_factory = MagicMock(tf.TestFactory)

    def side_effect(test_case_arg, _):
        test_case_arg.add_statement(int_stmt(f"var_{test_case_arg.size()}", 5))
        return 0

    test_factory.insert_random_statement.side_effect = side_effect
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    config.configuration.search_algorithm.statement_insertion_probability = 0.5
    config.configuration.search_algorithm.chromosome_length = 1
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0, 0.0]
        assert chromosome._mutation_insert()
    test_factory.insert_random_statement.assert_has_calls([call(default_test_case, 0)])
    assert default_test_case.size() == 1


# --------------------------------------------------------------------------------
# _mutation_change
# --------------------------------------------------------------------------------


def test_mutation_change_nothing_to_change(test_case_chromosome):
    assert not test_case_chromosome._mutation_change()


def test_mutation_change_no_change(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    test_case.add_statement(int_stmt("var_0", 5))
    with mock.patch("pynguin.utils.randomness.next_float", return_value=1.0):
        assert not chromosome._mutation_change()


@pytest.mark.parametrize("mutate_value_result", [True, False])
def test_mutation_change_single_prim_delegates_to_mutate_value(
    test_case_chromosome_with_test, mutate_value_result
):
    chromosome, test_case = test_case_chromosome_with_test
    test_case.add_statement(int_stmt("var_0", 5))
    factory = MagicMock(tf.TestFactory)
    factory.mutate_value.return_value = mutate_value_result
    chromosome._test_factory = factory
    # Disable the change_statement_type gate so mutation reaches mutate_value.
    config.configuration.search_algorithm.change_statement_type_probability = 0.0
    with mock.patch("pynguin.utils.randomness.next_float", return_value=0.0):
        assert chromosome._mutation_change() is mutate_value_result
    factory.mutate_value.assert_called_once_with(test_case, 0)


def test_mutation_change_skips_statement_without_bound_variable(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    test_case.add_statement(stmt("print(1)"))
    factory = MagicMock(tf.TestFactory)
    chromosome._test_factory = factory
    with mock.patch("pynguin.utils.randomness.next_float", return_value=0.0):
        assert not chromosome._mutation_change()
    factory.mutate_value.assert_not_called()
    factory.mutate_call.assert_not_called()


@pytest.mark.parametrize(
    "mutate_call_result,change_random_call_result,expected",
    [
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ],
)
def test_mutation_change_call(
    constructor_mock,
    default_test_case,
    mutate_call_result,
    change_random_call_result,
    expected,
):
    factory = MagicMock(tf.TestFactory)
    factory.mutate_call.return_value = mutate_call_result
    factory.change_random_call.return_value = change_random_call_result
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=factory)
    statement = call_stmt("var_0", "SomeType(var_0)")
    statement.accessible = constructor_mock
    default_test_case.add_statement(statement)
    # Disable the change_statement_type gate so mutation reaches mutate_call.
    config.configuration.search_algorithm.change_statement_type_probability = 0.0
    with mock.patch("pynguin.utils.randomness.next_float", return_value=0.0):
        assert chromosome._mutation_change() is expected
    factory.mutate_call.assert_called_once_with(default_test_case, 0)
    if mutate_call_result:
        factory.change_random_call.assert_not_called()
    else:
        factory.change_random_call.assert_called_once_with(default_test_case, 0)


def test_mutation_change_fires_change_statement_type(constructor_mock, default_test_case):
    """When the gate probability fires, mutation delegates to change_statement_type."""
    factory = MagicMock(tf.TestFactory)
    factory.change_statement_type.return_value = True
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=factory)
    statement = call_stmt("var_0", "SomeType(var_0)")
    statement.accessible = constructor_mock
    default_test_case.add_statement(statement)
    config.configuration.search_algorithm.change_statement_type_probability = 1.0
    with mock.patch("pynguin.utils.randomness.next_float", return_value=0.0):
        assert chromosome._mutation_change() is True
    factory.change_statement_type.assert_called_once_with(default_test_case, 0)
    factory.mutate_call.assert_not_called()
    factory.change_random_call.assert_not_called()


def test_mutation_change_field_delegates_to_field_call(field_mock, default_test_case):
    """A field statement is mutated via change_random_field_call, then mutate_call."""
    factory = MagicMock(tf.TestFactory)
    factory.change_random_field_call.return_value = False
    factory.mutate_call.return_value = True
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=factory)
    statement = call_stmt("var_0", "var_1.value")
    statement.accessible = field_mock
    default_test_case.add_statement(statement)
    config.configuration.search_algorithm.change_statement_type_probability = 0.0
    with mock.patch("pynguin.utils.randomness.next_float", return_value=0.0):
        assert chromosome._mutation_change() is True
    factory.change_random_field_call.assert_called_once_with(default_test_case, 0)
    factory.mutate_call.assert_called_once_with(default_test_case, 0)


# --------------------------------------------------------------------------------
# _mutation_delete / _delete_statement
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("result", [True, False])
def test_delete_statement(result, default_test_case):
    test_factory = MagicMock(tf.TestFactory)
    test_factory.delete_statement_gracefully.return_value = result
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    default_test_case.add_statement(int_stmt("var_0", 5))
    assert chromosome._delete_statement(0) == result
    test_factory.delete_statement_gracefully.assert_called_with(default_test_case, 0)


def test_mutation_delete_empty(test_case_chromosome):
    assert not test_case_chromosome._mutation_delete()


def test_mutation_delete_not_empty(default_test_case):
    chromosome = tcc.TestCaseChromosome(default_test_case)
    default_test_case.add_statement(int_stmt("var_0", 5))
    default_test_case.add_statement(int_stmt("var_1", 5))
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0, 1.0]
        with mock.patch.object(chromosome, "_delete_statement") as delete_mock:
            delete_mock.return_value = True
            assert chromosome._mutation_delete()
            delete_mock.assert_has_calls([call(1)])
            assert delete_mock.call_count == 1


def test_mutation_delete_skipping_out_of_range_indices(default_test_case):
    """Covers the "idx >= self.size()" skip branch."""
    chromosome = tcc.TestCaseChromosome(default_test_case)
    with mock.patch.object(chromosome, "_delete_statement") as delete_mock:
        delete_mock.return_value = True
        with mock.patch.object(chromosome, "get_last_mutatable_statement") as mut_mock:
            mut_mock.return_value = 3
            assert not chromosome._mutation_delete()
            assert delete_mock.call_count == 0


# --------------------------------------------------------------------------------
# mutate (delegation to the test factory)
# --------------------------------------------------------------------------------


def test_mutate_chop(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    chromosome.changed = False
    for i in range(50):
        test_case.add_statement(int_stmt(f"var_{i}", 5))
    config.configuration.search_algorithm.test_insert_probability = 0.0
    config.configuration.search_algorithm.test_change_probability = 0.0
    config.configuration.search_algorithm.test_delete_probability = 0.0
    with mock.patch.object(chromosome, "get_last_mutatable_statement") as mut_mock:
        mut_mock.return_value = 5
        with mock.patch.object(chromosome, "_test_factory") as factory_mock:
            factory_mock.has_call_on_sut.return_value = True
            chromosome.mutate()
            assert chromosome.changed
            assert test_case.size() == 6
            assert factory_mock.has_call_on_sut.call_count == 1


def test_mutate_no_chop(test_case_chromosome_with_test):
    chromosome, test_case = test_case_chromosome_with_test
    for i in range(50):
        test_case.add_statement(int_stmt(f"var_{i}", 5))
    chromosome.changed = False
    config.configuration.search_algorithm.test_insert_probability = 0.0
    config.configuration.search_algorithm.test_change_probability = 0.0
    config.configuration.search_algorithm.test_delete_probability = 0.0
    with mock.patch.object(chromosome, "get_last_mutatable_statement") as mut_mock:
        mut_mock.return_value = None
        with mock.patch.object(chromosome, "_test_factory") as factory_mock:
            factory_mock.has_call_on_sut.return_value = True
            chromosome.mutate()
            assert test_case.size() == 50
            assert not chromosome.changed
            assert factory_mock.has_call_on_sut.call_count == 1


@pytest.mark.parametrize(
    "func,rand,result",
    [
        ("_mutation_delete", [0, 1, 1], False),
        ("_mutation_delete", [0, 1, 1], True),
        ("_mutation_change", [1, 0, 1], True),
        ("_mutation_change", [1, 0, 1], False),
        ("_mutation_insert", [1, 1, 0], True),
        ("_mutation_insert", [1, 1, 0], False),
    ],
)
def test_mutate_delegates_to_the_right_operator(test_case_chromosome, func, rand, result):
    test_case_chromosome.changed = False
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = rand
        with mock.patch.object(test_case_chromosome, func) as mock_func:
            mock_func.return_value = result
            with mock.patch.object(test_case_chromosome, "_test_factory") as factory_mock:
                factory_mock.has_call_on_sut.return_value = True
                test_case_chromosome.mutate()
                assert test_case_chromosome.changed == result
                mock_func.assert_called_once()


def test_mutate_restores_backup_when_no_call_on_sut(default_test_case):
    """Covers the "insurance" branch: mutation removed all calls on the SUT."""
    default_test_case.add_statement(int_stmt("var_0", 5))
    test_factory = MagicMock(tf.TestFactory)
    test_factory.has_call_on_sut.return_value = False
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    with (
        mock.patch("pynguin.utils.randomness.next_float", return_value=1.0),
        mock.patch.object(chromosome, "_mutation_insert") as insert_mock,
    ):
        chromosome.mutate()
    test_factory.has_call_on_sut.assert_called_once_with(chromosome.test_case)
    insert_mock.assert_called_once()
    # The backup (a clone) was installed as the new wrapped test case.
    assert chromosome.test_case is not default_test_case


# --------------------------------------------------------------------------------
# cross_over
# --------------------------------------------------------------------------------


def test_crossover_wrong_type(test_case_chromosome):
    with pytest.raises(AssertionError):
        test_case_chromosome.cross_over(MagicMock(), 0, 0)


def test_crossover_requires_test_factory(default_test_case):
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=None)
    other = tcc.TestCaseChromosome(tc.TestCase(), test_factory=None)
    with pytest.raises(AssertionError, match="Crossover requires a test factory"):
        chromosome.cross_over(other, 0, 0)


@pytest.mark.parametrize(
    "offspring_size,position1,expect_remove",
    [
        (5, 3, True),
        (3, 5, False),
        (3, 3, False),
    ],
)
def test_crossover_success(offspring_size, position1, expect_remove):
    test_factory = MagicMock()
    test_case0 = MagicMock(tc.TestCase)
    test_case0_clone = MagicMock(tc.TestCase)
    test_case0_clone.size.return_value = offspring_size
    test_case0.clone.return_value = test_case0_clone
    test_case1 = MagicMock(tc.TestCase)
    left = tcc.TestCaseChromosome(test_case0, test_factory=test_factory)
    right = tcc.TestCaseChromosome(test_case1, test_factory=test_factory)
    config.configuration.search_algorithm.chromosome_length = 100
    left.changed = False

    left.cross_over(right, position1, 2)

    if expect_remove:
        test_case0_clone.remove_statements_batch.assert_called_once_with(
            set(range(position1, offspring_size))
        )
    else:
        test_case0_clone.remove_statements_batch.assert_not_called()
    test_case0_clone.append_test_case_from.assert_called_once_with(test_case1, 2)
    assert left.test_case is test_case0_clone
    assert left.changed


def test_crossover_too_large():
    test_factory = MagicMock()
    test_case0 = MagicMock(tc.TestCase)
    test_case0_clone = MagicMock(tc.TestCase)
    test_case0_clone.size.return_value = 5
    test_case0.clone.return_value = test_case0_clone
    test_case1 = MagicMock(tc.TestCase)
    left = tcc.TestCaseChromosome(test_case0, test_factory=test_factory)
    right = tcc.TestCaseChromosome(test_case1, test_factory=test_factory)
    config.configuration.search_algorithm.chromosome_length = 3
    left.changed = False

    left.cross_over(right, 1, 2)

    test_case0_clone.append_test_case_from.assert_called_once_with(test_case1, 2)
    assert not left.changed
    assert left.test_case is test_case0


# --------------------------------------------------------------------------------
# is_failing
# --------------------------------------------------------------------------------


def test_is_failing(test_case_chromosome):
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = True
    test_case_chromosome.set_last_execution_result(result)
    assert test_case_chromosome.is_failing()


def test_is_failing_without_execution_result(test_case_chromosome):
    assert not test_case_chromosome.is_failing()


# --------------------------------------------------------------------------------
# accept / clone / equality / hash
# --------------------------------------------------------------------------------


def test_accept(test_case_chromosome):
    visitor = MagicMock()
    test_case_chromosome.accept(visitor)
    visitor.visit_test_case_chromosome.assert_called_once_with(test_case_chromosome)


def test_clone(default_test_case):
    default_test_case.add_statement(int_stmt("var_0", 5))
    test_factory = MagicMock(tf.TestFactory)
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)
    chromosome.changed = False
    chromosome._num_mutations = 3
    result = MagicMock(ExecutionResult)
    chromosome.set_last_execution_result(result)

    clone = chromosome.clone()

    assert isinstance(clone, tcc.TestCaseChromosome)
    assert clone is not chromosome
    assert clone.test_case is not chromosome.test_case
    assert clone.test_case == chromosome.test_case
    assert clone.changed == chromosome.changed
    assert clone.num_mutations() == chromosome.num_mutations()
    assert clone.get_last_execution_result() == chromosome.get_last_execution_result()
    assert clone._test_factory is chromosome._test_factory


def test_eq_self(test_case_chromosome):
    same_reference = test_case_chromosome
    assert test_case_chromosome == same_reference


def test_eq_other_type(test_case_chromosome):
    assert test_case_chromosome != MagicMock()


def test_eq_same_test_case(default_test_case):
    default_test_case.add_statement(int_stmt("var_0", 5))
    chromosome1 = tcc.TestCaseChromosome(default_test_case)
    chromosome2 = tcc.TestCaseChromosome(default_test_case)
    assert chromosome1 == chromosome2


def test_eq_different_test_case(default_test_case):
    other_test_case = tc.TestCase()
    other_test_case.add_statement(int_stmt("var_0", 5))
    chromosome1 = tcc.TestCaseChromosome(default_test_case)
    chromosome2 = tcc.TestCaseChromosome(other_test_case)
    assert chromosome1 != chromosome2


def test_eq_diverging_execution_traces(default_test_case):
    chromosome1 = tcc.TestCaseChromosome(default_test_case)
    chromosome2 = tcc.TestCaseChromosome(default_test_case.clone())
    result1 = MagicMock(ExecutionResult)
    result1.execution_trace = MagicMock()
    result2 = MagicMock(ExecutionResult)
    result2.execution_trace = MagicMock()
    chromosome1.set_last_execution_result(result1)
    chromosome2.set_last_execution_result(result2)
    assert chromosome1 != chromosome2


def test_eq_matching_execution_traces(default_test_case):
    chromosome1 = tcc.TestCaseChromosome(default_test_case)
    chromosome2 = tcc.TestCaseChromosome(default_test_case.clone())
    shared_trace = MagicMock()
    result1 = MagicMock(ExecutionResult)
    result1.execution_trace = shared_trace
    result2 = MagicMock(ExecutionResult)
    result2.execution_trace = shared_trace
    chromosome1.set_last_execution_result(result1)
    chromosome2.set_last_execution_result(result2)
    assert chromosome1 == chromosome2


def test_hash(default_test_case):
    chromosome = tcc.TestCaseChromosome(default_test_case)
    assert hash(chromosome) == hash(default_test_case)


# --------------------------------------------------------------------------------
# Fitness caching (invalidation on mutation)
# --------------------------------------------------------------------------------


def test_fitness_cache_invalidated_after_mutation(default_test_case):
    default_test_case.add_statement(int_stmt("var_0", 5))
    test_factory = MagicMock(tf.TestFactory)
    test_factory.has_call_on_sut.return_value = True
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)

    fitness_function = MagicMock(ff.FitnessFunction)
    fitness_function.is_maximisation_function.return_value = False
    fitness_function.compute_fitness.side_effect = [1.0, 0.5]
    fitness_function.compute_is_covered.return_value = False
    chromosome.add_fitness_function(fitness_function)

    assert chromosome.get_fitness() == 1.0
    assert chromosome.get_fitness() == 1.0
    assert fitness_function.compute_fitness.call_count == 1

    config.configuration.search_algorithm.test_delete_probability = 1.0
    config.configuration.search_algorithm.test_change_probability = 0.0
    config.configuration.search_algorithm.test_insert_probability = 0.0
    with (
        mock.patch("pynguin.utils.randomness.next_float", side_effect=[0.0, 1.0, 1.0]),
        mock.patch.object(chromosome, "_mutation_delete", return_value=True),
    ):
        chromosome.mutate()
    assert chromosome.changed
    assert chromosome.num_mutations() == 1

    assert chromosome.get_fitness() == 0.5
    assert fitness_function.compute_fitness.call_count == 2


def test_fitness_cache_not_invalidated_without_mutation(default_test_case):
    default_test_case.add_statement(int_stmt("var_0", 5))
    test_factory = MagicMock(tf.TestFactory)
    test_factory.has_call_on_sut.return_value = True
    chromosome = tcc.TestCaseChromosome(default_test_case, test_factory=test_factory)

    fitness_function = MagicMock(ff.FitnessFunction)
    fitness_function.is_maximisation_function.return_value = False
    fitness_function.compute_fitness.side_effect = [1.0, 2.0]
    fitness_function.compute_is_covered.return_value = False
    chromosome.add_fitness_function(fitness_function)

    assert chromosome.get_fitness() == 1.0

    config.configuration.search_algorithm.test_delete_probability = 0.0
    config.configuration.search_algorithm.test_change_probability = 0.0
    config.configuration.search_algorithm.test_insert_probability = 0.0
    with mock.patch("pynguin.utils.randomness.next_float", return_value=1.0):
        chromosome.mutate()
    assert not chromosome.changed

    assert chromosome.get_fitness() == 1.0
    assert fitness_function.compute_fitness.call_count == 1
