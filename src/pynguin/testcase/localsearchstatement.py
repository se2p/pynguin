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

from abc import ABC
from abc import abstractmethod
from typing import cast

import pynguin.configuration as config

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import BooleanPrimitiveStatement
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import EnumPrimitiveStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import MethodStatement
from pynguin.testcase.statement import NoneStatement
from pynguin.testcase.statement import ParametrizedStatement
from pynguin.testcase.statement import PrimitiveStatement
from pynguin.testcase.statement import Statement
from pynguin.testcase.statement import StringPrimitiveStatement
from pynguin.testcase.statement import VariableCreatingStatement
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils import randomness


class StatementLocalSearch(abc.ABC):
    """An abstract local search strategy for statements."""

    _logger = logging.getLogger(__name__)

    @abstractmethod
    def search(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None,
    ) -> None:
        """Applies local search to a specific statement of the chromosome.

        Args:
            chromosome: The chromosome on which the local search will be applied.
            position: The position of the statement in the chromosome.
            objective: The local search objective of the chromosome.
            factory: The factory for modifying the test case chromosome
        """

    @staticmethod
    def choose_local_search_statement(
        statement: Statement,
    ) -> StatementLocalSearch | None:
        logger = logging.getLogger(__name__)
        logger.debug("Choose local search statement from statement")
        if isinstance(statement, NoneStatement):
            logger.debug("None local search statement found")
            return ParametrizedStatementLocalSearch()
        if isinstance(statement, EnumPrimitiveStatement):
            logger.debug(f"Statement is enum {statement.value}")
            return EnumLocalSearch()
        if isinstance(statement, PrimitiveStatement):
            primitive_type = statement.value
            if isinstance(primitive_type, bool):
                logger.debug(f"Primitive type is bool {primitive_type}")
                return BooleanLocalSearch()
            if isinstance(primitive_type, int):
                logger.debug(f"Primitive type is int with value {primitive_type}")
                return IntegerLocalSearch()
            if isinstance(primitive_type, str):
                logger.debug(f"Primitive type is string {primitive_type}")
                return StringLocalSearch()
            if isinstance(primitive_type, float):
                logger.debug(f"Primitive type is float {primitive_type}")
            elif isinstance(primitive_type, complex):
                logger.debug(f"Primitive type is complex {primitive_type}")
            elif isinstance(primitive_type, bytes):
                logger.debug(f"Primitive type is bytes {primitive_type!r}")
            else:
                logger.debug(f"Unknown primitive type {primitive_type}")
        elif isinstance(statement, FunctionStatement):
            logger.debug("Function local search statement found")
            return ParametrizedStatementLocalSearch()
        elif isinstance(statement, MethodStatement):
            logger.debug("Method local search statement found")
            return ParametrizedStatementLocalSearch()
        elif isinstance(statement, ConstructorStatement):
            logger.debug("Constructor search statement found")
            return ParametrizedStatementLocalSearch()
        else:
            logger.debug(f"No local search statement found for {statement.__class__.__name__}")
        return None


class BooleanLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for booleans."""

    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ) -> None:
        statement = cast("BooleanPrimitiveStatement", chromosome.test_case.statements[position])
        execution_result = chromosome.get_last_execution_result()
        old_value = statement.value

        statement.value = not old_value

        if not objective.has_improved(chromosome):
            statement.value = old_value
            chromosome.set_last_execution_result(
                execution_result
            ) if execution_result is not None else None
            chromosome.changed = False


class NumericalLocalSearch(StatementLocalSearch, ABC):
    """An abstract local search strategy for numerical variables."""

    def iterate(
        self,
        chromosome: TestCaseChromosome,
        statement: PrimitiveStatement,
        objective: LocalSearchObjective,
        delta,
        increasing_factor,
    ) -> bool:
        """Executes one or several iterations of applying a delta to the value of the statement. The delta increases each iteration.

        Args:
            chromosome (TestCaseChromosome): The chromosome of the statement to be iterated.
            statement (PrimitiveStatement): The statement to be iterated.
            objective (LocalSearchObjective): The objective which defines the improvements made mutating.
            delta: The value which is used for starting the iterations.
            increasing_factor: The factor which describes how much the delta is increased each iteration.

        Returns:
            Gives back True, if at least one iteration increased the fitness.

        """
        self._logger.debug(f"Incrementing value of {statement.value} with delta {delta} ")
        improved = False
        current_value = statement.value
        last_execution_result = chromosome.get_last_execution_result()
        statement.value += delta

        while objective.has_improved(chromosome):
            self._logger.debug(f"Incrementing value of {statement.value} with delta {delta} ")
            current_value = statement.value
            last_execution_result = chromosome.get_last_execution_result()
            improved = True
            delta *= increasing_factor
            statement.value += delta
            if LocalSearchTimer.get_instance().limit_reached():
                break

        statement.value = current_value
        chromosome.set_last_execution_result(
            last_execution_result
        ) if last_execution_result is not None else None
        return improved


class IntegerLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for integers."""

    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ) -> None:
        statement = cast("IntPrimitiveStatement", chromosome.test_case.statements[position])
        old_value = statement.value
        increasing_factor = config.LocalSearchConfiguration.int_delta_increasing_factor

        done = False
        improved = False

        while not done and not LocalSearchTimer.get_instance().limit_reached():
            done = True
            if LocalSearchTimer.get_instance().limit_reached():
                break
            if self.iterate(chromosome, statement, objective, 1, increasing_factor):
                self._logger.debug(
                    f"Successfully incremented value of {old_value} to {statement.value} "
                )
                done = False
                improved = True
            elif self.iterate(chromosome, statement, objective, -1, increasing_factor):
                self._logger.debug(
                    f"Successfully decremented value of {old_value} to {statement.value} "
                )
                done = False
                improved = True
            old_value = statement.value
        if not improved:
            chromosome.changed = False


class EnumLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for enumerations."""

    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ) -> None:
        statement = cast("EnumPrimitiveStatement", chromosome.test_case.statements[position])
        initial_value = statement.value
        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value

        for value in range(len(statement.accessible_object().names)):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            if value != initial_value:
                if not objective.has_improved(chromosome):
                    statement.value = old_value
                    chromosome.set_last_execution_result(
                        last_execution_result
                    ) if last_execution_result is not None else None
                    chromosome.changed = False
                else:
                    self._logger.debug("Local search successfully found better enum value")
                    return


class FloatLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for floats."""

    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ) -> None:
        pass


class StringLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for strings."""

    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ) -> None:
        if self.apply_random_mutations(chromosome, position, objective):
            self._logger.debug("Removing characters from string")
            self.remove_chars(chromosome, position, objective)
            self._logger.debug("Replacing characters from string")
            self.replace_chars(chromosome, position, objective)
            self._logger.debug("Adding characters to the string")
            self.add_chars(chromosome, position, objective)

    def apply_random_mutations(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
    ) -> bool:
        """Applies a number of random mutations to the string.

        Args:
            chromosome: The chromosome to mutate.
            position: The position of the statement which gets mutated.
            objective: The objective which defines the improvements made mutating.

        Returns:
            Gives back true if the mutations change the fitness in any way.
        """
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])
        random_mutations_count = config.LocalSearchConfiguration.string_random_mutation_count
        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value
        while random_mutations_count > 0:
            statement.randomize_value()

            improvement = objective.has_changed(chromosome)
            if improvement < 0:
                chromosome.set_last_execution_result(
                    last_execution_result
                ) if last_execution_result is not None else None
                statement.value = old_value
                chromosome.changed = False

            if improvement != 0:
                self._logger.debug(
                    f"The random mutations have changed the fitness of {chromosome.test_case.statements[position]}, applying local search"
                )
                return True
            random_mutations_count -= 1
        self._logger.debug(
            "The random mutations have no impact on the fitness, aborting local search"
        )
        return False

    def remove_chars(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
    ):
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])
        assert statement.value is not None

        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value
        old_changed = chromosome.changed

        for i in range(len(statement.value) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            self._logger.debug(f"Removing character {i} from string")
            statement.value = statement.value[:i] + statement.value[i + 1 :]
            if objective.has_improved(chromosome):
                last_execution_result = chromosome.get_last_execution_result()
                old_value = statement.value
                old_changed = chromosome.changed
            else:
                chromosome.set_last_execution_result(
                    last_execution_result
                ) if last_execution_result is not None else None
                statement.value = old_value
                chromosome.changed = old_changed

    def replace_chars(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
    ):
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])

        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value
        old_changed = chromosome.changed

    def add_chars(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
    ):
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])

        last_execution_result = chromosome.get_last_execution_result()
        old_value = statement.value
        old_changed = chromosome.changed


class ParametrizedStatementLocalSearch(StatementLocalSearch, ABC):
    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None,
    ):
        assert factory is not None
        statement = chromosome.test_case.statements[position]
        mutations = 0
        if not (
            isinstance(statement, ParametrizedStatement) or isinstance(statement, NoneStatement)
        ):
            self._logger.debug(
                f"Error! The statement at position {position} has to be a ParametrizedStatement or NoneStatement"
            )
            return

        last_execution_result = chromosome.get_last_execution_result()
        old_chromosome = TestCaseChromosome(None, None, chromosome)

        class Operations(enum.Enum):
            REPLACE = 0
            RANDOM_CALL = 1
            PARAMETER = 2

        while (
            not LocalSearchTimer.get_instance().limit_reached()
            and mutations < config.LocalSearchConfiguration.random_parametrized_statement_call_count
        ):
            operations: list[Operations] = [Operations.REPLACE]
            if not isinstance(statement, NoneStatement):
                operations.append(Operations.RANDOM_CALL)
                if len(statement.args) > 0:  # type: ignore[attr-defined]
                    operations.append(Operations.PARAMETER)

            random = randomness.choice(operations)
            changed = False
            if random == Operations.RANDOM_CALL or random == Operations.PARAMETER:
                # TODO
                pass
            else:
                changed = self.replace(chromosome, position, factory)

            if changed and objective.has_improved(chromosome):
                last_execution_result = chromosome.get_last_execution_result()
                old_chromosome = chromosome
                mutations = 0
            else:
                chromosome = TestCaseChromosome(None, None, old_chromosome)
                chromosome.set_last_execution_result(
                    last_execution_result
                ) if last_execution_result is not None else None
                statement = chromosome.test_case.statements[position]
                mutations += 1

    def replace(self, chromosome: TestCaseChromosome, position: int, factory: TestFactory) -> bool:
        """Replaces a call with another possible call."""
        statement = chromosome.test_case.statements[position]
        successful = False
        if isinstance(statement, VariableCreatingStatement):
            successful = factory.change_random_call(chromosome.test_case, statement)
            if successful:
                self._logger.debug(
                    "Successfully replaced call {} with another possible call{}".format(
                        statement.get_variable_references(),
                        chromosome.test_case.statements[position].get_variable_references(),
                    )
                )
            else:
                self._logger.debug("Failed to replace call with another possible call")

        return successful
