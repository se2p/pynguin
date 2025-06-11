#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""
from __future__ import annotations

import abc
import enum
import logging
from abc import abstractmethod, ABC
from typing import cast

from mypy.typeops import false_only

import pynguin.configuration as config
from pynguin.ga.chromosome import Chromosome
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import Statement, NoneStatement, PrimitiveStatement, FunctionStatement, MethodStatement, \
    ConstructorStatement, BooleanPrimitiveStatement, IntPrimitiveStatement, EnumPrimitiveStatement, \
    FloatPrimitiveStatement, StringPrimitiveStatement
from tests.testcase.execution.test_executionresult import execution_result


class StatementLocalSearch(abc.ABC):
    """An abstract local search strategy for statements."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        """TODO"""

    @abstractmethod
    def search(self, chromosome: TestCaseChromosome,position: int, objective: LocalSearchObjective) -> None:
        """Applies local search to a specific statement of the chromosome.

        Args:
            chromosome: The chromosome on which the local search will be applied.
            position: The position of the statement in the chromosome.
            objective: The local search objective of the chromosome.
        """

    @staticmethod
    def choose_local_search_statement(statement: Statement) -> StatementLocalSearch | None:
        logger = logging.getLogger(__name__)
        logger.debug("Choose local search statement from statement")
        if isinstance(statement, NoneStatement):
            logger.debug("No None local search statement found")
            pass
        elif isinstance(statement, EnumPrimitiveStatement):
            logger.debug("Statement is enum {}".format(statement.value))
            return EnumLocalSearch()
        elif isinstance(statement, PrimitiveStatement):
            primitive_type = statement.value
            if isinstance(primitive_type, bool):
                logger.debug("Primitive type is bool {}".format(primitive_type))
                return BooleanLocalSearch()
            elif isinstance(primitive_type, int):
                logger.debug("Primitive type is int with value {}".format(primitive_type))
                return IntegerLocalSearch()
            elif isinstance(primitive_type, str):
                logger.debug("Primitive type is str {}".format(primitive_type))
            elif isinstance(primitive_type, float):
                logger.debug("Primitive type is float {}".format(primitive_type))
            elif isinstance(primitive_type, complex):
                logger.debug("Primitive type is complex {}".format(primitive_type))
            elif isinstance(primitive_type, bytes):
                logger.debug("Primitive type is bytes {}".format(primitive_type))
            else:
                logger.debug("Unknown primitive type {}".format(primitive_type))
        elif isinstance(statement, FunctionStatement):
            logger.debug("No function local search statement found")
            pass
        elif isinstance(statement, MethodStatement):
            logger.debug("No method local search statement found")
            pass
        elif isinstance(statement, ConstructorStatement):
            logger.debug("No constructor search statement found")
            pass
        return None


class BooleanLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for booleans."""

    def search(self, chromosome: TestCaseChromosome, position: int, objective: LocalSearchObjective) -> None:
        statement = cast(BooleanPrimitiveStatement,chromosome.test_case.statements[position])
        execution_result = chromosome.get_last_execution_result()
        old_value = statement.value

        statement.value = not old_value

        if not objective.has_improved(chromosome):
            statement.value = old_value
            chromosome.set_last_execution_result(execution_result)
            chromosome.changed = False

class NumericalLocalSearch(StatementLocalSearch, ABC):
    """An abstract local search strategy for numerical variables."""

    def iterate(self, chromosome: TestCaseChromosome, statement: PrimitiveStatement, objective: LocalSearchObjective, delta, increasing_factor) -> bool:
        """Executes one or several iterations of applying a delta to the value of the statement. The delta increases each iteration.

        Args:
            chromosome (TestCaseChromosome): The chromosome of the statement to be iterated.
            statement (PrimitiveStatement): The statement to be iterated.
            objective (LocalSearchObjective): The objective which defines the improvements made mutating.
            delta: The value which is used for starting the iterations.

        Returns:
            Gives back True, if at least one iteration increased the fitness.

        """
        self._logger.debug("Incrementing value of {} with delta {} ".format(statement.value, delta))
        improved = False
        current_value = statement.value
        last_execution_result = chromosome.get_last_execution_result()
        statement.value += delta

        while objective.has_improved(chromosome):
            self._logger.debug("Incrementing value of {} with delta {} ".format(statement.value, delta))
            current_value = statement.value
            last_execution_result = chromosome.get_last_execution_result()
            improved = True
            delta *= increasing_factor
            statement.value += delta

        statement.value = current_value
        chromosome.set_last_execution_result(last_execution_result)
        return improved

class IntegerLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for integers."""

    def search(self, chromosome: TestCaseChromosome,position: int, objective: LocalSearchObjective) -> None:
        statement = cast(IntPrimitiveStatement, chromosome.test_case.statements[position])
        old_value = statement.value
        increasing_factor = config.LocalSearchConfiguration.int_delta_increasing_factor

        done = False
        improved = False

        while not done and not LocalSearchTimer.get_instance().limit_reached():
            done = True

            if self.iterate(chromosome, statement, objective, 1, increasing_factor):
                self._logger.debug("Successfully incremented value of {} to {} ".format(old_value, statement.value))
                done = False
                improved = True
            elif self.iterate(chromosome, statement, objective, -1, increasing_factor):
                self._logger.debug("Successfully decremented value of {} to {} ".format(old_value, statement.value))
                done = False
                improved = True
            old_value = statement.value
        if not improved:
            chromosome.changed = False

class EnumLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for enumerations."""

    def search(self, chromosome: TestCaseChromosome,position: int, objective: LocalSearchObjective) -> None:
        statement = cast(EnumPrimitiveStatement, chromosome.test_case.statements[position])
        initial_value = statement.value
        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value

        for value in range(len(statement.accessible_object().names)):
            if value != initial_value:
                if not objective.has_improved(chromosome):
                    statement.value = old_value
                    chromosome.set_last_execution_result(last_execution_result)
                    chromosome.changed = False
                else:
                    self._logger.debug("")




class FloatLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for floats."""

    def search(self, chromosome: TestCaseChromosome, position: int, objective: LocalSearchObjective) -> None:
        pass

class StringLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for strings."""

    def search(self, chromosome: TestCaseChromosome, position: int,  objective: LocalSearchObjective) -> None:
        statement = cast(EnumPrimitiveStatement, chromosome.test_case.statements[position])

        if self.apply_random_mutations(chromosome,position,objective):
            pass


    def apply_random_mutations(self, chromosome: TestCaseChromosome, position: int,  objective: LocalSearchObjective) -> bool:
        """Applies a number of random mutations to the string.

        Args:
            chromosome: The chromosome to mutate.
            position: The position of the statement which gets mutated.
            objective: The objective which defines the improvements made mutating.

        Returns:
            Gives back true if the mutations change the fitness in any way.
        """
        statement = cast(StringPrimitiveStatement, chromosome.test_case.statements[position])
        random_mutations_count = config.LocalSearchConfiguration.string_random_mutation_count
        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value
        while random_mutations_count > 0 :
            statement.randomize_value()

            improvement = objective.has_changed(chromosome)
            if improvement < 0:
                chromosome.set_last_execution_result(last_execution_result)
                statement.value = old_value
                chromosome.changed = False

            if improvement != 0:
                self._logger.debug("The random mutations have changed the fitness of {}, applying local search".format(chromosome.test_case.statements[position]))
                return True
            random_mutations_count -= 1
        self._logger.debug("The random mutations have no impact on the fitness, aborting local search")
        return False



