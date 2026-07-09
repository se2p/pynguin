#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an abstract observer that can be used to generate assertions."""

from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Sized
from types import ModuleType
from typing import TYPE_CHECKING, Any

import libcst as cst

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.configuration as config
import pynguin.testcase.execution as ex
import pynguin.utils.typetracing as tt
from pynguin.assertion.assertion_to_ast import assertion_to_cst
from pynguin.utils.exceptions import TracingAbortedException
from pynguin.utils.naming import get_module_alias
from pynguin.utils.type_utils import is_assertable, is_primitive_type

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc

_LOGGER = logging.getLogger(__name__)

# Sentinel returned by ``RemoteAssertionTraceObserver._resolve_source`` when a
# (possibly dotted) reference path cannot be resolved against the namespace.
_UNRESOLVED = object()


class RemoteAssertionTraceObserver(ex.RemoteExecutionObserver):
    """Remote observer that creates assertions.

    Observes the per-statement execution of a test case and generates
    assertions from it.
    """

    class RemoteAssertionLocalState(threading.local):
        """Stores thread-local assertion data."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.trace: at.AssertionTrace = at.AssertionTrace()
            # Variables (by name) whose value is continually re-checked after
            # every subsequent statement, mirroring main's watch_list of
            # VariableReferences.
            self.watch_list: list[str] = []
            # Statements are executed in a simple loop (see
            # TestCaseExecutor._execute_test_case), so unlike the old AST-based
            # ExecutionContext there is no Statement.get_position(); track the
            # position ourselves, incremented once per after_statement_execution
            # call.
            self.position: int = 0

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self._assertion_local_state = RemoteAssertionTraceObserver.RemoteAssertionLocalState()

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

    def after_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        executor: ex.TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        position = self._assertion_local_state.position
        self._assertion_local_state.position = position + 1

        if exception is not None:
            self._assertion_local_state.trace.add_entry(
                position,
                ass.ExceptionAssertion(
                    module=type(exception).__module__,
                    exception_type_name=type(exception).__name__,
                ),
            )
            return

        if statement.bound_variable is not None:
            self._handle(statement.bound_variable, namespace, position)

    def after_test_case_execution(  # noqa: D102
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ):
        result.assertion_trace = self.get_trace()

    def _handle(
        self,
        bound_variable: str,
        namespace: dict[str, Any],
        position: int,
    ) -> None:
        """Generate assertions for the variable a statement just bound.

        Mirrors main's ``RemoteAssertionTraceObserver._handle``, adapted to the
        libcst representation: references are plain variable names, or dotted
        attribute-access paths rooted at a namespace entry (e.g. module static
        fields), looked up in the shared execution namespace instead of
        ``VariableReference``s resolved through an ``ExecutionContext``.

        In addition to the bound variable and the watch list, this also
        (re-)checks the public static fields of the module under test after
        every statement, mirroring main's module-field enumeration.

        Args:
            bound_variable: The name of the variable the statement bound.
            namespace: The shared execution namespace.
            position: The position of the statement after whose execution the
                state is observed.
        """
        trace = self._assertion_local_state.trace
        watch_list = self._assertion_local_state.watch_list

        value = tt.unwrap(namespace.get(bound_variable))
        if is_primitive_type(type(value)):
            # Primitives won't change, so we only check them once.
            self._check_reference(namespace, bound_variable, position, trace)
        elif type(value).__module__ != "builtins":
            # Everything else is continually checked, unless it is from builtins.
            watch_list.append(bound_variable)

        for var_name in watch_list:
            self._check_reference(namespace, var_name, position, trace)

        # Check the static fields of the module under test. Unlike main (which
        # enumerated every imported module), the libcst representation only
        # ever imports the SUT module into the namespace (under its alias), so
        # this covers the SUT module only.
        module_alias = get_module_alias(config.configuration.module_name)
        module = namespace.get(module_alias)
        if isinstance(module, ModuleType):
            for field, field_value in vars(module).items():
                if self._should_ignore(field, field_value):
                    continue
                self._check_reference(namespace, f"{module_alias}.{field}", position, trace)

    @staticmethod
    def _should_ignore(field: str, value: Any) -> bool:
        """Check whether a static field should be ignored for assertions.

        Args:
            field: The name of the field.
            value: The value of the field.

        Returns:
            True, if the field should not be turned into an assertion.
        """
        return (
            field.startswith("_")
            or field.endswith("__")
            or callable(value)
            or isinstance(value, ModuleType)
        )

    @staticmethod
    def _resolve_source(namespace: dict[str, Any], source: str) -> Any:
        """Resolve a (possibly dotted) reference path against the namespace.

        Args:
            namespace: The shared execution namespace.
            source: A variable name, or a dotted attribute-access path rooted
                at a namespace entry (e.g. a module field's
                ``"<alias>.<field>"``).

        Returns:
            The resolved value, or ``_UNRESOLVED`` if the root is not in the
            namespace or an attribute in the path could not be accessed.
        """
        root, *attrs = source.split(".")
        if root not in namespace:
            return _UNRESOLVED
        value = namespace[root]
        try:
            for attr in attrs:
                value = getattr(value, attr)
        except BaseException:  # noqa: BLE001  descriptors may raise anything
            return _UNRESOLVED
        return tt.unwrap(value)

    def _check_reference(
        self,
        namespace: dict[str, Any],
        var_name: str,
        position: int,
        trace: at.AssertionTrace,
    ) -> None:
        """Check if we can generate an assertion for the given variable.

        Args:
            namespace: The shared execution namespace.
            var_name: The name of the variable (or dotted reference path)
                that should be checked.
            position: The position of the test case after which the assertions
                are made.
            trace: The assertion trace where the observed assertions are stored.
        """
        value = self._resolve_source(namespace, var_name)
        if value is _UNRESOLVED:
            return
        if isinstance(value, float):
            trace.add_entry(position, ass.FloatAssertion(var_name, value))
            return
        if is_assertable(value):
            trace.add_entry(position, ass.ObjectAssertion(var_name, copy.deepcopy(value)))
            return

        # No precise assertion possible, so assert on type.
        typ = type(value)
        if hasattr(typ, "__module__") and hasattr(typ, "__qualname__"):
            if self._is_type_importable(typ):
                trace.add_entry(
                    position,
                    ass.IsInstanceAssertion(var_name, typ.__module__, typ.__qualname__),
                )
            else:
                trace.add_entry(
                    position,
                    ass.TypeNameAssertion(var_name, typ.__module__, typ.__qualname__),
                )
        if isinstance(value, Sized):
            try:
                length = len(value)
            except BaseException as err:  # noqa: BLE001
                # Could not get len, so give up on this reference.
                _LOGGER.debug(err)
                return
            trace.add_entry(position, ass.CollectionLengthAssertion(var_name, length))

    @staticmethod
    def _is_type_importable(typ: type) -> bool:
        """Check whether a type can be referenced from the generated test file.

        Unlike main's ``ExecutionContext``-based writer, the libcst exporter
        (``pynguin.testcase.export.TestSuiteWriter``) only ever imports the SUT
        module (under its alias) plus builtins; it does not track and import
        arbitrary modules referenced by assertions. An ``IsInstanceAssertion``
        is therefore only safe for builtins or types defined in the SUT module
        itself -- anything else falls back to the always-safe
        ``TypeNameAssertion``, which only compares string names and needs no
        import.

        Args:
            typ: The type to check.

        Returns:
            True, if an isinstance-based assertion can safely be rendered.
        """
        if not hasattr(typ, "__module__") or not hasattr(typ, "__qualname__"):
            return False
        if typ.__module__ == "builtins":
            return True
        return typ.__module__ == config.configuration.module_name


class RemoteAssertionVerificationObserver(ex.RemoteExecutionObserver):
    """This remote observer is used to check if assertions hold.

    Adapted from main's ``ExecutionContext``-based verification: instead of
    wrapping an exception-raising statement in ``pytest.raises`` before
    execution, exception-only statements are checked directly against the
    real exception the executor already captured for that statement (the
    per-statement loop in ``TestCaseExecutor._execute_test_case`` gives us
    this for free). Regular value assertions are rendered to source via
    ``assertion_to_cst`` and executed directly against the shared namespace,
    same as main did via ``execute_ast``.
    """

    class RemoteAssertionExecutorLocalState(threading.local):
        """Local state for assertion executor."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.trace = at.AssertionVerificationTrace()
            # See RemoteAssertionTraceObserver.RemoteAssertionLocalState.position.
            self.position: int = 0

    def __init__(self):  # noqa: D107
        super().__init__()
        self._state = RemoteAssertionVerificationObserver.RemoteAssertionExecutorLocalState()

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return {
            "trace": self._state.trace,
        }

    @state.setter
    def state(self, state: dict[str, Any]) -> None:
        self._state.trace = state["trace"]

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        executor: ex.TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        position = self._state.position
        self._state.position = position + 1

        if statement.has_only_exception_assertion():
            assertion = next(iter(statement.assertions))
            expected_name = assertion.exception_type_name  # type: ignore[attr-defined]
            if exception is None:
                # The expected exception was not raised.
                self._state.trace.failed[position].add(0)
            elif type(exception).__name__ != expected_name:
                # A different exception was raised; treat as an error, not a
                # (clean) assertion violation, mirroring main.
                self._state.trace.error[position].add(0)
            return

        for idx, assertion in enumerate(statement.assertions):
            cst_node = assertion_to_cst(assertion)
            if cst_node is None:
                continue
            code_str = cst.Module(body=[cst_node]).code
            try:
                exec(compile(code_str, "<assertion>", "exec"), namespace)  # noqa: S102
            except TracingAbortedException:
                # Must always propagate, so the watchdog thread can be killed.
                raise
            except AssertionError:
                self._state.trace.failed[position].add(idx)
            except BaseException as exc:  # noqa: BLE001
                _LOGGER.debug(exc)
                self._state.trace.error[position].add(idx)

    def after_test_case_execution(  # noqa: D102
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ) -> None:
        result.assertion_verification_trace = self._state.trace
