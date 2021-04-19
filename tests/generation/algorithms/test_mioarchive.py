#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

from pynguin.generation.algorithms.mioarchive import Population, PopulationPair


def test_population_pair():
    pair = PopulationPair(0.5, MagicMock())
    assert pair == pair


def test_population_initial_counter():
    population = Population(1)
    assert population.counter == 0


def test_population_not_covered():
    population = Population(1)
    assert not population.is_covered


def test_population_is_covered():
    population = Population(1)
    best_solution = MagicMock()
    population.add_solution(1.0, best_solution)
    assert population.is_covered


def test_population_add_solution_covered():
    population = Population(5)
    best_solution = MagicMock()
    population.add_solution(1.0, best_solution)
    assert population.num_solutions == 1


def test_population_add_solution_worst():
    population = Population(5)
    best_solution = MagicMock()
    population.add_solution(0.0, best_solution)
    assert population.num_solutions == 0


def test_population_add_solution_already_covered():
    population = Population(5)
    best_solution = MagicMock()
    good_solution = MagicMock()
    population.add_solution(1.0, best_solution)
    assert population.add_solution(0.5, good_solution) is False


def test_population_add_solution_replace_best():
    population = Population(5)
    good_solution = MagicMock()
    better_solution = MagicMock()
    population.add_solution(1.0, good_solution)
    with mock.patch.object(population, "_is_pair_better_than_current") as better_mock:
        better_mock.return_value = True
        assert population.add_solution(1.0, better_solution) is True
        better_mock.assert_called_with(
            PopulationPair(1.0, good_solution), PopulationPair(1.0, better_solution)
        )
        assert population.get_best_solution_if_any() == better_solution


def test_population_add_solution_shrink():
    population = Population(2)
    good_solution = MagicMock()
    population.add_solution(0.5, MagicMock())
    population.add_solution(0.5, MagicMock())
    assert population.num_solutions == 2
    assert population.add_solution(1.0, good_solution) is True
    assert population.get_best_solution_if_any() == good_solution
    assert population.num_solutions == 1


def test_population_add_solution_still_space():
    population = Population(5)
    population.add_solution(0.5, MagicMock())
    population.add_solution(0.5, MagicMock())
    population.add_solution(0.5, MagicMock())
    population.add_solution(0.5, MagicMock())
    assert population.add_solution(0.5, MagicMock()) is True
    assert population.num_solutions == 5


def test_population_add_solution_replace_worst():
    population = Population(5)
    population.add_solution(0.1, MagicMock())
    population.add_solution(0.2, MagicMock())
    population.add_solution(0.3, MagicMock())
    population.add_solution(0.4, MagicMock())
    population.add_solution(0.5, MagicMock())
    with mock.patch.object(population, "_is_pair_better_than_current") as better_mock:
        better_mock.return_value = True
        assert population.add_solution(0.6, MagicMock()) is True
        assert population.num_solutions == 5


def test_population_add_solution_to_bad():
    population = Population(5)
    population.add_solution(0.1, MagicMock())
    population.add_solution(0.2, MagicMock())
    population.add_solution(0.3, MagicMock())
    population.add_solution(0.4, MagicMock())
    population.add_solution(0.5, MagicMock())
    with mock.patch.object(population, "_is_pair_better_than_current") as better_mock:
        better_mock.return_value = False
        assert population.add_solution(0.01, MagicMock()) is False
        assert population.num_solutions == 5


def test_population_sample_solution():
    population = Population(5)
    solution = MagicMock()
    population.add_solution(0.1, solution)
    assert population.sample_solution() == solution
    assert population.counter == 1


def test_population_sample_solution_reset():
    population = Population(5)
    solution = MagicMock()
    population.add_solution(0.1, solution)
    assert population.sample_solution() == solution
    assert population.counter == 1
    assert population.add_solution(0.01, solution) is True
    assert population.counter == 0


def test_population_no_solution():
    population = Population(5)
    assert population.get_best_solution_if_any() is None


def test_population_shrink_solution():
    population = Population(3)
    population.add_solution(0.5, MagicMock())
    population.add_solution(0.5, MagicMock())
    population.add_solution(0.5, MagicMock())
    population.shrink_population(1)
    assert population.num_solutions == 1


def test_population_shrink_solution_already_covered():
    population = Population(3)
    with mock.patch.object(population, "_is_pair_better_than_current") as better_mock:
        better_mock.return_value = False
        population.add_solution(1.0, MagicMock())
        population.add_solution(1.0, MagicMock())
        population.add_solution(1.0, MagicMock())
        population.shrink_population(1)
        assert population.num_solutions == 1


def test_population_make_sure_sorted():
    population = Population(3)
    with mock.patch.object(population, "_is_pair_better_than_current") as better_mock:
        better_mock.return_value = False
        first = MagicMock()
        second = MagicMock()
        third = MagicMock()
        population.add_solution(0.2, second)
        population.add_solution(0.1, first)
        population.add_solution(0.3, third)
        assert [p.test_case_chromosome for p in population._solutions] == [
            third,
            second,
            first,
        ]
