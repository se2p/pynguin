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
"""Implements a random test generation algorithm similar to Randoop."""
import datetime
import inspect
import logging
import random
import string
from typing import List, Type, Tuple, Set, Callable, Any, Dict

from pynguin.configuration import Configuration
from pynguin.generation.algorithms.algorithm import GenerationAlgorithm
from pynguin.generation.executor import Executor
from pynguin.generation.symboltable import SymbolTable
from pynguin.generation.valuegeneration import init_value
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.proxy import MagicProxy
from pynguin.utils.recorder import CoverageRecorder
from pynguin.utils.statements import (
    Sequence,
    Name,
    Expression,
    Assignment,
    Attribute,
    Call,
    FunctionSignature,
)
from pynguin.utils.utils import get_members_from_module

LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class RandomGenerationAlgorithm(GenerationAlgorithm):
    """Implements a random test generation algorithm similar to Randoop."""

    def __init__(
        self,
        recorder: CoverageRecorder,
        executor: Executor,
        configuration: Configuration,
    ) -> None:
        super().__init__(configuration)
        self._recorder = recorder
        self._executor = executor
        self._configuration = configuration
        self._symbol_table: SymbolTable = None  # type: ignore

    # pylint: disable=too-many-locals
    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[Sequence], List[Sequence]]:
        """Generates sequences for a given module until the time limit is reached.

        :param time_limit: The maximum amount of time that shall be consumed
        :param modules: The list of types that are available
        :return: A tuple of lists of sequences
        """
        LOGGER.info("Start generating sequences")

        self._symbol_table = SymbolTable(
            None,
            self._get_default_domains(modules, False),
            self._configuration.use_type_hints,
        )

        error_sequences: List[Sequence] = []
        non_error_sequences: List[Sequence] = []
        archive: List[Sequence] = []
        start_time = datetime.datetime.now()
        execution_counter: int = 0

        objects_under_test = self._find_objects_under_test(modules)

        while (datetime.datetime.now() - start_time).total_seconds() < time_limit:
            try:
                methods = self._choose_random_public_method(objects_under_test)

                sequences = self._choose_random_sequences(non_error_sequences)
                values = self._choose_random_values(methods, sequences)
                new_sequence = self._extend(methods, sequences, values)

                if (
                    new_sequence in non_error_sequences
                    or new_sequence in error_sequences
                ):
                    continue

                output_values, _, violations, _ = self._executor.execute(new_sequence)
                execution_counter += 1

                self._record_exception_statistic(violations, methods)
                if self._has_type_violations(violations):
                    if self._configuration.record_types:
                        # TODO(sl) implement type constraint recording
                        LOGGER.debug(
                            "Reached: TODO(sl) Implement type constraint recording"
                        )
                elif violations:
                    if new_sequence not in error_sequences:
                        error_sequences.append(new_sequence)
                        self._mark_original_sequences(sequences)
                else:
                    if self._configuration.record_types:
                        self._record_return_values(methods, new_sequence, output_values)

                    if new_sequence not in error_sequences:
                        new_sequence.output_values = output_values
                        non_error_sequences.append(new_sequence)
                        self._recorder.record_data(
                            data=self._executor.accumulated_coverage
                        )

                purged, sequences = self._purge_sequences(non_error_sequences)
                non_error_sequences = sequences
                archive = archive + purged
            except GenerationException as exception:
                LOGGER.debug("Generate sequences: %s", exception.__repr__())

        LOGGER.info("Finished generating sequences")

        error_sequences = error_sequences + archive
        return non_error_sequences, error_sequences

    @staticmethod
    def _get_default_domains(
        modules: List[Type], primitive_only: bool = True
    ) -> Set[Type]:
        if primitive_only:
            return SymbolTable.get_default_domain()

        classes = []
        for module in modules:
            for _, member in inspect.getmembers(module):
                if inspect.isclass(member):
                    classes.append(member)
        domains = SymbolTable.get_default_domain().union(classes)
        return domains

    @staticmethod
    def _find_objects_under_test(modules: List[Type]) -> List[Type]:
        objects_under_test = modules.copy()
        # pylint: disable=cell-var-from-loop
        for module in modules:
            members = get_members_from_module(module)
            objects_under_test = objects_under_test + [x[1] for x in members]
        return objects_under_test

    @staticmethod
    def _choose_random_public_method(objects_under_test: List[Type]) -> Callable:
        def inspect_member(member):
            try:
                return (
                    inspect.isclass(member)
                    or inspect.ismethod(member)
                    or inspect.isfunction(member)
                )
            except Exception as exception:
                raise GenerationException("Test member: " + exception.__repr__())

        object_under_test = random.choice(objects_under_test)
        members = inspect.getmembers(
            # pylint: disable=unnecessary-lambda
            object_under_test,
            lambda member: inspect_member(member),
        )

        public_members = [
            m[1]
            for m in members
            if not m[0][0] == "_" and not m[1].__name__ == "_recording_isinstance"
        ]

        if not public_members:
            raise GenerationException(
                object_under_test.__name__ + " has no public callables."
            )

        method = random.choice(public_members)
        return method

    def _choose_random_sequences(self, sequences: List[Sequence]) -> List[Sequence]:
        if self._configuration.max_sequence_length == 0:
            selectables = sequences
        else:
            selectables = [
                sequence
                for sequence in sequences
                if len(sequence) < self._configuration.max_sequence_length
            ]
        if self._configuration.max_sequences_combined == 0:
            upper_bound = len(selectables)
        else:
            upper_bound = min(
                len(selectables), self._configuration.max_sequences_combined
            )
        new_sequences = random.sample(selectables, random.randint(0, upper_bound))
        return new_sequences

    def _choose_random_values(
        self, method: Callable, sequences: List[Sequence]
    ) -> Dict[str, Any]:
        def sort_arguments():
            signature = inspect.signature(method)
            parameters = [p.name for _, p in signature.parameters.items()]
            for parameter in parameters.copy():
                if parameter == "self":
                    parameters.remove(parameter)
            sorted_args = {el: unsorted_args[el] for el in parameters}
            return sorted_args

        if method not in self._symbol_table:
            self._symbol_table.add_callable(method)

        all_solutions = [self._symbol_table[method]]

        if not all_solutions:
            raise GenerationException(
                "Could not find any candidate types for " + method.__name__
            )

        solution = random.choice(all_solutions)

        if isinstance(solution, FunctionSignature) and solution.inputs == []:
            return {}
        if isinstance(solution, FunctionSignature):
            unsorted_args = {}
            for item in solution.inputs:
                type_ = random.choice(list(SymbolTable.get_default_domain()))
                initialised_value = init_value(type_, sequences)
                unsorted_args[item] = MagicProxy(initialised_value)
            return sort_arguments()
        LOGGER.debug("Unhandled value creation instance.")
        return {}

    # pylint: disable=too-many-locals
    def _extend(  # noqa: C901
        self, method: Callable, sequences: List[Sequence], values: Dict[str, Any]
    ) -> Sequence:
        def contains_explicit_return(func: Callable) -> bool:
            try:
                lines, _ = inspect.getsourcelines(func)
                return any("return" in line for line in lines)
            except TypeError as error:
                raise GenerationException(error)

        def find_callee_for_method(func: Callable, new_sequence: Sequence) -> Name:
            overwritten: List[Expression] = []
            function_signature = self._symbol_table[func]
            for statement in reversed(new_sequence):
                if isinstance(statement, Assignment) and isinstance(
                    statement.rhs, Attribute
                ):
                    for return_tuple in function_signature.return_value:
                        # pylint: disable=unused-variable
                        for value in return_tuple:
                            # TODO(sl) what shall we do with this?
                            LOGGER.debug(
                                "Reached: TODO(sl) what shall we do with this? %s",
                                repr(value),
                            )
                            raise GenerationException("Not implemented handling")
                elif isinstance(statement, Assignment) and isinstance(
                    statement.rhs, Call
                ):
                    call_expression = statement.rhs
                    if isinstance(call_expression.function, Name):
                        if (
                            function_signature.class_name
                            in call_expression.function.identifier
                            and statement.lhs not in overwritten
                        ):
                            assert isinstance(statement.lhs, Name)
                            return statement.lhs
                    elif isinstance(call_expression.function, Attribute):
                        if (
                            function_signature.class_name
                            in call_expression.function.owner.identifier
                            and statement.lhs not in overwritten
                        ):
                            assert isinstance(statement.lhs, Name)
                            return statement.lhs
                    else:
                        raise GenerationException("Not implemented handling")
                    overwritten.append(statement.lhs)
            return Name(identifier="")

        new_sequence = Sequence()
        for sequence in sequences:
            new_sequence = new_sequence + sequence

        is_constructor = False
        attribute: Expression = None  # type: ignore
        if not self._symbol_table[method].class_name:
            signature = self._symbol_table[method]
            if signature.module_name:
                attribute = Name(signature.module_name + "." + signature.method_name)
            else:
                attribute = Name(signature.method_name)
            is_constructor = True
        else:
            callee = find_callee_for_method(method, new_sequence)
            if self._symbol_table[method].class_name:
                attribute = Attribute(callee, method.__name__)
            else:
                attribute = Name(method.__name__)

        call = Call(attribute, list(values.values()))
        if is_constructor or contains_explicit_return(method):
            letter = random.choice(string.ascii_lowercase)
            identifier = Name(letter + str(len(new_sequence) + 1))
            assignment = Assignment(identifier, call)
            new_sequence.append(assignment)
        else:
            new_sequence.append(call)

        return new_sequence

    @staticmethod
    def _record_exception_statistic(
        exceptions: List[Exception], method: Callable
    ) -> None:
        pass

    @staticmethod
    def _has_type_violations(exceptions: List[Exception]) -> bool:
        for exception in exceptions:
            if isinstance(exception, (TypeError, AttributeError)):
                return True
        return False

    @staticmethod
    def _mark_original_sequences(sequences: List[Sequence]) -> None:
        for sequence in sequences:
            sequence.counter += 1

    def _record_return_values(
        self, method: Callable, sequence: Sequence, output_values: Dict[str, Any]
    ) -> None:
        pass

    def _purge_sequences(
        self, sequences: List[Sequence]
    ) -> Tuple[List[Sequence], List[Sequence]]:
        if self._configuration.counter_threshold == 0:
            return [], sequences

        purged: List[Sequence] = []
        remaining: List[Sequence] = []
        for sequence in sequences:
            if sequence.counter > self._configuration.counter_threshold:
                purged.append(sequence)
            else:
                remaining.append(sequence)
        return purged, remaining
