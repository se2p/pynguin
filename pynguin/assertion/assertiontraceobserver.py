#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract observer that can be used to generate assertions."""
import copy
from types import ModuleType
from typing import Sized, cast

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.testcase.execution as ex
import pynguin.testcase.statement as st
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.testcase.execution import ExecutionContext
from pynguin.utils.type_utils import (
    is_assertable,
    is_collection_type,
    is_ignorable_type,
    is_primitive_type,
)


class AssertionTraceObserver(ex.ExecutionObserver):
    """Observer that creates assertions.
    Observes the execution of a test case and generates assertions from it."""

    def __init__(self) -> None:
        self._trace: at.AssertionTrace = at.AssertionTrace()
        self._watch_list: list[vr.VariableReference] = []

    def clear(self) -> None:
        """Clear the existing gathered trace."""
        self._trace.clear()
        self._watch_list.clear()

    def get_trace(self) -> at.AssertionTrace:
        """Get a copy of the gathered trace.

        Returns:
            A copy of the gathered trace.

        """
        return self._trace.clone()

    def before_test_case_execution(self, test_case: tc.TestCase):
        self.clear()

    def before_statement_execution(
        self, statement: st.Statement, exec_ctx: ExecutionContext
    ):
        # Nothing to do before statement.
        pass

    def after_statement_execution(
        self,
        statement: st.Statement,
        exec_ctx: ex.ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        if exception is not None:
            self._trace.add_entry(
                statement.get_position(),
                ass.ExceptionAssertion(
                    module=type(exception).__module__,
                    exception_type_name=type(exception).__name__,
                ),
            )
            return
        if statement.affects_assertions:
            stmt = cast(st.VariableCreatingStatement, statement)
            self._handle(stmt, exec_ctx)

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ):
        result.add_assertion_trace(type(self), self.get_trace())

    def _handle(
        self, statement: st.VariableCreatingStatement, exec_ctx: ex.ExecutionContext
    ) -> None:
        """Actually handle the statement.

        Args:
            exec_ctx: the execution context.
            statement: the statement that is visited.
        """
        position = statement.get_position()

        if not statement.ret_val.is_none_type():
            if is_primitive_type(type(exec_ctx.get_reference_value(statement.ret_val))):
                # Primitives won't change, so we only check them once.
                self._check_reference(exec_ctx, statement.ret_val, position)
            else:
                # Everything else is continually checked.
                self._watch_list.append(statement.ret_val)

        for var in self._watch_list:
            self._check_reference(exec_ctx, var, position)

        # Check all used modules.
        for module_name, alias in exec_ctx.module_aliases:
            module = exec_ctx.global_namespace[alias]

            # Check all static fields.
            for field, value in vars(module).items():
                if self._should_ignore(field, value):
                    continue
                self._check_reference(
                    exec_ctx,
                    vr.StaticModuleFieldReference(
                        gao.GenericStaticModuleField(module_name, field, type(value))
                    ),
                    position,
                )

        # Check fields of classes whose constructors were used.
        for seen_type in [
            type(exec_ctx.get_reference_value(ref)) for ref in self._watch_list
        ]:
            if (
                is_primitive_type(seen_type)
                or is_collection_type(seen_type)
                or is_ignorable_type(seen_type)
            ):
                continue

            if not hasattr(seen_type, "__dict__"):
                continue

            for field, value in vars(seen_type).items():
                if self._should_ignore(field, value):
                    continue
                self._check_reference(
                    exec_ctx,
                    vr.StaticFieldReference(
                        gao.GenericStaticField(seen_type, field, type(value))
                    ),
                    position,
                )

    def _check_reference(  # pylint: disable=too-many-arguments
        self,
        exec_ctx: ex.ExecutionContext,
        ref: vr.Reference,
        position: int,
        depth: int = 0,
        max_depth: int = 1,
    ) -> None:
        """Check if we can generate an assertion for the given reference.
        For complex types, we do one recursion step, i.e., try to assert anything
        on the attributes of the given object.

        Args:
            exec_ctx: The execution context.
            ref: The reference that should be checked.
            position: The position of the test case after which the assertions are made.
            depth: The current recursion depth
            max_depth: The maximum recursion depth.
        """
        value = exec_ctx.get_reference_value(ref)
        if isinstance(value, float):
            self._trace.add_entry(position, ass.FloatAssertion(ref, value))
        elif is_assertable(value):
            self._trace.add_entry(
                position, ass.ObjectAssertion(ref, copy.deepcopy(value))
            )
        elif isinstance(value, Sized):
            self._trace.add_entry(
                position, ass.CollectionLengthAssertion(ref, len(value))
            )
        elif depth < max_depth and hasattr(value, "__dict__"):
            asserted_something = False
            # Reference is a complex object.
            # Try to assert something on its fields.
            for field, field_value in vars(value).items():
                if not self._should_ignore(field, field_value):
                    asserted_something = True
                    self._check_reference(
                        exec_ctx,
                        vr.FieldReference(
                            ref, gao.GenericField(type(value), field, type(field_value))
                        ),
                        position,
                        depth + 1,
                    )
            if not asserted_something:
                # If we can assert nothing else, we can at least assert that it
                # is not None
                self._trace.add_entry(position, ass.NotNoneAssertion(ref))

    @staticmethod
    def _should_ignore(field, attr_value):
        return (
            field.startswith("_")
            or field.endswith("__")
            or callable(attr_value)
            or isinstance(attr_value, ModuleType)
        )
