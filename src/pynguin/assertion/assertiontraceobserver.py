#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an abstract observer that can be used to generate assertions."""

import ast
import copy
import logging
import threading

from collections.abc import Sized
from types import ModuleType
from typing import cast

from _pytest.outcomes import Failed  # noqa: PLC2701

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.testcase.execution as ex
import pynguin.testcase.statement as st
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.analyses.typesystem import ANY
from pynguin.analyses.typesystem import TypeInfo
from pynguin.utils.type_utils import is_assertable
from pynguin.utils.type_utils import is_collection_type
from pynguin.utils.type_utils import is_ignorable_type
from pynguin.utils.type_utils import is_primitive_type


_LOGGER = logging.getLogger(__name__)


class AssertionTraceObserver(ex.ExecutionObserver):
    """Observer that creates assertions.

    Observes the execution of a test case and generates assertions from it.
    """

    class AssertionLocalState(threading.local):
        """Stores thread-local assertion data."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.trace: at.AssertionTrace = at.AssertionTrace()
            self.watch_list: list[vr.VariableReference] = []

    def __init__(self) -> None:  # noqa: D107
        self._assertion_local_state = AssertionTraceObserver.AssertionLocalState()

    def get_trace(self) -> at.AssertionTrace:
        """Get a copy of the gathered trace.

        Returns:
            A copy of the gathered trace.

        """
        return self._assertion_local_state.trace.clone()

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def before_statement_execution(  # noqa: D102
        self, statement: st.Statement, node: ast.stmt, exec_ctx: ex.ExecutionContext
    ) -> ast.stmt:
        # Nothing to do before statement.
        return node

    def after_statement_execution(  # noqa: D102
        self,
        statement: st.Statement,
        executor: ex.TestCaseExecutor,
        exec_ctx: ex.ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        if exception is not None:
            self._assertion_local_state.trace.add_entry(
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

    def after_test_case_execution_inside_thread(  # noqa: D102
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ):
        result.assertion_trace = self.get_trace()

    def after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ):
        """Not used.

        Args:
            test_case: Not used
            result: Not used
        """

    def _handle(  # noqa: C901
        self, statement: st.VariableCreatingStatement, exec_ctx: ex.ExecutionContext
    ) -> None:
        """Actually handle the statement.

        Args:
            exec_ctx: the execution context.
            statement: the statement that is visited.
        """
        position = statement.get_position()

        trace = self._assertion_local_state.trace

        if not statement.ret_val.is_none_type():
            if is_primitive_type(type(exec_ctx.get_reference_value(statement.ret_val))):
                # Primitives won't change, so we only check them once.
                self._check_reference(exec_ctx, statement.ret_val, position, trace)
            elif type(exec_ctx.get_reference_value(statement.ret_val)).__module__ != "builtins":
                # Everything else is continually checked, unless it is from builtins.
                self._assertion_local_state.watch_list.append(statement.ret_val)

        for var in self._assertion_local_state.watch_list:
            self._check_reference(exec_ctx, var, position, trace)

        # Check all used modules.
        for module_name, alias in exec_ctx.module_aliases:
            if module_name == "builtins":
                # Don't assert stuff on builtins
                continue

            module = exec_ctx.global_namespace[alias]

            # Check all static fields.
            for field, value in vars(module).items():
                if self._should_ignore(field, value):
                    continue
                self._check_reference(
                    exec_ctx,
                    vr.StaticModuleFieldReference(
                        # Type information is not used here, so use Any.
                        gao.GenericStaticModuleField(module_name, field, ANY)
                    ),
                    position,
                    trace,
                )

        # Check fields of classes whose constructors were used.
        for seen_type in [
            type(exec_ctx.get_reference_value(ref))
            for ref in self._assertion_local_state.watch_list
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
                        # Type information is not used here, so use Any.
                        gao.GenericStaticField(TypeInfo(seen_type), field, ANY)
                    ),
                    position,
                    trace,
                )

    def _check_reference(
        self,
        exec_ctx: ex.ExecutionContext,
        ref: vr.Reference,
        position: int,
        trace: at.AssertionTrace,
        *,
        depth: int = 0,
        max_depth: int = 1,
    ):
        """Check if we can generate an assertion for the given reference.

        For complex types, we do one recursion step, i.e., try to assert anything
        on the attributes of the given object.

        Args:
            exec_ctx: The execution context.
            ref: The reference that should be checked.
            position: The position of the test case after which the assertions are made.
            trace: The assertion trace where the observed assertions are stored.
            depth: The current recursion depth
            max_depth: The maximum recursion depth.
        """
        value = exec_ctx.get_reference_value(ref)
        if isinstance(value, float):
            trace.add_entry(position, ass.FloatAssertion(ref, value))
            return
        if is_assertable(value):
            trace.add_entry(position, ass.ObjectAssertion(ref, copy.deepcopy(value)))
        else:
            # No precise assertion possible, so assert on type.
            typ = type(value)
            if hasattr(typ, "__module__") and hasattr(typ, "__qualname__"):
                trace.add_entry(
                    position,
                    ass.TypeNameAssertion(ref, typ.__module__, typ.__qualname__),
                )
            if isinstance(value, Sized):
                try:
                    length = len(value)
                    trace.add_entry(position, ass.CollectionLengthAssertion(ref, length))
                    return
                except BaseException as err:  # noqa: BLE001
                    # Could not get len, so continue down.
                    _LOGGER.debug(err)
            if depth < max_depth and hasattr(value, "__dict__"):
                # Reference is a complex object.
                # Try to assert something on its fields.
                for field, field_value in vars(value).items():
                    if not self._should_ignore(field, field_value):
                        self._check_reference(
                            exec_ctx,
                            vr.FieldReference(
                                ref,
                                # Type information is not used here, so use Any.
                                gao.GenericField(TypeInfo(type(value)), field, ANY),
                            ),
                            position,
                            trace,
                            depth=depth + 1,
                        )

    @staticmethod
    def _should_ignore(field, attr_value):
        return (
            field.startswith("_")
            or field.endswith("__")
            or callable(attr_value)
            or isinstance(attr_value, ModuleType)
        )


class AssertionVerificationObserver(ex.ExecutionObserver):
    """This observer is used to check if assertions hold."""

    class AssertionExecutorLocalState(threading.local):
        """Local state for assertion executor."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.trace = at.AssertionVerificationTrace()

    def __init__(self):  # noqa: D107
        self.state = AssertionVerificationObserver.AssertionExecutorLocalState()

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_test_case_execution_inside_thread(  # noqa: D102
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ) -> None:
        result.assertion_verification_trace = self.state.trace

    def after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ) -> None:
        """Not used.

        Args:
            test_case: Not used
            result: Not used
        """

    def before_statement_execution(  # noqa: D102
        self, statement: st.Statement, node: ast.stmt, exec_ctx: ex.ExecutionContext
    ) -> ast.stmt:
        if statement.has_only_exception_assertion():
            return exec_ctx.node_for_assertion(next(iter(statement.assertions)), node)
        return node

    def after_statement_execution(  # noqa: D102
        self,
        statement: st.Statement,
        executor: ex.TestCaseExecutor,
        exec_ctx: ex.ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        if statement.has_only_exception_assertion():
            if exception is None:
                return
            # If we have an exception assertion, all we have to do is check the
            # exception.
            if isinstance(exception, Failed):
                # Failed indicates that the expected assertion was not raised
                self.state.trace.failed[statement.get_position()].add(0)
            else:
                self.state.trace.error[statement.get_position()].add(0)
        else:
            # Other assertions are executed after the statement.
            for idx, assertion in enumerate(statement.assertions):
                exc = executor.execute_ast(
                    exec_ctx.wrap_node_in_module(
                        exec_ctx.node_for_assertion(assertion, ast.stmt())
                    ),
                    exec_ctx,
                )
                if exc is None:
                    continue

                if isinstance(exc, AssertionError):
                    self.state.trace.failed[statement.get_position()].add(idx)
                else:
                    self.state.trace.error[statement.get_position()].add(idx)
