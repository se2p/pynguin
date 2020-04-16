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
"""Provides capabilities to perform branch instrumentation."""
import logging
from types import CodeType
from typing import Set, Optional

from bytecode import Instr, Bytecode, Compare, Label

from pynguin.instrumentation.basis import TRACER_NAME
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.utils.iterator import ListIterator


# pylint:disable=too-few-public-methods
class BranchDistanceInstrumentation:
    """Instruments code objects to enable branch distance tracking."""

    # As of CPython 3.8, there are a few compare ops for which we can't really
    # compute a sensible branch distance. So for now, we just ignore those
    # comparisons and just track the result.
    # TODO(fk) update this to work with the bytecode for CPython 3.9, once it is released.
    _IGNORED_COMPARE_OPS: Set[Compare] = {Compare.EXC_MATCH}

    _logger = logging.getLogger(__name__)

    def __init__(self, tracer: ExecutionTracer) -> None:
        self._code_object_id: int = 0
        self._predicate_id: int = 0
        self._tracer = tracer

    def _instrument_inner_code_objects(self, code: CodeType) -> CodeType:
        new_consts = []
        for const in code.co_consts:
            if isinstance(const, CodeType):
                # The const is an inner code object
                new_consts.append(self._instrument_code_recursive(const))
            else:
                new_consts.append(const)
        return code.replace(co_consts=tuple(new_consts))

    def _instrument_code_recursive(
        self, code: CodeType, add_global_tracer: bool = False
    ) -> CodeType:
        """Instrument the given CodeType recursively."""
        # TODO(fk) Change instrumentation to make use of a visitor pattern, similar to ASM in Java.
        # The instrumentation loop is already getting really big...

        # Nested code objects are found within the consts of the CodeType.
        self._logger.debug("Instrumenting Code Object for %s", self._get_name(code))
        code = self._instrument_inner_code_objects(code)
        instructions = Bytecode.from_code(code)
        iterator: ListIterator = ListIterator(instructions)
        inserted_at_start = False
        while iterator.next():
            current = iterator.current()

            if not inserted_at_start:
                if add_global_tracer:
                    self._add_tracer_to_globals(iterator)
                self._add_code_object_entered(
                    iterator, current.lineno, self._get_name(code)
                )
                inserted_at_start = True

            if isinstance(current, Instr) and current.name == "FOR_ITER":
                # If the FOR_ITER instruction is a jump target
                # we have to add our changes before the label
                instruction_offset = 0
                if iterator.has_previous() and isinstance(iterator.previous(), Label):
                    instruction_offset = 1

                self._add_for_loop_check(
                    iterator, instruction_offset, current.lineno,
                )

            if isinstance(current, Instr) and current.is_cond_jump():
                if (
                    iterator.has_previous()
                    and isinstance(iterator.previous(), Instr)
                    and iterator.previous().name == "COMPARE_OP"
                    and not iterator.previous().arg
                    in BranchDistanceInstrumentation._IGNORED_COMPARE_OPS
                ):
                    self._add_cmp_predicate(iterator, current.lineno)
                else:
                    self._add_bool_predicate(iterator, current.lineno)
        return instructions.to_code()

    def _add_bool_predicate(
        self, iterator: ListIterator, lineno: Optional[int]
    ) -> None:
        self._tracer.predicate_exists(self._predicate_id)
        iterator.insert_before(
            [
                Instr("DUP_TOP", lineno=lineno),
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.passed_bool_predicate.__name__,
                    lineno=lineno,
                ),
                Instr("ROT_THREE", lineno=lineno),
                Instr("ROT_THREE", lineno=lineno),
                Instr("LOAD_CONST", self._predicate_id, lineno=lineno),
                Instr("CALL_METHOD", 2, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
            ]
        )
        self._predicate_id += 1

    def _add_cmp_predicate(self, iterator: ListIterator, lineno: Optional[int]) -> None:
        cmp_op = iterator.previous()
        self._tracer.predicate_exists(self._predicate_id)
        iterator.insert_before(
            [
                Instr("DUP_TOP_TWO", lineno=lineno),
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.passed_cmp_predicate.__name__,
                    lineno=lineno,
                ),
                Instr("ROT_FOUR", lineno=lineno),
                Instr("ROT_FOUR", lineno=lineno),
                Instr("LOAD_CONST", self._predicate_id, lineno=lineno),
                Instr("LOAD_CONST", cmp_op.arg, lineno=lineno),
                Instr("CALL_METHOD", 4, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
            ],
            1,
        )
        self._predicate_id += 1

    def _add_code_object_entered(
        self, iterator: ListIterator, lineno: Optional[int], name: str
    ) -> None:
        self._tracer.code_object_exists(self._code_object_id, name)
        self._add_entered_call(
            iterator,
            ExecutionTracer.entered_code_object.__name__,
            self._code_object_id,
            lineno,
        )
        self._code_object_id += 1

    def _add_for_loop_check(
        self, iterator: ListIterator, instruction_offset: int, lineno: Optional[int],
    ) -> None:
        self._tracer.predicate_exists(self._predicate_id)
        # Label, if the iterator returns no value
        no_element = Label()
        # Label to the beginning of the for loop body
        for_loop_body = Label()
        # Label to exit of the for loop
        for_loop_exit = iterator.current().arg
        iterator.insert_before(
            [
                Instr("FOR_ITER", no_element, lineno=lineno),
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.passed_bool_predicate.__name__,
                    lineno=lineno,
                ),
                Instr("LOAD_CONST", True, lineno=lineno),
                Instr("LOAD_CONST", self._predicate_id, lineno=lineno),
                Instr("CALL_METHOD", 2, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
                Instr("JUMP_ABSOLUTE", for_loop_body, lineno=lineno),
                no_element,
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.passed_bool_predicate.__name__,
                    lineno=lineno,
                ),
                Instr("LOAD_CONST", False, lineno=lineno),
                Instr("LOAD_CONST", self._predicate_id, lineno=lineno),
                Instr("CALL_METHOD", 2, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
                Instr("JUMP_ABSOLUTE", for_loop_exit, lineno=lineno),
            ],
            instruction_offset,
        )
        iterator.insert_after_current([for_loop_body])
        self._predicate_id += 1

    @staticmethod
    def _add_entered_call(
        iterator: ListIterator, method_to_call: str, call_id: int, lineno: Optional[int]
    ) -> None:
        iterator.insert_before(
            [
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr("LOAD_METHOD", method_to_call, lineno=lineno),
                Instr("LOAD_CONST", call_id, lineno=lineno),
                Instr("CALL_METHOD", 1, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
            ]
        )

    def _add_tracer_to_globals(self, iterator: ListIterator) -> None:
        """Add the tracer to the globals."""
        iterator.insert_before(
            [Instr("LOAD_CONST", self._tracer), Instr("STORE_GLOBAL", TRACER_NAME)]
        )

    @staticmethod
    def _get_name(code: CodeType) -> str:
        """Compute name to easily identify a code object."""
        return f"{code.co_filename}.{code.co_name}:{code.co_firstlineno}"

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module."""
        for const in module_code.co_consts:
            if isinstance(const, ExecutionTracer):
                # Abort instrumentation, since we have already
                # instrumented this code object.
                assert False, "Tried to instrument already instrumented module."
        return self._instrument_code_recursive(module_code, True)
