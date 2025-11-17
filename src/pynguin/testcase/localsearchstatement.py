#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies.

Some of these strategies for primitives, which also exist in Java, and for complex objects are
similar to the local search strategies from Evosuite.
"""

from __future__ import annotations

import abc
import enum
import logging
import math
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.analyses.typesystem import AnyType, ProperType, is_primitive_type
from pynguin.testcase.localsearchobjective import LocalSearchImprovement as LS_Imp
from pynguin.testcase.statement import (
    BooleanPrimitiveStatement,
    BytesPrimitiveStatement,
    ClassPrimitiveStatement,
    CollectionStatement,
    ComplexPrimitiveStatement,
    ConstructorStatement,
    DictStatement,
    EnumPrimitiveStatement,
    FieldStatement,
    FloatPrimitiveStatement,
    FunctionStatement,
    IntPrimitiveStatement,
    MethodStatement,
    NonDictCollection,
    NoneStatement,
    ParametrizedStatement,
    PrimitiveStatement,
    SetStatement,
    StringPrimitiveStatement,
    VariableCreatingStatement,
    create_statement,
)
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.testcase.execution import ExecutionResult
    from pynguin.testcase.localsearchobjective import LocalSearchObjective
    from pynguin.testcase.localsearchtimer import LocalSearchTimer
    from pynguin.testcase.testfactory import TestFactory


class StatementLocalSearch(abc.ABC):
    """An abstract local search strategy for statements."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        chromosome: TestCaseChromosome,
        position: int,
        objective: LocalSearchObjective,
        factory: TestFactory,
        timer: LocalSearchTimer,
    ):
        """Initializes the local search strategy for a specific statement.

        Args:
            chromosome (TestCaseChromosome): The test case chromosome containing the statement.
            position (int): The position of the statement in the test case.
            objective (LocalSearchObjective): The objective to check for improvements.
            factory (TestFactory): The factory to create new statements.
            timer (LocalSearchTimer): The timer which limits the local search.
        """
        self._chromosome = chromosome
        self._objective = objective
        self._position = position
        self._factory = factory
        self._timer = timer

    @abstractmethod
    def search(self) -> bool:
        """Applies local search to a specific statement of the chromosome.

        Returns:
            True, if the local search was successful and improved the fitness.
        """


class PrimitiveLocalSearch(StatementLocalSearch, ABC):
    """Abstract local search strategy for primitive statements."""

    def _backup(self, statement: PrimitiveStatement):
        self._last_execution_result = cast(
            "ExecutionResult", self._chromosome.get_last_execution_result()
        )
        self._old_value = statement.value
        self._old_changed = self._chromosome.changed

    def _restore(self, statement: PrimitiveStatement):
        self._chromosome.set_last_execution_result(self._last_execution_result)
        self._chromosome.changed = self._old_changed
        statement.value = self._old_value


