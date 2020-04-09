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

from bytecode import Instr, Bytecode, Compare

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
        self._for_loop_id: int = 0
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
        # Nested code objects are found within the consts of the CodeType.
        code = self._instrument_inner_code_objects(code)
        instructions = Bytecode.from_code(code)
        code_iter: ListIterator = ListIterator(instructions)
        code_object_entered_inserted = False
        while code_iter.next():
            if not code_object_entered_inserted:
                self._add_code_object_entered(code_iter)
                code_object_entered_inserted = True

            if (
                code_iter.has_previous()
                and isinstance(code_iter.previous(), Instr)
                and code_iter.previous().name == "FOR_ITER"
            ):
                self._add_for_loop_entered(code_iter)

            current = code_iter.current()
            if isinstance(current, Instr) and current.is_cond_jump():
                if (
                    code_iter.has_previous()
                    and isinstance(code_iter.previous(), Instr)
                    and code_iter.previous().name == "COMPARE_OP"
                    and not code_iter.previous().arg
                    in BranchDistanceInstrumentation._IGNORED_COMPARE_OPS
                ):
                    self._add_cmp_predicate(code_iter)
                else:
                    self._add_bool_predicate(code_iter)
        return instructions.to_code()

    def _add_bool_predicate(self, iterator: ListIterator) -> None:
        self._tracer.predicate_exists(self._predicate_id)
        stmts = [
            Instr("DUP_TOP"),
            Instr("LOAD_GLOBAL", TRACER_NAME),
            Instr("LOAD_METHOD", ExecutionTracer.passed_bool_predicate.__name__),
            Instr("ROT_THREE"),
            Instr("ROT_THREE"),
            Instr("LOAD_CONST", self._predicate_id),
            Instr("CALL_METHOD", 2),
            Instr("POP_TOP"),
        ]
        iterator.insert_before(stmts)
        self._predicate_id += 1

    def _add_cmp_predicate(self, iterator: ListIterator) -> None:
        cmp_op = iterator.previous()
        self._tracer.predicate_exists(self._predicate_id)
        stmts = [
            Instr("DUP_TOP_TWO"),
            Instr("LOAD_GLOBAL", TRACER_NAME),
            Instr("LOAD_METHOD", ExecutionTracer.passed_cmp_predicate.__name__),
            Instr("ROT_FOUR"),
            Instr("ROT_FOUR"),
            Instr("LOAD_CONST", self._predicate_id),
            Instr("LOAD_CONST", cmp_op.arg),
            Instr("CALL_METHOD", 4),
            Instr("POP_TOP"),
        ]
        iterator.insert_before(stmts, 1)
        self._predicate_id += 1

    def _add_code_object_entered(self, iterator: ListIterator) -> None:
        self._tracer.code_object_exists(self._code_object_id)
        self._add_entered_call(
            iterator, ExecutionTracer.entered_code_object.__name__, self._code_object_id
        )
        self._code_object_id += 1

    def _add_for_loop_entered(self, iterator: ListIterator) -> None:
        self._tracer.for_loop_exists(self._for_loop_id)
        self._add_entered_call(
            iterator, ExecutionTracer.entered_for_loop.__name__, self._for_loop_id
        )
        self._for_loop_id += 1

    @staticmethod
    def _add_entered_call(
        iterator: ListIterator, method_to_call: str, call_id: int
    ) -> None:
        stmts = [
            Instr("LOAD_GLOBAL", TRACER_NAME),
            Instr("LOAD_METHOD", method_to_call),
            Instr("LOAD_CONST", call_id),
            Instr("CALL_METHOD", 1),
            Instr("POP_TOP"),
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
