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
from unittest.mock import MagicMock

import pytest

import pynguin.ga.fitnessfunction as ff
import pynguin.ga.chromosome as chrom
from pynguin.ga.chromosome import Chromosome


@pytest.fixture
def fitness_function():
    return MagicMock(ff.FitnessFunction)


@pytest.fixture
def fitness_value(fitness_function):
    return {fitness_function: 0.42}


@pytest.fixture
def coverage_value(fitness_function):
    return {fitness_function: 0.42}


@pytest.fixture
def chromosome():
    class DummyChromosome(chrom.Chromosome):
        def size(self) -> int:
            raise NotImplementedError()

        def cross_over(self, other: chrom.Chromosome, position1: int, position2: int) -> None:
            raise NotImplementedError()
    return DummyChromosome()


class _DummyFitnessFunction(ff.FitnessFunction):
    def get_fitness(self, individual) -> float:
        pass

    def is_maximisation_function(self) -> bool:
        pass


def test_fitness_no_fitness_values(chromosome):
    assert chromosome.fitness == 0.0


def test_fitness_one_fitness_value(chromosome, fitness_value):
    chromosome.fitness_values = fitness_value
    assert chromosome.fitness == 0.42


def test_fitness_two_fitness_values(chromosome, fitness_function):
    fv = {fitness_function: 0.42, MagicMock(ff.FitnessFunction): 0.23}
    chromosome.fitness_values = fv
    assert chromosome.fitness == 0.65


def test_get_fitness(chromosome, fitness_function):
    chromosome.set_fitness(fitness_function, 0.42)
    assert chromosome.get_fitness(fitness_function) == 0.42


def test_set_fitness_error(chromosome, fitness_function):
    with pytest.raises(RuntimeError):
        chromosome.set_fitness(fitness_function, float("inf"))


def test_set_fitness_twice(chromosome, fitness_function):
    chromosome.set_fitness(fitness_function, 0.42)
    chromosome.set_fitness(fitness_function, 0.23)
    assert chromosome.has_executed_fitness(fitness_function)
    assert chromosome.previous_fitness_values[fitness_function] == 0.42
    assert chromosome.get_fitness(fitness_function) == 0.23


def test_add_fitness(chromosome, fitness_function):
    chromosome.add_fitness(
        fitness_function=fitness_function,
        fitness_value=0.42,
        coverage=0.23,
        num_covered_goals=21,
    )
    assert chromosome.fitness_values[fitness_function] == 0.42
    assert chromosome.previous_fitness_values[fitness_function] == 0.42
    assert chromosome.coverage_values[fitness_function] == 0.23
    assert chromosome.nums_covered_goals[fitness_function] == 21
    assert chromosome.nums_not_covered_goals[fitness_function] == -1


def test_coverage(chromosome, fitness_function):
    fv = {fitness_function: 0.42, MagicMock(ff.FitnessFunction): 0.23}
    chromosome.coverage_values = fv
    assert chromosome.coverage == 0.325


def test_coverage_no_values(chromosome):
    assert chromosome.coverage == 0.0


def test_get_set_coverage(chromosome, fitness_function):
    chromosome.set_coverage(fitness_function, 0.42)
    assert chromosome.get_coverage(fitness_function) == 0.42


def test_number_of_evaluations(chromosome):
    chromosome.increase_number_of_evaluations()
    assert chromosome.number_of_evaluations == 1


def test_get_set_num_covered_goals(chromosome, fitness_function):
    chromosome.set_num_covered_goals(fitness_function, 42)
    assert chromosome.get_num_covered_goals(fitness_function) == 42


def test_num_of_covered_goals(chromosome, fitness_function):
    covered_goal = {fitness_function: 42, MagicMock(ff.FitnessFunction): 23}
    chromosome.nums_covered_goals = covered_goal
    assert chromosome.num_of_covered_goals == 65


def test_num_of_not_covered_goals(chromosome, fitness_function):
    goal = {fitness_function: 42, MagicMock(ff.FitnessFunction): 23}
    chromosome.nums_not_covered_goals = goal
    assert chromosome.num_of_not_covered_goals == 65


def test_get_fitness_instance_of_not_existing(chromosome, fitness_value):
    chromosome.fitness_values = fitness_value
    assert chromosome.get_fitness_instance_of(_DummyFitnessFunction) == 0


def test_get_fitness_instance_of_existing(chromosome):
    chromosome.fitness_values = {_DummyFitnessFunction(): 0.42}
    assert chromosome.get_fitness_instance_of(_DummyFitnessFunction) == 0.42


def test_get_coverage_instance_of_non_existing(chromosome, coverage_value):
    chromosome.coverage_values = coverage_value
    assert chromosome.get_coverage_instance_of(_DummyFitnessFunction) == 0


def test_get_coverage_instance_of_existing(chromosome):
    chromosome.coverage_values = {_DummyFitnessFunction(): 0.42}
    assert chromosome.get_coverage_instance_of(_DummyFitnessFunction) == 0.42


def test_set_changed(chromosome):
    chromosome.set_changed(False)
    assert not chromosome.changed
