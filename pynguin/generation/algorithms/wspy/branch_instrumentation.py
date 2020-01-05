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
from types import FunctionType
from typing import Set

from bytecode import Instr, Bytecode  # type: ignore

from pynguin.generation.algorithms.wspy.tracking import ExecutionTracer
from pynguin.utils.iterator import ListIterator


class BranchInstrumentation:
    """Instruments modules/classes/methods to enable branch distance tracking."""

    _INSTRUMENTED_FLAG: str = "instrumented"

    def __init__(self, tracer: ExecutionTracer) -> None:
        self._predicate_id: int = 0
        self._method_id: int = 0
        self._tracer = tracer

    def instrument_method(self, to_instrument: FunctionType) -> None:
        """Adds branch distance instrumentation to the given method."""
        # Prevent multiple instrumentation
        assert not hasattr(
            to_instrument, BranchInstrumentation._INSTRUMENTED_FLAG
        ), "Method is already instrumented"
        setattr(to_instrument, BranchInstrumentation._INSTRUMENTED_FLAG, True)

        to_instrument.__globals__["tracer"] = self._tracer
        instructions = Bytecode.from_code(to_instrument.__code__)
        code_iter: ListIterator = ListIterator(instructions)
        method_inserted = False
        while code_iter.next():
            if not method_inserted:
                self._add_method_entered(code_iter)
                method_inserted = True
            current = code_iter.current()
            if isinstance(current, Instr) and current.is_cond_jump():
                if (
                    code_iter.has_previous()
                    and isinstance(code_iter.previous(), Instr)
                    and code_iter.previous().name == "COMPARE_OP"
                ):
                    self._add_cmp_predicate(code_iter)
                else:
                    self._add_bool_predicate(code_iter)
        to_instrument.__code__ = instructions.to_code()

    def _add_bool_predicate(self, iterator: ListIterator) -> None:
        self._tracer.predicate_exists(self._predicate_id)
        stmts = [
            Instr("DUP_TOP"),
            Instr("LOAD_GLOBAL", "tracer"),
            Instr("LOAD_METHOD", "passed_bool_predicate"),
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
            Instr("LOAD_GLOBAL", "tracer"),
            Instr("LOAD_METHOD", "passed_cmp_predicate"),
            Instr("ROT_FOUR"),
            Instr("ROT_FOUR"),
            Instr("LOAD_CONST", self._predicate_id),
            Instr("LOAD_CONST", cmp_op.arg),
            Instr("CALL_METHOD", 4),
            Instr("POP_TOP"),
        ]
        iterator.insert_before(stmts, 1)
        self._predicate_id += 1

    def _add_method_entered(self, iterator: ListIterator) -> None:
        self._tracer.method_exists(self._method_id)
        stmts = [
            Instr("LOAD_GLOBAL", "tracer"),
            Instr("LOAD_METHOD", "entered_method"),
            Instr("LOAD_CONST", self._method_id),
            Instr("CALL_METHOD", 1),
            Instr("POP_TOP"),
        ]
        iterator.insert_before(stmts)
        self._method_id += 1

    def instrument(self, obj, seen: Set = None) -> None:
        """
        Recursively instruments the given object and all methods/classes within it.
        """
        if not seen:
            seen = set()

        if obj in seen:
            return
        seen.add(obj)

        members = inspect.getmembers(obj)
        for (_, value) in members:
            if inspect.isfunction(value):
                self.instrument_method(value)
            if inspect.isclass(value):
                self.instrument(value, seen)
