#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an observer and statement visitor to create primitive assertions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pynguin.assertion.assertiontraceobserver as ato
import pynguin.assertion.primitivetraceentry as pte
import pynguin.testcase.statement as st
from pynguin.utils.type_utils import is_primitive_type

if TYPE_CHECKING:
    import pynguin.assertion.statetrace as ot
    import pynguin.testcase.execution as ex
    import pynguin.testcase.variablereference as vr


class PrimitiveTraceObserver(ato.AssertionTraceObserver):
    """An observer that creates assertions on primitive values."""

    def before_statement_execution(
        self, statement: st.Statement, exec_ctx: ex.ExecutionContext
    ):
        pass

    def after_statement_execution(
        self,
        statement: st.Statement,
        exec_ctx: ex.ExecutionContext,
        exception: Optional[Exception] = None,
    ) -> None:
        if statement.ret_val is None:
            return
        if exception is not None:
            return
        if statement.ret_val.is_none_type():
            return

        visitor = PrimitiveAssertionVisitor(exec_ctx, statement.ret_val, self._trace)
        statement.accept(visitor)


class PrimitiveAssertionVisitor(st.StatementVisitor):
    """
    Simple visitor to create primitive assertions.
    Primitive statements are not visited, because something like
    var0 = 5
    assert var0 == 5
    does not make much sense.
    """

    def __init__(
        self,
        exec_ctx: ex.ExecutionContext,
        variable: vr.VariableReference,
        trace: ot.StateTrace,
    ):
        self._exec_ctx = exec_ctx
        self._variable = variable
        self._trace = trace

    def visit_int_primitive_statement(self, stmt) -> None:
        pass

    def visit_float_primitive_statement(self, stmt) -> None:
        pass

    def visit_string_primitive_statement(self, stmt) -> None:
        pass

    def visit_bytes_primitive_statement(self, stmt) -> None:
        pass

    def visit_boolean_primitive_statement(self, stmt) -> None:
        pass

    def visit_none_statement(self, stmt) -> None:
        pass

    def visit_enum_statement(self, stmt) -> None:
        pass

    def visit_list_statement(self, stmt) -> None:
        pass

    def visit_set_statement(self, stmt) -> None:
        pass

    def visit_tuple_statement(self, stmt) -> None:
        pass

    def visit_dict_statement(self, stmt) -> None:
        pass

    def visit_constructor_statement(self, stmt) -> None:
        self.handle(stmt)

    def visit_method_statement(self, stmt) -> None:
        self.handle(stmt)

    def visit_function_statement(self, stmt) -> None:
        self.handle(stmt)

    def visit_field_statement(self, stmt) -> None:
        raise NotImplementedError("Fields are not supported yet")

    def visit_assignment_statement(self, stmt) -> None:
        raise NotImplementedError("Assignments are not supported yet")

    def handle(self, statement: st.VariableCreatingStatement) -> None:
        """Actually handle the statement.

        Args:
            statement: the statement that is visited.
        """
        value = self._exec_ctx.get_reference_value(self._variable)
        if value is None:
            return

        if is_primitive_type(type(value)):
            self._trace.add_entry(
                statement.get_position(),
                pte.PrimitiveTraceEntry(self._variable, value),
            )
