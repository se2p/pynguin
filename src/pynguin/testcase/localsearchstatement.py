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
from pynguin.testcase.statement import BytesPrimitiveStatement
from pynguin.testcase.statement import ComplexPrimitiveStatement
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import EnumPrimitiveStatement
from pynguin.testcase.statement import FieldStatement
from pynguin.testcase.statement import FloatPrimitiveStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import MethodStatement
from pynguin.testcase.statement import NoneStatement
from pynguin.testcase.statement import ParametrizedStatement
from pynguin.testcase.statement import PrimitiveStatement
from pynguin.testcase.statement import StringPrimitiveStatement
from pynguin.testcase.statement import VariableCreatingStatement
from pynguin.utils import randomness


if TYPE_CHECKING:
    from pynguin.testcase.localsearchobjective import LocalSearchObjective
    from pynguin.testcase.testfactory import TestFactory


class StatementLocalSearch(abc.ABC):
    """An abstract local search strategy for statements."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory | None = None,
    ):
        self._chromosome = chromosome
        self._objective = objective
        self._position = position
        self._factory = factory

    @abstractmethod
    def search(self) -> None:
        """Applies local search to a specific statement of the chromosome."""

    @staticmethod
    def choose_local_search_statement(
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory,
    ) -> StatementLocalSearch | None:
        statement = chromosome.test_case.statements[position]
        logger = logging.getLogger(__name__)
        logger.debug("Choose local search statement from statement")
        if isinstance(statement, NoneStatement):
            logger.debug("None local search statement found")
            # return ParametrizedStatementLocalSearch(chromosome, position, objective, factory)
        elif isinstance(statement, EnumPrimitiveStatement):
            logger.debug("Statement is enum %r", statement.value)
            # return EnumLocalSearch(chromosome, position, objective)
        elif isinstance(statement, PrimitiveStatement):
            primitive_type = statement.value
            if isinstance(primitive_type, bool):
                logger.debug("Primitive type is bool %s", primitive_type)
                # return BooleanLocalSearch(chromosome, position, objective)
            elif isinstance(primitive_type, int):
                logger.debug("Primitive type is int %d", primitive_type)
                # return IntegerLocalSearch(chromosome, position, objective)
            elif isinstance(primitive_type, str):
                logger.debug("Primitive type is string %s", primitive_type)
                # return StringLocalSearch(chromosome, position, objective)
            elif isinstance(primitive_type, float):
                logger.debug("Primitive type is float %f", primitive_type)
                # return FloatLocalSearch(chromosome, position, objective)
            elif isinstance(primitive_type, complex):
                logger.debug("Primitive type is complex %s", primitive_type)
                # return ComplexLocalSearch(chromosome, position, objective)
            elif isinstance(primitive_type, bytes):
                logger.debug("Primitive type is bytes %s", primitive_type)
                # return BytesLocalSearch(chromosome, position, objective)
            else:
                logger.debug("Unknown primitive type: %s", primitive_type)
        elif (
            isinstance(statement, FunctionStatement)
            | isinstance(statement, ConstructorStatement)
            | isinstance(statement, MethodStatement)
        ):
            logger.debug("%s statement found", statement.__class__.__name__)
            # return ParametrizedStatementLocalSearch(chromosome, position, objective, factory)
        elif isinstance(statement, FieldStatement):
            logger.debug("%s statement found", statement.__class__.__name__)
            return FieldStatementLocalSearch(chromosome, position, objective)

        else:
            logger.debug("No local search statement found for %s", statement.__class__.__name__)
        return None


class BooleanLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for booleans."""

    def search(self) -> None:  # noqa: D102
        statement = cast(
            "BooleanPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        execution_result = self._chromosome.get_last_execution_result()
        old_value = statement.value

        statement.value = not old_value

        if not self._objective.has_improved(self._chromosome):
            statement.value = old_value
            self._chromosome.set_last_execution_result(
                execution_result
            ) if execution_result is not None else None
            self._chromosome.changed = False


class NumericalLocalSearch(StatementLocalSearch, ABC):
    """An abstract local search strategy for iterable variables."""

    def iterate(self, statement: PrimitiveStatement, delta, increasing_factor) -> bool:
        """Executes one or several iterations of applying a delta to the value of the statement. The
        delta increases each iteration.

        Args:
            statement (PrimitiveStatement): The statement to be iterated.
            delta: The value which is used for starting the iterations.
            increasing_factor: The factor which describes how much the delta is increased each
                iteration.

        Returns:
            Gives back True, if at least one iteration increased the fitness.

        """  # noqa: D205
        self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
        improved = False
        current_value = statement.value
        last_execution_result = self._chromosome.get_last_execution_result()
        statement.value += delta
        while (
            self._objective.has_improved(self._chromosome)
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
            current_value = statement.value
            last_execution_result = self._chromosome.get_last_execution_result()
            improved = True
            delta *= increasing_factor
            statement.value += delta
        statement.value = current_value
        self._chromosome.set_last_execution_result(last_execution_result)
        return improved

    def iterate_directions(
        self,
        statement: PrimitiveStatement,
        delta,
        factor,
    ) -> bool:
        """Iterates through the different iterations of negative/positive increases of a value
        until no improvement is registered anymore.

        Args:
            statement (PrimitiveStatement): The statement to be iterated.
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
            if self.iterate(statement, delta, factor):
                self._logger.debug(
                    "Successfully incremented value of %s to %s ", old_value, statement.value
                )
                done = False
                improved = True
            elif self.iterate(statement, (-1) * delta, factor):
                self._logger.debug(
                    "Successfully decremented value of %s to %s ", old_value, statement.value
                )
                done = False
                improved = True
            old_value = statement.value
        if not improved:
            self._chromosome.changed = False
        return improved


class IntegerLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for integers."""

    def search(  # noqa: D102
        self,
    ) -> None:
        statement = cast(
            "IntPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        old_value = statement.value
        increasing_factor = config.LocalSearchConfiguration.int_delta_increasing_factor
        if self.iterate_directions(statement, 1, increasing_factor):
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
    ) -> None:
        statement = cast(
            "EnumPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        initial_value = statement.value

        for value in range(len(statement.accessible_object().names)):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            last_execution_result = self._chromosome.get_last_execution_result()
            old_value = statement.value
            statement.value = value
            if value != initial_value:
                if not self._objective.has_improved(self._chromosome):
                    statement.value = old_value
                    self._chromosome.set_last_execution_result(
                        last_execution_result
                    ) if last_execution_result is not None else None
                    self._chromosome.changed = False
                else:
                    self._logger.debug("Local search successfully found better enum value")
                    return


class FloatLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for floats."""

    def search(  # noqa: D102
        self,
    ) -> None:
        statement = cast(
            "FloatPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        improved = False
        original_value = statement.value
        increasing_factor = config.LocalSearchConfiguration.int_delta_increasing_factor
        if self.iterate_directions(statement, 1, increasing_factor):
            improved = True

        precision = 1
        while (
            precision <= sys.float_info.dig and not LocalSearchTimer.get_instance().limit_reached()
        ):
            last_execution_result = self._chromosome.get_last_execution_result()
            old_value = statement.value
            statement.value = round(statement.value, precision)
            if self._objective.has_changed(self._chromosome) < 0:
                self._chromosome.set_last_execution_result(last_execution_result)
                statement.value = old_value
            self._logger.debug("Starting local search with precision %s", precision)
            if self.iterate_directions(statement, 10.0 ** (-precision), increasing_factor):
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

    def search(self) -> None:  # noqa: D102
        statement = cast(
            "ComplexPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        improved = False

        # First improve the real part and then the imaginary part of the complex number
        if self.iterate_precision(statement, False):  # noqa: FBT003
            improved = True
        if self.iterate_precision(statement, True):  # noqa: FBT003
            improved = True

        if improved:
            self._logger.debug("Local search successfully changed the value of the complex number")
        else:
            self._logger.debug("Local search could not find a better complex number")

    def iterate_precision(
        self,
        statement: ComplexPrimitiveStatement,
        imaginary: bool,  # noqa: FBT001
    ) -> bool:
        """Iterates through the different precision stages of floating point values.

        Args:
            statement (ComplexPrimitiveStatement): The complex statement to be iterated.
            imaginary (bool): Whether the iteration should happen on the imaginary part or the
                real part of the complex value.

        Returns:
            Gives back True, if at least one iteration increased the fitness.
        """
        improved = False
        if self.iterate_directions(statement, 1, imaginary):
            improved = True

        precision = 1
        while (
            precision <= sys.float_info.dig and not LocalSearchTimer.get_instance().limit_reached()
        ):
            self._logger.debug("Starting local search with precision %d", precision)
            if self.iterate_directions(statement, 10.0 ** (-precision), imaginary):
                improved = True
                last_execution_result = self._chromosome.get_last_execution_result()
                old_value = statement.value
                if imaginary:
                    statement.value = complex(
                        statement.value.real, round(statement.value.imag, precision)
                    )
                else:
                    statement.value = complex(
                        round(statement.value.real, precision), statement.value.imag
                    )
                if self._objective.has_changed(self._chromosome) < 0:
                    self._chromosome.set_last_execution_result(last_execution_result)
                    statement.value = old_value
            precision += 1
        return improved

    def iterate_directions(
        self,
        statement: ComplexPrimitiveStatement,
        delta: float,
        imaginary: bool,  # noqa: FBT001
    ) -> bool:
        """Iterates through the different directions (forwards/backwards).

        Args:
            statement (ComplexPrimitiveStatement): The complex statement to be iterated.
            imaginary (bool): Whether the iteration should happen on the imaginary part or the
                real part of the complex value.
            delta: The value which is used for starting the iterations.


        Returns:
            Gives back True, if at least one iteration increased the fitness.
        """
        improved = False
        info = "imaginary" if imaginary else "real"
        old_value = statement.value

        done = False
        while not done and not LocalSearchTimer.get_instance().limit_reached():
            done = True
            if self.iterate_complex(statement, imaginary, delta):
                (
                    self._logger.debug(
                        "Successfully incremented %r part of %s to %s ",
                        info,
                        old_value,
                        statement.value,
                    )
                )
                done = False
                improved = True
            elif self.iterate_complex(statement, imaginary, -delta):
                self._logger.debug(
                    "Successfully decremented %r part of %s to %s ",
                    info,
                    old_value,
                    statement.value,
                )
                done = False
                improved = True
            old_value = statement.value
        return improved

    def iterate_complex(
        self,
        statement: ComplexPrimitiveStatement,
        imaginary: bool,  # noqa: FBT001
        delta: float,
    ) -> bool:
        """Executes one or several iterations of applying a delta to the value of the statement. The
        delta increases each iteration.

        Args:
            statement (ComplexPrimitiveStatement): The complex statement to be iterated.
            imaginary (bool): Whether the iteration should happen on the imaginary part or the
                real part of the complex value.
            delta: The value which is used for starting the iterations.

        Returns:
            Gives back True, if at least one iteration increased the fitness.
        """  # noqa: D205
        self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
        factor = config.LocalSearchConfiguration.int_delta_increasing_factor

        improved = False
        current_value = statement.value
        last_execution_result = self._chromosome.get_last_execution_result()
        if imaginary:
            statement.value = complex(statement.value.real, statement.value.imag + delta)
        else:
            statement.value = complex(statement.value.real + delta, statement.value.imag)
        while (
            self._objective.has_improved(self._chromosome)
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
            current_value = statement.value
            last_execution_result = self._chromosome.get_last_execution_result()
            improved = True
            delta *= factor
            if imaginary:
                statement.value = complex(statement.value.real, statement.value.imag + delta)
            else:
                statement.value = complex(statement.value.real + delta, statement.value.imag)
        statement.value = current_value
        self._chromosome.set_last_execution_result(last_execution_result)
        return improved


class StringLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for strings."""

    _changed: bool = False
    _last_execution_result: ExecutionResult = None
    _old_value = None

    def search(self) -> None:  # noqa: D102
        if self.apply_random_mutations():
            self._logger.debug("Removing characters from string")
            self.remove_chars()
            self._logger.debug("Replacing characters from string")
            self.replace_chars()
            self._logger.debug("Adding characters to the string")
            self.add_chars()

    def apply_random_mutations(self) -> bool:
        """Applies a number of random mutations to the string.

        Returns:
            Gives back true if the mutations change the fitness in any way.
        """
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        random_mutations_count = config.LocalSearchConfiguration.string_random_mutation_count
        self._backup(statement)
        while random_mutations_count > 0:
            statement.randomize_value()

            improvement = self._objective.has_changed(self._chromosome)
            if improvement < 0:
                self._restore(statement)

            if improvement != 0:
                self._logger.debug(
                    "The random mutations have changed the fitness of %r, applying local search",
                    self._chromosome.test_case.statements[self._position],
                )
                return True
            random_mutations_count -= 1
        self._logger.debug(
            "The random mutations have no impact on the fitness, aborting local search"
        )
        return False

    def remove_chars(self):
        """Removes each character from the string.

        If an improvement to the string is found, the character is removed., otherwise the old
        string is restored.
        """
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        assert statement.value is not None
        self._backup(statement)
        for i in range(len(statement.value) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            self._logger.debug("Removing character %d from string %r", i, statement.value)
            statement.value = statement.value[:i] + statement.value[i + 1 :]
            if self._objective.has_improved(self._chromosome):
                self._logger.debug("Removing the character has improved the fitness.")
                self._backup(statement)
            else:
                self._restore(statement)

    def replace_chars(self):
        """Replaces each character with every other possible character until successful
        replacement.
        """  # noqa: D205
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )

        old_changed = self._chromosome.changed
        improved = False
        self._backup(statement)
        for i in range(len(statement.value) - 1, -1, -1):
            finished = False

            while not finished:
                finished = True
                old_value = statement.value
                if self.iterate_string(statement, i, 1):
                    finished = False
                    improved = True
                if self.iterate_string(statement, i, -1):
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
            self._chromosome.changed = old_changed

    def add_chars(self) -> None:
        """Tries to add a character at each position of the string. If the addition was
        successful, the best char for this position is evaluated.
        """  # noqa: D205
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)
        i = 0
        while i <= len(statement.value):
            statement.value = statement.value[:i] + chr(97) + statement.value[i:]
            # TODO: Which is best char to start with (maybe the one in the middle?)
            self._logger.debug(
                "Starting to add character at position %d from string %r", i, statement.value
            )
            if self._objective.has_improved(self._chromosome):
                self._backup(statement)
                finished = False

                while not finished:
                    finished = True
                    if self.iterate_string(statement, i, 1):
                        finished = False
                    if self.iterate_string(statement, i, -1):
                        finished = False

                self._logger.debug(
                    "Successfully added character at position %d to string %r",
                    i,
                    statement.value,
                )
            else:
                self._restore(statement)
                self._logger.debug(
                    "Inserting a letter at position %d of string %r has no positive impact.",
                    i,
                    statement.value,
                )
            i += 1

    def _backup(self, statement: StringPrimitiveStatement):
        self._last_execution_result = self._chromosome.get_last_execution_result()
        self._old_value = statement.value
        self._old_changed = self._chromosome.changed

    def _restore(self, statement: StringPrimitiveStatement):
        self._chromosome.set_last_execution_result(self._last_execution_result)
        self._chromosome.changed = self._old_changed
        statement.value = self._old_value

    def iterate_string(
        self,
        statement: StringPrimitiveStatement,
        char_position: int,
        delta: int,
    ) -> bool:
        """Iterates through all possible characters at the specified position, but only in one
        direction.

        Args:
            statement (StringPrimitiveStatement): The statement containing the string.
            char_position (int): The position of the character which gets mutated.
            delta (int): The value which is used for starting the iterations.

        Returns:
              Gives back true, if at least one iteration was successful.
        """  # noqa: D205
        self._backup(statement)
        if (
            ord(statement.value[char_position]) + delta > sys.maxunicode
            or ord(statement.value[char_position]) + delta < 0
        ):
            return False
        self._replace_single_char(statement, char_position, delta)
        improved = False
        while self._objective.has_improved(self._chromosome):
            improved = True
            self._chromosome.changed = True
            self._backup(statement)
            if LocalSearchTimer.get_instance().limit_reached():
                break
            delta *= config.LocalSearchConfiguration.int_delta_increasing_factor
            if (
                ord(statement.value[char_position]) + delta > sys.maxunicode
                or ord(statement.value[char_position]) + delta < 0
            ):
                return improved
            self._replace_single_char(statement, char_position, delta)
        self._restore(statement)
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

    def search(self):  # noqa: D102
        assert self._factory is not None
        statement = self._chromosome.test_case.statements[self._position]
        mutations = 0
        if not (isinstance(statement, ParametrizedStatement | NoneStatement)):
            self._logger.debug(
                "Error! The statement at position %d has to be a ParametrizedStatement or "
                "NoneStatement",
                self._position,
            )
            return

        last_execution_result = self._chromosome.get_last_execution_result()
        old_chromosome = TestCaseChromosome(None, None, self._chromosome)

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
                changed = self.random_call()
            elif random == Operations.PARAMETER:
                changed = self.random_parameter()
            else:
                changed = self.replace()

            if changed and self._objective.has_improved(self._chromosome):
                last_execution_result = self._chromosome.get_last_execution_result()
                old_chromosome = self._chromosome
                mutations = 0
            else:
                self._chromosome = TestCaseChromosome(None, None, old_chromosome)
                self._chromosome.set_last_execution_result(
                    last_execution_result
                ) if last_execution_result is not None else None
                statement = self._chromosome.test_case.statements[self._position]
                mutations += 1

    def replace(self) -> bool:
        """Replaces a call with another possible call.

        Returns:
            Gives back true if replacing the call was successful and false otherwise.
        """
        statement = self._chromosome.test_case.statements[self._position]
        successful = False
        if isinstance(statement, VariableCreatingStatement):
            successful = self._factory.change_random_call(self._chromosome.test_case, statement)
            if successful:
                self._logger.debug(
                    "Successfully replaced call %s with another possible call %s",
                    statement.get_variable_references(),
                    self._chromosome.test_case.statements[self._position].get_variable_references(),
                )
            else:
                self._logger.debug("Failed to replace call with another possible call")

        return successful

    def random_call(self) -> bool:
        """Adds a random call on the object at the position.

        Returns:
            Gives back true if the addition of a random call was successful and false otherwise.
        """
        statement = self._chromosome.test_case.statements[self._position]
        successful = False
        if isinstance(statement, VariableCreatingStatement):
            variable = statement.ret_val
            successful = self._factory.insert_random_call_on_object_at(
                self._chromosome.test_case, variable, self._position + 1
            )
            if successful:
                self._logger.debug(
                    "Successfully inserted random %s call at position %d",
                    self._chromosome.test_case.statements[self._position + 1].ret_val,
                    self._position + 1,
                )
        return successful

    def random_parameter(self) -> bool:
        """Mutates a random parameter of the method call.

        Returns:
            Gives back true if the mutation was successful and false otherwise.
        """
        statement = self._chromosome.test_case.statements[self._position]

        if isinstance(statement, FunctionStatement) | isinstance(statement, ConstructorStatement):
            return self._replace_parameter(statement)
        if isinstance(statement, MethodStatement):
            return self._replace_params_or_callee(statement)
        return False

    def _replace_parameter(self, statement: ParametrizedStatement) -> bool:
        params = statement.args.values()
        if len(params) == 0:
            return False
        parameter = randomness.choice(list(params))
        types = self._chromosome.test_case.get_objects(statement.ret_val.type, self._position)
        types.remove(statement.ret_val)
        if len(types) == 0:
            self._logger.debug(
                "No other possible calls found for datatype %r", statement.ret_val.type
            )
            return False
        new_parameter = randomness.choice(types)
        statement.replace(parameter, new_parameter)
        return True

    def _replace_params_or_callee(self, statement: MethodStatement) -> bool:
        params = statement.args.values()
        possible_replacements = len(params)
        if not statement.accessible_object().is_static():
            possible_replacements += 1

        # Check if callee or params should be replaced
        if possible_replacements == randomness.next_int(1, possible_replacements + 1):
            types = self._chromosome.test_case.get_objects(statement.callee.type, self._position)
            types.remove(statement.callee)
            if len(types) == 0:
                self._logger.debug(
                    "No other possible calls found for callee %r", statement.callee.type
                )
                return False
            statement.callee = randomness.choice(types)
            return True
        return self._replace_parameter(statement)


class FieldStatementLocalSearch(StatementLocalSearch, ABC):
    def search(self) -> None:  # noqa: D102
        assert self._factory is not None
        last_execution_result = self._chromosome.get_last_execution_result()
        old_chromosome = TestCaseChromosome(None, None, self._chromosome)

        changed = True
        mutations = 0
        while (
            changed
            and mutations < config.LocalSearchConfiguration.random_parametrized_statement_call_count
        ):
            changed = self._factory.change_random_field_call(
                self._chromosome.test_case, self._position
            )
            if changed:
                if not self._objective.has_improved(self._chromosome):
                    changed = False
                    self._chromosome = old_chromosome
                    self._chromosome.set_last_execution_result(last_execution_result)
                else:
                    old_chromosome = TestCaseChromosome(None, None, self._chromosome)
                    last_execution_result = self._chromosome.get_last_execution_result()
            mutations += 1


class BytesLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for bytes"""

    def search(self) -> None:  # noqa: D102
        if self._apply_random_mutations():
            self._logger.debug("Removing values from bytes")
            self.remove_values()
            self._logger.debug("Replacing values from bytes")
            self.replace_values()
            self._logger.debug("Adding values to bytes")
            self.add_values()

    def _backup(self, statement: PrimitiveStatement):
        self._last_execution_result = self._chromosome.get_last_execution_result()
        self._old_value = statement.value
        self._old_changed = self._chromosome.changed

    def _restore(self, statement: PrimitiveStatement):
        self._chromosome.set_last_execution_result(self._last_execution_result)
        self._chromosome.changed = self._old_changed
        statement.value = self._old_value

    def _apply_random_mutations(self) -> bool:
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        random_mutations_count = config.LocalSearchConfiguration.string_random_mutation_count

        while random_mutations_count > 0:
            self._backup(statement)
            statement.delta()
            changed = self._objective.has_changed(self._chromosome)
            if changed < 1:
                self._restore(statement)
            if changed != 0:
                self._logger.debug("Random mutations have an impact on the fitness")
                return True
            random_mutations_count -= 1
        self._logger.debug("Random mutations have no impact on the fitness, aborting local search")
        return False

    def add_values(self) -> None:
        """Tries to add a value at each position of the bytes. If the addition was
        successful, the best value for this position is evaluated.
        """
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)
        i = 0
        while i <= len(statement.value):
            statement.value = statement.value[:i] + bytes([97]) + statement.value[i:]
            self._logger.debug(
                "Starting to add value at position %d from bytes %r", i, statement.value
            )
            if self._objective.has_improved(self._chromosome):
                self._backup(statement)
                finished = False

                while not finished:
                    finished = True
                    if self._iterate_bytes(statement, i, 1):
                        finished = False
                    if self._iterate_bytes(statement, i, -1):
                        finished = False

                self._logger.debug(
                    "Successfully added value at position %d to bytes %r",
                    i,
                    statement.value,
                )
            else:
                self._restore(statement)
                self._logger.debug(
                    "Inserting a value at position %d of bytes %r has no positive impact.",
                    i,
                    statement.value,
                )
            i += 1

    def replace_values(self) -> None:
        """Replaces each value with every other possible value until successful
        replacement.
        """  # noqa: D205
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )

        old_changed = self._chromosome.changed
        improved = False
        self._backup(statement)
        for i in range(len(statement.value) - 1, -1, -1):
            finished = False

            while not finished:
                finished = True
                old_value = statement.value
                if self._iterate_bytes(statement, i, 1):
                    finished = False
                    improved = True
                if self._iterate_bytes(statement, i, -1):
                    finished = False
                    improved = True
                if not finished:
                    self._logger.debug(
                        "Successfully replaced value %d from bytes %r to %r",
                        i,
                        old_value,
                        statement.value,
                    )
        if not improved:
            self._chromosome.changed = old_changed

    def remove_values(self) -> None:
        """Removes each value from bytes.

        If an improvement to the bytes is found, the value is removed., otherwise the old
        bytes is restored.
        """
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)

        for i in range(len(statement.value) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                break
            self._logger.debug("Removing value %d from byte %r", i, statement.value)
            statement.value = statement.value[:i] + statement.value[i + 1 :]
            if self._objective.has_improved(self._chromosome):
                self._logger.debug("Removing the value has improved the fitness.")
                self._backup(statement)
            else:
                self._restore(statement)

    def _iterate_bytes(
        self,
        statement: BytesPrimitiveStatement,
        pos: int,
        delta: int,
    ) -> bool:
        self._backup(statement)
        if statement.value[pos] + delta not in range(256):
            return False
        statement.value = (
            statement.value[:pos]
            + bytes([statement.value[pos] + delta])
            + statement.value[pos + 1 :]
        )

        improved = False
        while (
            self._objective.has_improved(self._chromosome)
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            improved = True
            self._chromosome.changed = True
            self._backup(statement)
            delta *= config.LocalSearchConfiguration.int_delta_increasing_factor
            if statement.value[pos] + delta not in range(256):
                return improved
            statement.value = (
                statement.value[:pos]
                + bytes([statement.value[pos] + delta])
                + statement.value[pos + 1 :]
            )
        self._restore(statement)
        return improved
