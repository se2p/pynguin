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
import sys

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import cast

import pynguin.configuration as config

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.testcase.execution import ExecutionResult
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import BooleanPrimitiveStatement
from pynguin.testcase.statement import ComplexPrimitiveStatement
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import EnumPrimitiveStatement
from pynguin.testcase.statement import FloatPrimitiveStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import MethodStatement
from pynguin.testcase.statement import NoneStatement
from pynguin.testcase.statement import ParametrizedStatement
from pynguin.testcase.statement import PrimitiveStatement
from pynguin.testcase.statement import Statement
from pynguin.testcase.statement import StringPrimitiveStatement
from pynguin.testcase.statement import VariableCreatingStatement
from pynguin.utils import randomness


if TYPE_CHECKING:
    from pynguin.testcase.localsearchobjective import LocalSearchObjective
    from pynguin.testcase.testfactory import TestFactory


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
            logger.debug("Statement is enum %r", statement.value)
            return EnumLocalSearch()
        if isinstance(statement, PrimitiveStatement):
            primitive_type = statement.value
            if isinstance(primitive_type, bool):
                logger.debug("Primitive type is bool %s", primitive_type)
                return BooleanLocalSearch()
            if isinstance(primitive_type, int):
                logger.debug("Primitive type is int %d", primitive_type)
                return IntegerLocalSearch()
            if isinstance(primitive_type, str):
                logger.debug("Primitive type is string %s", primitive_type)
                # return StringLocalSearch()
            if isinstance(primitive_type, float):
                logger.debug("Primitive type is float %f", primitive_type)
                return FloatLocalSearch()
            if isinstance(primitive_type, complex):
                logger.debug("Primitive type is complex %s", primitive_type)
            elif isinstance(primitive_type, bytes):
                logger.debug("Primitive type is bytes %s", primitive_type)
            else:
                logger.debug("Unknown primitive type: %s", primitive_type)
        elif (
            isinstance(statement, FunctionStatement)
            | isinstance(statement, ConstructorStatement)
            | isinstance(statement, MethodStatement)
        ):
            logger.debug("%s statement found", statement.__class__.__name__)
            return ParametrizedStatementLocalSearch()
        else:
            logger.debug("No local search statement found for %s", statement.__class__.__name__)
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
    """An abstract local search strategy for iterable variables."""

    def iterate(
        self,
        chromosome: TestCaseChromosome,
        statement: PrimitiveStatement,
        objective: LocalSearchObjective,
        delta,
        increasing_factor,
    ) -> bool:
        """Executes one or several iterations of applying a delta to the value of the statement. The
        delta increases each iteration.

        Args:
            chromosome (TestCaseChromosome): The chromosome of the statement to be iterated.
            statement (PrimitiveStatement): The statement to be iterated.
            objective (LocalSearchObjective): The objective which defines the improvements made
                mutating.
            delta: The value which is used for starting the iterations.
            increasing_factor: The factor which describes how much the delta is increased each
                iteration.

        Returns:
            Gives back True, if at least one iteration increased the fitness.

        """  # noqa: D205
        self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
        improved = False
        current_value = statement.value
        last_execution_result = chromosome.get_last_execution_result()
        statement.value += delta
        while (
            objective.has_improved(chromosome)
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
            current_value = statement.value
            last_execution_result = chromosome.get_last_execution_result()
            improved = True
            delta *= increasing_factor
            statement.value += delta
        statement.value = current_value
        chromosome.set_last_execution_result(last_execution_result)
        return improved

    def iterate_directions(
        self,
        chromosome: TestCaseChromosome,
        statement: PrimitiveStatement,
        objective: LocalSearchObjective,
        delta,
        factor,
    ) -> bool:
        """Iterates through the different iterations of negative/positive increases of a value
        until no improvement is registered anymore.

        Args:
            chromosome (TestCaseChromosome): The chromosome of the statement to be iterated.
            statement (PrimitiveStatement): The statement to be iterated.
            objective (LocalSearchObjective): The objective which defines the improvements made.
            delta: The value by how much the original value is increased in the first iteration.
            factor: The factor which describes how much the delta is increased each iteration.

        Returns:
            Gives back True, if at least one iteration increased the fitness.
        """  # noqa: D205
        old_value = statement.value

        done = False
        improved = False

        while not done and not LocalSearchTimer.get_instance().limit_reached():
            done = True
            if self.iterate(chromosome, statement, objective, delta, factor):
                self._logger.debug(
                    "Successfully incremented value of %s to %s ", old_value, statement.value
                )
                done = False
                improved = True
            elif self.iterate(chromosome, statement, objective, (-1) * delta, factor):
                self._logger.debug(
                    "Successfully decremented value of %s to %s ", old_value, statement.value
                )
                done = False
                improved = True
            old_value = statement.value
        if not improved:
            chromosome.changed = False
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
        if self.iterate_directions(chromosome, statement, objective, 1, increasing_factor):
            self._logger.debug(
                "Successfully increased value of %s to %s ", old_value, statement.value
            )
        else:
            self._logger.debug(
                "Local search couldn't find a better int value for %s", statement.value
            )


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
        statement = cast("FloatPrimitiveStatement", chromosome.test_case.statements[position])
        improved = False
        original_value = statement.value
        increasing_factor = config.LocalSearchConfiguration.int_delta_increasing_factor
        if self.iterate_directions(chromosome, statement, objective, 1, increasing_factor):
            improved = True

        precision = 1
        while (
            precision <= sys.float_info.dig and not LocalSearchTimer.get_instance().limit_reached()
        ):
            last_execution_result = chromosome.get_last_execution_result()
            old_value = statement.value
            statement.value = round(statement.value, precision)
            if objective.has_changed(chromosome) < 0:
                chromosome.set_last_execution_result(last_execution_result)
                statement.value = old_value
            self._logger.debug("Starting local search with precision %s", precision)
            if self.iterate_directions(
                chromosome, statement, objective, 10.0 ** (-precision), increasing_factor
            ):
                improved = True
            precision += 1

        if improved:
            self._logger.debug(
                "Local search successfully changed value of the float from %f to %f",
                original_value,
                statement.value,
            )
        else:
            self._logger.debug(
                "Local search could not find a better float for float %f", statement.value
            )


class ComplexLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for complex numbers."""

    def search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ) -> None:
        statement = cast("ComplexPrimitiveStatement", chromosome.test_case.statements[position])
        old_value = statement.value
        done = False
        factor = config.LocalSearchConfiguration.int_delta_increasing_factor
        improved = False

        # First improve the real part and then the imaginary part of the complex number
        while not done and not LocalSearchTimer.get_instance().limit_reached():
            done = True
            if self.iterate_complex(chromosome, statement, objective, False, 1.0, factor):  # noqa: FBT003
                self._logger.debug(
                    "Successfully incremented real part of %s to %s ", old_value, statement.value
                )
                done = False
                improved = True
            elif self.iterate_complex(chromosome, statement, objective, False, -1.0, factor):  # noqa: FBT003
                self._logger.debug(
                    "Successfully decremented real part of %s to %s ", old_value, statement.value
                )
                done = False
                improved = True
            old_value = statement.value

        done = False
        while not done and not LocalSearchTimer.get_instance().limit_reached():
            done = True
            if self.iterate_complex(chromosome, statement, objective, True, 1.0, factor):  # noqa: FBT003
                self._logger.debug(
                    "Successfully incremented imaginary part of %s to %s ",
                    old_value,
                    statement.value,
                )
                done = False
                improved = True
            elif self.iterate_complex(chromosome, statement, objective, True, -1.0, factor):  # noqa: FBT003
                self._logger.debug(
                    "Successfully decremented imaginary part of %s to %s ",
                    old_value,
                    statement.value,
                )
                done = False
                improved = True
            old_value = statement.value
        if improved:
            self._logger.debug("Local search successfully changed the value of the complex number")
        else:
            self._logger.debug("Local search could not find a better complex number")

    def iterate_complex(  # noqa: PLR0917
        self,
        chromosome: TestCaseChromosome,
        statement: ComplexPrimitiveStatement,
        objective: LocalSearchObjective,
        imaginary: bool,  # noqa: FBT001
        delta: float,
        factor: float,
    ) -> bool:
        """Executes one or several iterations of applying a delta to the value of the statement. The
        delta increases each iteration.

        Args:
            chromosome (TestCaseChromosome): The chromosome of the statement to be iterated.
            statement (ComplexPrimitiveStatement): The complex statement to be iterated.
            objective (LocalSearchObjective): The objective which defines the improvements made
                mutating.
            imaginary (bool): Whether the iteration should happen on the imaginary part or the
                real part of the complex value.
            delta: The value which is used for starting the iterations.
            factor: The factor which describes how much the delta is increased each iteration.

        Returns:
            Gives back True, if at least one iteration increased the fitness.
        """  # noqa: D205
        self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
        improved = False
        current_value = statement.value
        last_execution_result = chromosome.get_last_execution_result()
        if imaginary:
            statement.value = complex(statement.value.real, statement.value.imag + delta)
        else:
            statement.value = complex(statement.value.real + delta, statement.value.imag)
        while (
            objective.has_improved(chromosome)
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
            current_value = statement.value
            last_execution_result = chromosome.get_last_execution_result()
            improved = True
            delta *= factor
            if imaginary:
                statement.value = complex(statement.value.real, statement.value.imag + delta)
            else:
                statement.value = complex(statement.value.real + delta, statement.value.imag)
        statement.value = current_value
        chromosome.set_last_execution_result(last_execution_result)
        return improved


class StringLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for strings."""

    _changed: bool = False
    _last_execution_result: ExecutionResult = None
    _old_value = None

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
        self._backup(chromosome, statement)
        while random_mutations_count > 0:
            statement.randomize_value()

            improvement = objective.has_changed(chromosome)
            if improvement < 0:
                self._restore(chromosome, statement)

            if improvement != 0:
                self._logger.debug(
                    "The random mutations have changed the fitness of %r, applying local search",
                    chromosome.test_case.statements[position],
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
        """Removes each character from the string.

        If an improvement to the string is found, the character is removed., otherwise the old
        string is restored.

        Args:
            chromosome (TestCaseChromosome): The chromosome to mutate.
            position(int): The position of the statement which gets mutated.
            objective(LocalSearchObjective): The objective which defines the improvements made
                mutating.
        """
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])
        assert statement.value is not None
        self._backup(chromosome, statement)
        for i in range(len(statement.value) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            self._logger.debug("Removing character %d from string %r", i, statement.value)
            statement.value = statement.value[:i] + statement.value[i + 1 :]
            if objective.has_improved(chromosome):
                self._logger.debug("Removing the character has improved the fitness.")
                self._backup(chromosome, statement)
            else:
                self._restore(chromosome, statement)

    def replace_chars(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
    ):
        """Replaces each character with every other possible character until successful
        replacement.

        Args:
            chromosome(TestCaseChromosome): The chromosome to mutate.
            position(int): The position of the statement which gets mutated.
            objective(LocalSearchObjective): The objective which defines the improvements made
                mutating.
        """  # noqa: D205
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])

        old_changed = chromosome.changed
        improved = False
        self._backup(chromosome, statement)
        for i in range(len(statement.value) - 1, -1, -1):
            finished = False

            while not finished:
                finished = True
                old_value = statement.value
                if self.iterate_string(chromosome, statement, objective, i, 1):
                    finished = False
                    improved = True
                if self.iterate_string(chromosome, statement, objective, i, -1):
                    finished = False
                    improved = True
                if not finished:
                    self._logger.debug(
                        "Successfully replaced character %d from string %r to %r",
                        i,
                        old_value,
                        statement.value,
                    )
        if not improved:
            chromosome.changed = old_changed

    def add_chars(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
    ) -> None:
        """Tries to add a character at each position of the string. If the addition was
        successful, the best char for this position is evaluated.

        Args:
            chromosome(TestCaseChromosome): The chromosome to mutate.
            position(int): The position of the statement which gets mutated.
            objective(LocalSearchObjective): The objective which defines the improvements made
                mutating.
        """  # noqa: D205
        statement = cast("StringPrimitiveStatement", chromosome.test_case.statements[position])
        self._backup(chromosome, statement)
        for i in range(0, len(statement.value) + 1, 1):
            statement.value = statement.value[:i] + chr(97) + statement.value[i:]
            # TODO: Which is best char to start with (maybe the one in the middle?)
            self._logger.debug(
                "Starting to add character at position %d from string %r", i, statement.value
            )
            if objective.has_improved(chromosome):
                self._backup(chromosome, statement)
                finished = False

                while not finished:
                    finished = True
                    if self.iterate_string(chromosome, statement, objective, i, 1):
                        finished = False
                    if self.iterate_string(chromosome, statement, objective, i, -1):
                        finished = False

                self._logger.debug(
                    "Successfully added character at position %d to string %r",
                    i,
                    statement.value,
                )
            else:
                self._restore(chromosome, statement)
                self._logger.debug(
                    "Inserting a letter at position %d of string %r has no positive impact.",
                    i,
                    statement.value,
                )

    def _backup(self, chromosome: TestCaseChromosome, statement: StringPrimitiveStatement):
        self._last_execution_result = chromosome.get_last_execution_result()
        self._old_value = statement.value
        self._old_changed = chromosome.changed

    def _restore(self, chromosome: TestCaseChromosome, statement: StringPrimitiveStatement):
        chromosome.set_last_execution_result(self._last_execution_result)
        chromosome.changed = self._old_changed
        statement.value = self._old_value

    def iterate_string(
        self,
        chromosome: TestCaseChromosome,
        statement: StringPrimitiveStatement,
        objective: LocalSearchObjective,
        char_position: int,
        delta: int,
    ) -> bool:
        """Iterates through all possible characters at the specified position, but only in one
        direction.

        Args:
            chromosome (TestCaseChromosome): The chromosome to mutate.
            statement (StringPrimitiveStatement): The statement containing the string.
            objective (LocalSearchObjective): The objective which defines the improvements made
                mutating.
            char_position (int): The position of the character which gets mutated.
            delta (int): The value which is used for starting the iterations.

        Returns:
              Gives back true, if at least one iteration was successful.
        """  # noqa: D205
        self._backup(chromosome, statement)
        if (
            ord(statement.value[char_position]) + delta > sys.maxunicode
            or ord(statement.value[char_position]) + delta < 0
        ):
            return False
        self._replace_single_char(statement, char_position, delta)
        improved = False
        while objective.has_improved(chromosome):
            improved = True
            chromosome.changed = True
            self._backup(chromosome, statement)
            if LocalSearchTimer.get_instance().limit_reached():
                break
            delta *= config.LocalSearchConfiguration.int_delta_increasing_factor
            if (
                ord(statement.value[char_position]) + delta > sys.maxunicode
                or ord(statement.value[char_position]) + delta < 0
            ):
                return improved
            self._replace_single_char(statement, char_position, delta)
        self._restore(chromosome, statement)
        return improved

    def _replace_single_char(
        self, statement: StringPrimitiveStatement, char_position: int, delta: int
    ) -> None:
        new_char = chr(ord(statement.value[char_position]) + delta)
        statement.value = (
            statement.value[:char_position] + new_char + statement.value[char_position + 1 :]
        )
        self._logger.debug(
            "Changed letter %d of string %r to %r",
            char_position,
            self._old_value,
            statement.value,
        )


class ParametrizedStatementLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for parametrized statements."""

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
        if not (isinstance(statement, ParametrizedStatement | NoneStatement)):
            self._logger.debug(
                "Error! The statement at position %d has to be a ParametrizedStatement or "
                "NoneStatement",
                position,
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
            if random == Operations.RANDOM_CALL:
                changed = self.random_call(chromosome, position, factory)
            elif random == Operations.PARAMETER:
                changed = self.random_parameter(chromosome, position, factory)
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
        """Replaces a call with another possible call.

        Args:
            chromosome (TestCaseChromosome): The testcase which gets modified.
            position (int): The position of the statement which gets replaced.
            factory (TestFactory): The test factory

        Returns:
            Gives back true if replacing the call was successful and false otherwise.
        """
        statement = chromosome.test_case.statements[position]
        successful = False
        if isinstance(statement, VariableCreatingStatement):
            successful = factory.change_random_call(chromosome.test_case, statement)
            if successful:
                self._logger.debug(
                    "Successfully replaced call %s with another possible call %s",
                    statement.get_variable_references(),
                    chromosome.test_case.statements[position].get_variable_references(),
                )
            else:
                self._logger.debug("Failed to replace call with another possible call")

        return successful

    def random_call(
        self, chromosome: TestCaseChromosome, position: int, factory: TestFactory
    ) -> bool:
        """Adds a random call on the object at the position.

        Args:
            chromosome (TestCaseChromosome): The testcase which gets modified.
            position (int): The position of the object on which the random call gets added.
            factory (TestFactory): The test factory

        Returns:
            Gives back true if the addition of a random call was successful and false otherwise.
        """
        statement = chromosome.test_case.statements[position]
        successful = False
        if isinstance(statement, VariableCreatingStatement):
            variable = statement.ret_val
            successful = factory.insert_random_call_on_object_at(
                chromosome.test_case, variable, position + 1
            )
            if successful:
                self._logger.debug(
                    "Successfully inserted random %s call at position %d",
                    chromosome.test_case.statements[position + 1].ret_val,
                    position + 1,
                )
        return successful

    def random_parameter(
        self, chromosome: TestCaseChromosome, position: int, factory: TestFactory
    ) -> bool:
        """Mutates a random parameter of the method call.

        Args:
            chromosome (TestCaseChromosome): The testcase which gets modified.
            position (int): The position of the method call whose parameter is being mutated.
            factory (TestFactory): The test factory

        Returns:
            Gives back true if the mutation was successful and false otherwise.
        """
        # TODO:
