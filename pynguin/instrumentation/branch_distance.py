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
import inspect
from types import FunctionType, CodeType
from typing import Set, Optional, Any

from bytecode import Instr, Bytecode, Compare, Label

from pynguin.instrumentation.basis import TRACER_NAME
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.utils import type_utils
from pynguin.utils.iterator import ListIterator


class BranchDistanceInstrumentation:
    """Instruments modules/classes/methods/functions to enable branch distance tracking."""

    _INSTRUMENTED_FLAG: str = "pynguin_instrumented"

    # As of CPython 3.8, there are a few compare ops for which we can't really
    # compute a sensible branch distance. So for now, we just ignore those
    # comparisons and just track the result.
    # TODO(fk) update this to work with the bytecode for CPython 3.9, once it is released.
    _IGNORED_COMPARE_OPS: Set[Compare] = {Compare.EXC_MATCH}

    def __init__(self, tracer: ExecutionTracer) -> None:
        self._code_object_id: int = 0
        self._predicate_id: int = 0
        self._tracer = tracer

    def instrument_function(self, to_instrument: FunctionType) -> None:
        """Adds branch distance instrumentation to the given function."""
        # Prevent multiple instrumentation
        assert not hasattr(
            to_instrument, BranchDistanceInstrumentation._INSTRUMENTED_FLAG
        ), "Function is already instrumented"
        setattr(to_instrument, BranchDistanceInstrumentation._INSTRUMENTED_FLAG, True)

        # install tracer in the globals of the function so we can call it from bytecode
        to_instrument.__globals__[TRACER_NAME] = self._tracer
        to_instrument.__code__ = self._instrument_code_recursive(to_instrument.__code__)

    def _instrument_inner_code_objects(self, code: CodeType) -> CodeType:
        new_consts = []
        for const in code.co_consts:
            if hasattr(const, "co_code"):
                # The const is an inner code object
                new_consts.append(self._instrument_code_recursive(const))
            else:
                new_consts.append(const)
        return code.replace(co_consts=tuple(new_consts))

    def _instrument_code_recursive(self, code: CodeType) -> CodeType:
        """Instrument the given CodeType recursively."""
        # TODO(fk) Change instrumentation to make use of a visitor pattern, similar to ASM in Java.
        # The instrumentation loop is already getting really big...

        # Nested code objects are found within the consts of the CodeType.
        code = self._instrument_inner_code_objects(code)
        instructions = Bytecode.from_code(code)
        code_iter: ListIterator = ListIterator(instructions)
        code_object_entered_inserted = False
        while code_iter.next():
            current = code_iter.current()

            if not code_object_entered_inserted:
                self._add_code_object_entered(code_iter, current.lineno)
                code_object_entered_inserted = True

            if code_iter.has_previous():
                prev = code_iter.previous()
                if isinstance(prev, Instr) and prev.name == "GET_ITER":
                    for_iter_instr: Optional[Instr] = None
                    for_loop_body_offset = 0
                    # There might be a Label between GET_ITER and FOR_ITER
                    # We have to check for it.
                    if isinstance(current, Instr) and current.name == "FOR_ITER":
                        for_iter_instr = current
                    elif code_iter.can_peek():
                        peek = code_iter.peek()
                        if (
                            isinstance(current, Label)
                            and isinstance(peek, Instr)
                            and peek.name == "FOR_ITER"
                        ):
                            for_iter_instr = peek
                            # We have to account for the label
                            for_loop_body_offset = 1

                    if for_iter_instr is not None:
                        self._add_for_loop_check(
                            code_iter,
                            for_iter_instr,
                            for_loop_body_offset,
                            for_iter_instr.lineno,
                        )

            if isinstance(current, Instr) and current.is_cond_jump():
                if (
                    code_iter.has_previous()
                    and isinstance(code_iter.previous(), Instr)
                    and code_iter.previous().name == "COMPARE_OP"
                    and not code_iter.previous().arg
                    in BranchDistanceInstrumentation._IGNORED_COMPARE_OPS
                ):
                    self._add_cmp_predicate(code_iter, current.lineno)
                else:
                    self._add_bool_predicate(code_iter, current.lineno)
        return instructions.to_code()

    def _add_bool_predicate(
        self, iterator: ListIterator, lineno: Optional[int]
    ) -> None:
        self._tracer.predicate_exists(self._predicate_id)
        stmts = [
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
        iterator.insert_before(stmts)
        self._predicate_id += 1

    def _add_cmp_predicate(self, iterator: ListIterator, lineno: Optional[int]) -> None:
        cmp_op = iterator.previous()
        self._tracer.predicate_exists(self._predicate_id)
        stmts = [
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
        ]
        iterator.insert_before(stmts, 1)
        self._predicate_id += 1

    def _add_code_object_entered(
        self, iterator: ListIterator, lineno: Optional[int]
    ) -> None:
        self._tracer.code_object_exists(self._code_object_id)
        self._add_entered_call(
            iterator,
            ExecutionTracer.entered_code_object.__name__,
            self._code_object_id,
            lineno,
        )
        self._code_object_id += 1

    def _add_for_loop_check(
        self,
        iterator: ListIterator,
        for_iter_instr: Instr,
        for_loop_body_offset: int,
        lineno: Optional[int],
    ) -> None:
        self._tracer.predicate_exists(self._predicate_id)
        # Label, if the iterator returns no value
        no_element = Label()
        # Label to the beginning of the for loop body
        for_loop_body = Label()
        # Label to exit of the for loop
        for_loop_exit = for_iter_instr.arg
        to_insert = [
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
        ]
        iterator.insert_after_current([for_loop_body], for_loop_body_offset)
        iterator.insert_before(to_insert)
        self._predicate_id += 1

    @staticmethod
    def _add_entered_call(
        iterator: ListIterator, method_to_call: str, call_id: int, lineno: Optional[int]
    ) -> None:
        stmts = [
            Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
            Instr("LOAD_METHOD", method_to_call, lineno=lineno),
            Instr("LOAD_CONST", call_id, lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        iterator.insert_before(stmts)

    def instrument(
        self, obj, module_name: str, seen: Optional[Set[Any]] = None
    ) -> None:
        """
        Recursively instruments the given object and all functions within it.
        Technically there are a lot of different objects in Python that contain code,
        but we are only interested in functions, because methods are just wrappers around functions.
        See https://docs.python.org/3/library/inspect.html.

        There a also special objects for generators and coroutines that contain code,
        but these should not be of interest for us. If they should prove interesting,
        then a more sophisticated approach similar to dis.dis() should be adopted.
        """
        if not seen:
            seen = set()

        if obj in seen:
            return
        seen.add(obj)
        members = inspect.getmembers(obj)
        for (_, value) in members:
            if type_utils.function_in_module(module_name)(value):
                self.instrument_function(value)
            if type_utils.class_in_module(module_name)(value) or inspect.ismethod(
                value
            ):
                self.instrument(value, module_name, seen)