class BooleanLocalSearch(PrimitiveLocalSearch, ABC):
    """A local search strategy for booleans."""

    def search(self) -> bool:  # noqa: D102
        statement = cast(
            "BooleanPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)
        statement.value = not statement.value
        if not self._objective.has_improved(self._chromosome):
            self._restore(statement)
            return False
        return True


class NumericalLocalSearch(PrimitiveLocalSearch, ABC):
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
        self._backup(statement)
        statement.value += delta
        while self._objective.has_improved(self._chromosome) and not self._timer.limit_reached():
            self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
            self._backup(statement)
            improved = True
            delta *= increasing_factor
            statement.value += delta
        self._restore(statement)
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

        while not done and not self._timer.limit_reached():
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
    ) -> bool:
        statement = cast(
            "IntPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        old_value = statement.value
        increasing_factor = config.configuration.local_search.ls_int_delta_increasing_factor
        if self.iterate_directions(statement, 1, increasing_factor):
            self._logger.debug(
                "Successfully increased value of %s to %s ", old_value, statement.value
            )
            return True
        self._logger.debug("Local search couldn't find a better int value for %s", statement.value)
        return False


class EnumLocalSearch(PrimitiveLocalSearch, ABC):
    """A local search strategy for enumerations."""

    def search(  # noqa: D102
        self,
    ) -> bool:
        statement = cast(
            "EnumPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        initial_value = statement.value
        self._backup(statement)
        for value in range(len(statement.accessible_object().names)):
            if self._timer.limit_reached():
                return False
            if value != initial_value:
                if not self._objective.has_improved(self._chromosome):
                    self._restore(statement)
                else:
                    self._logger.debug("Local search successfully found better enum value")
                    return True
        return False


class ClassLocalSearch(PrimitiveLocalSearch, ABC):
    """A local search strategy for classes."""

    def search(  # noqa: D102
        self,
    ) -> bool:
        statement = cast(
            "ClassPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        initial_value = statement.value
        self._backup(statement)
        for value in range(len(statement.test_case.test_cluster.type_system.get_all_types())):
            if self._timer.limit_reached():
                return False
            if value != initial_value:
                if not self._objective.has_improved(self._chromosome):
                    self._restore(statement)
                else:
                    self._logger.debug("Local search successfully found better class value")
                    return True
        return False


class FloatLocalSearch(NumericalLocalSearch, ABC):
    """A local search strategy for floats."""

    # TODO: Maybe shift into integer and apply local search for integers, shift back and evaluate?
    def search(  # noqa: D102
        self,
    ) -> bool:
        statement = cast(
            "FloatPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        improved = False
        original_value = statement.value
        increasing_factor = config.configuration.local_search.ls_int_delta_increasing_factor
        if self.iterate_directions(statement, 1, increasing_factor):
            improved = True

        precision = 1
        while (
            precision <= sys.float_info.dig
            and not self._timer.limit_reached()
            and statement.value is not None
        ):
            self._backup(statement)
            statement.value = round(statement.value, precision)
            if self._objective.has_changed(self._chromosome) == LS_Imp.DETERIORATION:
                self._restore(statement)
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
        return improved


class ComplexLocalSearch(PrimitiveLocalSearch, ABC):
    """A local search strategy for complex numbers."""

    def search(self) -> bool:  # noqa: D102
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
        return improved

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
        while precision <= sys.float_info.dig and not self._timer.limit_reached():
            self._logger.debug("Starting local search with precision %d", precision)
            if self.iterate_directions(statement, 10.0 ** (-precision), imaginary):
                improved = True
                self._backup(statement)
                if statement.value is None:
                    return improved
                if imaginary:
                    statement.value = complex(
                        statement.value.real, round(statement.value.imag, precision)
                    )
                else:
                    statement.value = complex(
                        round(statement.value.real, precision), statement.value.imag
                    )
                if self._objective.has_changed(self._chromosome) == LS_Imp.DETERIORATION:
                    self._restore(statement)
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
        while not done and not self._timer.limit_reached():
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
        factor = float(config.configuration.local_search.ls_int_delta_increasing_factor)
        if statement.value is None:
            return False

        improved = False
        self._backup(statement)
        if imaginary:
            statement.value = complex(statement.value.real, statement.value.imag + delta)
        else:
            statement.value = complex(statement.value.real + delta, statement.value.imag)
        while (
            self._objective.has_improved(self._chromosome)
            and not self._timer.limit_reached()
            and {statement.value.real, statement.value.imag}.isdisjoint((-math.inf, math.inf))
        ):
            delta *= factor
            self._logger.debug("Incrementing value of %s with delta %s ", statement.value, delta)
            self._backup(statement)
            improved = True
            if imaginary:
                statement.value = complex(statement.value.real, statement.value.imag + delta)
            else:
                statement.value = complex(statement.value.real + delta, statement.value.imag)
        self._restore(statement)
        return improved


class StringLocalSearch(PrimitiveLocalSearch, ABC):
    """A local search strategy for strings."""

    def search(self) -> bool:  # noqa: D102
        improved = False
        if self.apply_random_mutations():
            self._logger.debug("Removing characters from string")
            if self.remove_chars():
                improved = True
            self._logger.debug("Replacing characters from string")
            if self.replace_chars():
                improved = True
            self._logger.debug("Adding characters to the string")
            if self.add_chars():
                improved = True
        return improved

    def apply_random_mutations(self) -> bool:
        """Applies a number of random mutations to the string.

        Returns:
            Gives back true if the mutations change the fitness in any way.
        """
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        random_mutations_count = config.configuration.local_search.ls_string_random_mutation_count
        self._backup(statement)
        while random_mutations_count > 0:
            statement.randomize_value()

            improvement = self._objective.has_changed(self._chromosome)
            if improvement in {LS_Imp.DETERIORATION, LS_Imp.NONE}:
                self._restore(statement)

            if improvement in {LS_Imp.DETERIORATION, LS_Imp.IMPROVEMENT}:
                self._logger.debug(
                    "The random mutations have changed the fitness of %r, applying local search",
                    self._chromosome.test_case.statements[self._position],
                )
                stat.add_to_runtime_variable(
                    RuntimeVariable.LocalSearchSuccessfulExploratoryMoves, 1
                )
                return True
            random_mutations_count -= 1
        stat.add_to_runtime_variable(RuntimeVariable.LocalSearchUnsuccessfulExploratoryMoves, 1)
        self._logger.debug(
            "The random mutations have no impact on the fitness, aborting local search"
        )
        return False

    def remove_chars(self) -> bool:
        """Removes each character from the string.

        If an improvement to the string is found, the character is removed., otherwise the old
        string is restored.
        """
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        assert statement.value is not None
        self._backup(statement)
        improved = False
        for i in range(len(statement.value) - 1, -1, -1):
            if self._timer.limit_reached():
                return improved
            self._logger.debug("Removing character %d from string %r", i, statement.value)
            statement.value = statement.value[:i] + statement.value[i + 1 :]
            if self._objective.has_improved(self._chromosome):
                self._logger.debug("Removing the character has improved the fitness.")
                self._backup(statement)
                improved = True
            else:
                self._restore(statement)
        return improved

    def replace_chars(self) -> bool:
        """Replaces each character with every other possible character until successful
        replacement.
        """  # noqa: D205
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        if statement.value is None:
            return False
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
        return improved

    def add_chars(self) -> bool:
        """Tries to add a character at each position of the string. If the addition was
        successful, the best char for this position is evaluated.
        """  # noqa: D205
        statement = cast(
            "StringPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)
        i = 0
        improved = False
        while (
            statement.value is not None
            and i <= len(statement.value)
            and not self._timer.limit_reached()
        ):
            statement.value = statement.value[:i] + chr(97) + statement.value[i:]
            # TODO: Which is best char to start with (maybe the one in the middle?)
            self._logger.debug(
                "Starting to add character at position %d from string %r", i, statement.value
            )
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
                finished = False

                while not finished and not self._timer.limit_reached():
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
        return improved

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
            statement.value is None
            or ord(statement.value[char_position]) + delta > sys.maxunicode
            or ord(statement.value[char_position]) + delta < 0
        ):
            return False
        self._replace_single_char(statement, char_position, delta)
        improved = False
        while self._objective.has_improved(self._chromosome):
            improved = True
            self._chromosome.changed = True
            self._backup(statement)
            if self._timer.limit_reached() or statement.value is None:
                break
            delta *= config.configuration.local_search.ls_int_delta_increasing_factor
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
        if statement.value is None:
            return
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


class ParametrizedStatementOperations(enum.Enum):
    """The different operations for the parametrized statement local search."""

    REPLACE = 0
    RANDOM_CALL = 1
    PARAMETER = 2


class ParametrizedStatementLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for parametrized statements."""

    def search(self) -> bool:  # noqa: D102
        assert self._factory is not None
        statement = self._chromosome.test_case.statements[self._position]
        mutations = 0
        if not (isinstance(statement, ParametrizedStatement | NoneStatement)):
            self._logger.debug(
                "Error! The statement at position %d has to be a ParametrizedStatement or "
                "NoneStatement",
                self._position,
            )
            return False

        last_execution_result = self._chromosome.get_last_execution_result()
        old_test_case = self._chromosome.test_case.clone()

        total_iterations = 0
        improved = False
        while (
            not self._timer.limit_reached()
            and mutations
            < config.configuration.local_search.ls_random_parametrized_statement_call_count
        ):
            total_iterations += 1
            operations: list[ParametrizedStatementOperations] = [
                ParametrizedStatementOperations.REPLACE
            ]
            if isinstance(statement, ParametrizedStatement):
                operations.append(ParametrizedStatementOperations.RANDOM_CALL)
                if len(statement.args) > 0:
                    operations.append(ParametrizedStatementOperations.PARAMETER)
            old_size = len(self._chromosome.test_case.statements)
            random = randomness.choice(operations)
            if random == ParametrizedStatementOperations.RANDOM_CALL:
                changed = self.random_call()
            elif random == ParametrizedStatementOperations.PARAMETER:
                changed = self.random_parameter()
            else:
                changed = self.replace()

            if changed and self._objective.has_improved(self._chromosome):
                improved = True
                last_execution_result = self._chromosome.get_last_execution_result()
                old_test_case = self._chromosome.test_case.clone()
                mutations = 0
                self._position += len(self._chromosome.test_case.statements) - old_size
            else:
                self._chromosome.test_case = old_test_case.clone()
                self._chromosome.set_last_execution_result(
                    last_execution_result
                ) if last_execution_result is not None else None
                statement = self._chromosome.test_case.statements[self._position]
                mutations += 1
        if (
            total_iterations
            == config.configuration.local_search.ls_random_parametrized_statement_call_count
        ):
            stat.add_to_runtime_variable(RuntimeVariable.LocalSearchUnsuccessfulExploratoryMoves, 1)
        else:
            stat.add_to_runtime_variable(RuntimeVariable.LocalSearchSuccessfulExploratoryMoves, 1)
        return improved

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
            return self._replace_parameter(statement)  # type: ignore[arg-type]
        if isinstance(statement, MethodStatement):
            return self._replace_params_or_callee(statement)
        return False

    def _replace_parameter(self, statement: ParametrizedStatement) -> bool:
        self._logger.debug("Replacing parameter of %s", statement)
        params = statement.args.values()
        if len(params) == 0:
            return False
        parameter = randomness.choice(list(params))
        types = self._chromosome.test_case.get_objects(parameter.type, self._position)
        if randomness.next_float() < self._get_reuse_probability(parameter.type) or len(types) == 0:
            self._logger.debug("Creating new fitting reference for param %r", parameter.type)
            new_parameter = self._factory.create_fitting_reference(
                self._chromosome.test_case, parameter.type, position=self._position
            )
            if new_parameter is not None:
                statement.replace(parameter, new_parameter)
                return True
            return False
        self._logger.debug("Replacing param %r with another possible param", parameter.type)
        new_parameter = randomness.choice(types)
        statement.replace(parameter, new_parameter)
        return True

    def _replace_params_or_callee(self, statement: MethodStatement) -> bool:
        self._logger.debug("Replacing parameter or callee of %s", statement)
        params = statement.args.values()
        possible_replacements = len(params)
        if not statement.accessible_object().is_static():
            possible_replacements += 1

        # Check if callee or params should be replaced
        if possible_replacements == randomness.next_int(1, possible_replacements + 1):
            types = self._chromosome.test_case.get_objects(statement.callee.type, self._position)
            if (
                randomness.next_float() < self._get_reuse_probability(statement.callee.type)
                or len(types) == 0
            ):
                self._logger.debug(
                    "Creating new fitting reference for callee %r", statement.callee.type
                )
                new_type = self._factory.create_fitting_reference(
                    self._chromosome.test_case, statement.ret_val.type, position=self._position
                )
                if new_type is not None:
                    statement.callee = new_type
                    return True
                return False
            self._logger.debug("Replacing callee %r with another possible call", statement.callee)
            statement.callee = randomness.choice(types)
            return True
        return self._replace_parameter(statement)

    @staticmethod
    def _get_reuse_probability(input_type: ProperType) -> float:
        return (
            config.configuration.test_creation.primitive_reuse_probability
            if input_type.accept(is_primitive_type)
            else config.configuration.test_creation.object_reuse_probability
        )


class FieldStatementLocalSearch(StatementLocalSearch, ABC):
    """A local search strategy for field statements."""

    def search(self) -> bool:  # noqa: D102
        assert self._factory is not None
        last_execution_result = cast(
            "ExecutionResult", self._chromosome.get_last_execution_result()
        )
        old_test_case = self._chromosome.test_case.clone()

        changed = True
        improved = False
        mutations = 0
        while (
            changed
            and mutations
            < config.configuration.local_search.ls_random_parametrized_statement_call_count
        ):
            changed = self._factory.change_random_field_call(
                self._chromosome.test_case, self._position
            )
            if changed:
                if not self._objective.has_improved(self._chromosome):
                    improved = True
                    changed = False
                    self._chromosome.test_case = old_test_case
                    self._chromosome.set_last_execution_result(last_execution_result)
                else:
                    old_test_case = self._chromosome.test_case.clone()
                    last_execution_result = cast(
                        "ExecutionResult", self._chromosome.get_last_execution_result()
                    )
            mutations += 1
        return improved


class BytesLocalSearch(PrimitiveLocalSearch, ABC):
    """A local search strategy for bytes."""

    def search(self) -> bool:  # noqa: D102
        improved = False
        if self._apply_random_mutations():
            self._logger.debug("Removing values from bytes")
            if self.remove_values():
                improved = True
            self._logger.debug("Replacing values from bytes")
            if self.replace_values():
                improved = True
            self._logger.debug("Adding values to bytes")
            if self.add_values():
                improved = True
        return improved

    def _apply_random_mutations(self) -> bool:
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        random_mutations_count = config.configuration.local_search.ls_string_random_mutation_count

        while random_mutations_count > 0:
            self._backup(statement)
            statement.delta()
            changed = self._objective.has_changed(self._chromosome)
            if changed in {LS_Imp.DETERIORATION, LS_Imp.NONE}:
                self._restore(statement)
            if changed in {LS_Imp.DETERIORATION, LS_Imp.IMPROVEMENT}:
                self._logger.debug("Random mutations have an impact on the fitness")
                stat.add_to_runtime_variable(
                    RuntimeVariable.LocalSearchSuccessfulExploratoryMoves, 1
                )
                return True
            random_mutations_count -= 1
        self._logger.debug("Random mutations have no impact on the fitness, aborting local search")
        stat.add_to_runtime_variable(RuntimeVariable.LocalSearchUnsuccessfulExploratoryMoves, 1)
        return False

    def add_values(self) -> bool:
        """Tries to add a value at each position of the bytes. If the addition was
        successful, the best value for this position is evaluated.
        """  # noqa : D205
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)
        i = 0
        improved = False
        if statement.value is None:
            return False
        while i <= len(statement.value) and not self._timer.limit_reached():
            statement.value = statement.value[:i] + bytes([97]) + statement.value[i:]
            self._logger.debug(
                "Starting to add value at position %d from bytes %r", i, statement.value
            )
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
                finished = False

                while not finished and not self._timer.limit_reached():
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
        return improved

    def replace_values(self) -> bool:
        """Replaces each value with every other possible value until successful
        replacement.
        """  # noqa: D205
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )

        old_changed = self._chromosome.changed
        improved = False
        self._backup(statement)
        if statement.value is None:
            return False
        for i in range(len(statement.value) - 1, -1, -1):
            finished = False

            while not finished and not self._timer.limit_reached():
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
        return improved

    def remove_values(self) -> bool:
        """Removes each value from bytes.

        If an improvement to the bytes is found, the value is removed., otherwise the old
        bytes is restored.
        """
        statement = cast(
            "BytesPrimitiveStatement", self._chromosome.test_case.statements[self._position]
        )
        self._backup(statement)
        improved = False
        if statement.value is None:
            return improved
        for i in range(len(statement.value) - 1, -1, -1):
            if self._timer.limit_reached():
                break
            self._logger.debug("Removing value %d from byte %r", i, statement.value)
            statement.value = statement.value[:i] + statement.value[i + 1 :]
            if self._objective.has_improved(self._chromosome):
                self._logger.debug("Removing the value has improved the fitness.")
                self._backup(statement)
                improved = True
            else:
                self._restore(statement)
        return improved

    def _iterate_bytes(
        self,
        statement: BytesPrimitiveStatement,
        pos: int,
        delta: int,
    ) -> bool:
        self._backup(statement)
        if statement.value is None or statement.value[pos] + delta not in range(256):
            return False
        statement.value = (
            statement.value[:pos]
            + bytes([statement.value[pos] + delta])
            + statement.value[pos + 1 :]
        )

        improved = False
        while self._objective.has_improved(self._chromosome) and not self._timer.limit_reached():
            improved = True
            self._chromosome.changed = True
            self._backup(statement)
            delta *= config.configuration.local_search.ls_int_delta_increasing_factor
            if statement.value[pos] + delta not in range(256):
                return improved
            statement.value = (
                statement.value[:pos]
                + bytes([statement.value[pos] + delta])
                + statement.value[pos + 1 :]
            )
        self._restore(statement)
        return improved


class CollectionLocalSearch(StatementLocalSearch, ABC):
    """Abstract base class for local search strategies for collection types."""

    def _backup(self, statement: CollectionStatement) -> None:
        self._old_elements = statement.elements.copy()
        self._last_execution_result = cast(
            "ExecutionResult", self._chromosome.get_last_execution_result()
        )

    def _restore(self, statement: CollectionStatement) -> None:
        statement.elements = self._old_elements.copy()
        self._chromosome.set_last_execution_result(self._last_execution_result)


class NonDictCollectionLocalSearch(CollectionLocalSearch, ABC):
    """Local search strategies for non-dict collection types."""

    def search(self) -> bool:  # noqa: D102
        improved = False
        statement = cast("NonDictCollection", self._chromosome.test_case.statements[self._position])
        if self.remove_entries(statement):
            self._logger.debug("Removing non-dict collection entries has improved fitness.")
            improved = True
        if self.replace_entries(statement):
            self._logger.debug("Replacing non-dict collection entries has improved fitness.")
            improved = True
        if self.add_entries(statement):
            self._logger.debug("Adding non-dict collection entries has improved fitness.")
            improved = True
        return improved

    def remove_entries(self, statement: NonDictCollection) -> bool:
        """Removes every entry of the collection and checks for improved fitness.

        Args:
            statement (NonDictCollection): The non-dict collection which should be modified.

        Returns:
            Gives back True if the mutations have improved the fitness.
        """
        self._backup(statement)
        improved = False
        self._logger.debug("Starting to remove entries from %s", statement)
        for i in range(len(statement.elements) - 1, -1, -1):
            if self._timer.limit_reached():
                return improved
            statement.elements = statement.elements[:i] + statement.elements[i + 1 :]
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
            else:
                self._restore(statement)
        return improved

    def replace_entries(self, statement: NonDictCollection) -> bool:
        """Replaces entries in the collection with other possible entries.

        Args:
            statement (NonDictCollection): The non-dict collection which should be modified.

        Returns:
            Gives back True if the mutations have improved the fitness.
        """
        self._backup(statement)
        improved = False
        self._logger.debug("Starting to replace entries from %s", statement)
        for i in range(len(statement.elements)):
            if self._timer.limit_reached():
                return improved
            objects = self._chromosome.test_case.get_objects(statement.ret_val.type, self._position)
            if isinstance(statement, SetStatement):
                objects = [obj for obj in objects if obj not in statement.elements]
            else:
                objects = [obj for obj in objects if obj != statement.elements[i]]
            size_change = 0
            if len(objects) == 0:
                old_size = self._chromosome.test_case.size()
                new_element = self._factory.create_fitting_reference(
                    self._chromosome.test_case, statement.ret_val.type, position=self._position
                )
                if new_element is None:
                    continue
                objects.append(new_element)
                size_change = self._chromosome.test_case.size() - old_size
            statement.elements[i] = randomness.choice(objects)
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
                self._position += size_change
            else:
                self._restore(statement)
                for _ in range(size_change):
                    self._chromosome.test_case.remove(self._position)
        return improved

    def add_entries(self, statement: NonDictCollection) -> bool:
        """Adds entries to the collection at every possible place.

        Args:
            statement (NonDictCollection): The non-dict collection which should be modified.

        Returns:
            Gives back True if the mutations have improved the fitness.
        """
        self._backup(statement)
        pos = 0
        improved = False
        self._logger.debug("Starting to add entries from %s", statement)
        while pos <= len(statement.elements) and not self._timer.limit_reached():
            objects = self._chromosome.test_case.get_objects(statement.ret_val.type, self._position)
            if isinstance(statement, SetStatement):
                objects = [obj for obj in objects if obj not in statement.elements]
            size_change = 0
            if len(objects) == 0:
                old_size = self._chromosome.test_case.size()
                new_element = self._factory.create_fitting_reference(
                    self._chromosome.test_case, statement.ret_val.type, position=self._position
                )
                if new_element is None:
                    pos += 1
                    continue
                objects.append(new_element)
                size_change = self._chromosome.test_case.size() - old_size
            if isinstance(statement, SetStatement):
                statement.elements.append(randomness.choice(objects))
            else:
                statement.elements.insert(pos, randomness.choice(objects))
            pos += 1
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
                self._position += size_change
            else:
                self._restore(statement)
                for _ in range(size_change):
                    self._chromosome.test_case.remove(self._position)
        return improved


class DictStatementLocalSearch(CollectionLocalSearch, ABC):
    """Local search strategies for dictionaries."""

    def search(self) -> bool:  # noqa: D102
        statement = cast("DictStatement", self._chromosome.test_case.statements[self._position])
        improved = False
        if self.remove_entries(statement):
            self._logger.debug("Removing dict collection entries has improved fitness.")
            improved = True
        if self.replace_entries(statement):
            self._logger.debug("Replacing dict collection entries has improved fitness.")
            improved = True
        if self.add_entries(statement):
            self._logger.debug("Adding dict collection entries has improved fitness.")
            improved = True
        return improved

    def remove_entries(self, statement: DictStatement) -> bool:
        """Removes every entry of the dictionary and checks for improved fitness.

        Args:
            statement (DictStatement): The dictionary which should be modified.

        Returns:
            Gives back True if the mutations have improved the fitness.
        """
        self._backup(statement)
        improved = False
        for key, value in statement.elements.copy():
            if self._timer.limit_reached():
                return improved
            statement.elements.remove((key, value))
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
            else:
                self._restore(statement)
        return improved

    def replace_entries(self, statement: DictStatement) -> bool:  # noqa: C901, PLR0915
        """Replaces entries in the dictionary with other possible entries.

        Args:
            statement (DictStatement): The dictionary which should be modified.

        Returns:
            Gives back True if the mutations have improved the fitness.
        """
        self._backup(statement)
        improved = False
        for i in range(len(statement.elements)):
            key, value = statement.elements[i]
            if self._timer.limit_reached():
                return improved
            values = self._chromosome.test_case.get_objects(value.type, self._position)
            keys_reference = self._chromosome.test_case.get_objects(key.type, self._position)
            key_elements = {k for (k, _) in statement.elements}
            keys = [k for k in keys_reference if k not in key_elements]
            # Replace key
            if len(keys) == 0:
                old_size = self._chromosome.test_case.size()
                new_key = self._factory.create_fitting_reference(
                    self._chromosome.test_case, key.type, position=self._position
                )
                if new_key is not None:
                    statement.elements[i] = (new_key, value)
                    size_change = self._chromosome.test_case.size() - old_size
                    if self._objective.has_improved(self._chromosome):
                        self._backup(statement)
                        self._position += size_change
                        improved = True
                    else:
                        self._restore(statement)
                        for _ in range(size_change):
                            self._chromosome.test_case.remove(self._position)
            else:
                for available_key in randomness.sample(
                    keys, min(len(keys), config.configuration.local_search.ls_dict_max_insertions)
                ):
                    statement.elements[i] = (available_key, value)
                    if self._objective.has_improved(self._chromosome):
                        improved = True
                        self._backup(statement)
                        break
                    self._restore(statement)

            key, value = statement.elements[i]
            # Replace value
            if len(values) == 0:
                old_size = self._chromosome.test_case.size()
                new_value = self._factory.create_fitting_reference(
                    self._chromosome.test_case, value.type, position=self._position
                )
                if new_value is not None:
                    statement.elements[i] = (key, new_value)
                    size_change = self._chromosome.test_case.size() - old_size
                    if self._objective.has_improved(self._chromosome):
                        improved = True
                        self._backup(statement)
                        self._position += size_change
                    else:
                        self._restore(statement)
                        for _ in range(size_change):
                            self._chromosome.test_case.remove(self._position)
            else:
                for available_value in randomness.sample(
                    values,
                    min(len(values), config.configuration.local_search.ls_dict_max_insertions),
                ):
                    statement.elements[i] = (key, available_value)
                    if not self._objective.has_improved(self._chromosome):
                        self._restore(statement)
                    else:
                        improved = True
                        self._backup(statement)
                    break
        return improved

    def add_entries(self, statement: DictStatement) -> bool:
        """Adds entries to the dictionary at every possible place.

        First, possible key errors will be added, then random keys and values will be added.

        Args:
            statement (DictStatement): The dictionary which should be modified.

        Returns:
            Gives back True if the mutations have improved the fitness.
        """
        self._backup(statement)
        has_key_errors = True
        improved = False
        while has_key_errors and not self._timer.limit_reached():
            has_key_errors = self._fix_possible_key_error(statement)
            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
            else:
                has_key_errors = False
                self._restore(statement)
        insertions = 0
        while (
            insertions < config.configuration.local_search.ls_dict_max_insertions
            and not self._timer.limit_reached()
        ):
            values = self._chromosome.test_case.get_objects(AnyType(), self._position)
            key_elements = {k for (k, _) in statement.elements}
            keys = [key for key in values if key not in key_elements]
            size_change = 0
            if len(keys) == 0:
                old_size = self._chromosome.test_case.size()
                new_key = self._factory.create_fitting_reference(
                    self._chromosome.test_case, statement.ret_val.type, position=self._position
                )
                if new_key is None:
                    continue
                values.append(new_key)
                statement.elements.append((new_key, randomness.choice(values)))
                size_change = self._chromosome.test_case.size() - old_size
            else:
                statement.elements.append((randomness.choice(keys), randomness.choice(values)))

            if self._objective.has_improved(self._chromosome):
                improved = True
                self._backup(statement)
                if len(keys) == 0:
                    self._position += size_change
            else:
                insertions += 1
                self._restore(statement)
                for _ in range(size_change):
                    self._chromosome.test_case.remove(self._position)
        return improved

    def _fix_possible_key_error(self, statement: DictStatement) -> bool:
        self._logger.debug("Checking for possible key errors")
        execution_result = self._chromosome.get_last_execution_result()
        if execution_result is None:
            return False
        key_errors: dict[int, BaseException] = {
            key: value
            for key, value in (execution_result.exceptions.items())
            if isinstance(value, KeyError)
        }
        if len(key_errors) > 0:
            first_error_index = min(key_errors.keys())
            first_error = key_errors[first_error_index]
            key = first_error.args[0]
            new_statement = create_statement(self._chromosome.test_case, key)
            if new_statement is None:
                return False
            self._factory.append_statement(
                self._chromosome.test_case, new_statement, position=self._position
            )
            values = self._chromosome.test_case.get_objects(AnyType(), self._position + 1)
            statement.elements.append((key, randomness.choice(values)))
            return True

        self._logger.debug("No key error available")
        return False


def choose_local_search_statement(  # noqa: C901
    chromosome: TestCaseChromosome,
    position: int,
    objective: LocalSearchObjective,
    factory: TestFactory,
    timer: LocalSearchTimer,
) -> StatementLocalSearch | None:
    """Chooses the local search strategy for the statement at the position.

    Args:
        chromosome (TestCaseChromosome): The test case which should be changed.
        position (int): The position of the statement in the test case.
        objective (LocalSearchObjective): The objective which checks if improvements are made.
        factory (TestFactory): The test factory which modifies the test case.
        timer (LocalSearchTimer): The timer which limits the local search.
    """
    statement = chromosome.test_case.statements[position]
    logger = logging.getLogger(__name__)
    logger.debug("Choose local search statement from statement")
    if isinstance(statement, NoneStatement):
        logger.debug("None local search statement found")
        return ParametrizedStatementLocalSearch(chromosome, position, objective, factory, timer)
    if isinstance(statement, EnumPrimitiveStatement):
        logger.debug("Statement is enum %s", statement.value_name)
        return EnumLocalSearch(chromosome, position, objective, factory, timer)
    if isinstance(statement, ClassPrimitiveStatement):
        logger.debug("Statement is class %s", statement.type_info.full_name)
        return ClassLocalSearch(chromosome, position, objective, factory, timer)
    if isinstance(statement, PrimitiveStatement):
        primitive_type = statement.value
        if isinstance(primitive_type, bool):
            logger.debug("Primitive type is bool %s", primitive_type)
            return BooleanLocalSearch(chromosome, position, objective, factory, timer)
        if isinstance(primitive_type, int):
            logger.debug("Primitive type is int %d", primitive_type)
            return IntegerLocalSearch(chromosome, position, objective, factory, timer)
        if isinstance(primitive_type, str):
            logger.debug("Primitive type is string %s", primitive_type)
            return StringLocalSearch(chromosome, position, objective, factory, timer)
        if isinstance(primitive_type, float):
            logger.debug("Primitive type is float %f", primitive_type)
            return FloatLocalSearch(chromosome, position, objective, factory, timer)
        if isinstance(primitive_type, complex):
            logger.debug("Primitive type is complex %s", primitive_type)
            return ComplexLocalSearch(chromosome, position, objective, factory, timer)
        if isinstance(primitive_type, bytes):
            logger.debug("Primitive type is bytes %s", primitive_type)
            return BytesLocalSearch(chromosome, position, objective, factory, timer)
        logger.debug("Unknown primitive type: %s", primitive_type)
    elif isinstance(statement, NonDictCollection):
        logger.debug("%s non-dict collection found", statement.__class__.__name__)
        return NonDictCollectionLocalSearch(chromosome, position, objective, factory, timer)
    elif isinstance(statement, DictStatement):
        logger.debug("%s dict statement found", statement.__class__.__name__)
        return DictStatementLocalSearch(chromosome, position, objective, factory, timer)
    elif (
        isinstance(statement, FunctionStatement)
        | isinstance(statement, ConstructorStatement)
        | isinstance(statement, MethodStatement)
    ):
        logger.debug("%s statement found", statement.__class__.__name__)
        return ParametrizedStatementLocalSearch(chromosome, position, objective, factory, timer)

    elif isinstance(statement, FieldStatement):
        logger.debug("%s statement found", statement.__class__.__name__)
        return FieldStatementLocalSearch(chromosome, position, objective, factory, timer)

    else:
        logger.debug("No local search statement found for %s", statement.__class__.__name__)
    return None
