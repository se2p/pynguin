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
from pynguin.utils.type_utils import (
    is_assertable,
    is_collection_type,
    is_ignorable_type,
    is_primitive_type,
)

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc

_LOGGER = logging.getLogger(__name__)

# Sentinel returned by ``_resolve_source`` when a dotted reference path (e.g.
# ``"<module_alias>.ClassName.field"``) could not be resolved against the
# current namespace -- either the root name is unknown, or an attribute
# access along the chain raised.
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
            # every subsequent statement.
            self.watch_list: list[str] = []
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

        References are plain variable names (or, for class-level static
        fields, dotted attribute paths) looked up in the shared execution
        namespace. After checking the freshly bound variable and the watch
        list, also asserts on the public static fields of the module under
        test and on the public static fields of the classes of currently
        watched objects.

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

        # Check the static fields of the module under test. Only the SUT
        # module is ever imported into the namespace (under its alias), so
        # this covers the SUT module only.
        module_alias = get_module_alias(config.configuration.module_name)
        module = namespace.get(module_alias)
        if isinstance(module, ModuleType):
            for field, field_value in vars(module).items():
                if self._should_ignore(field, field_value):
                    continue
                self._check_reference(namespace, f"{module_alias}.{field}", position, trace)

        self._check_static_class_fields(namespace, watch_list, position, trace)

    def _check_static_class_fields(
        self,
        namespace: dict[str, Any],
        watch_list: list[str],
        position: int,
        trace: at.AssertionTrace,
    ) -> None:
        """Assert on public class-level (static) fields of watched objects.

        For every distinct type among the currently watched objects, assert
        on its public, non-callable class attributes (e.g. a class-level
        counter mutated by a method). Restricted to classes defined in the
        SUT module, matching the scope the exporter can actually import (only
        the SUT module is ever imported, see ``_is_type_importable``); a set
        is used to avoid re-asserting the same class once per watched
        instance.

        Args:
            namespace: The shared execution namespace.
            watch_list: Names of currently watched (non-primitive, non-builtin)
                variables.
            position: The position of the statement after whose execution the
                state is observed.
            trace: The assertion trace where the observed assertions are stored.
        """
        module_alias = get_module_alias(config.configuration.module_name)
        seen_types = {type(tt.unwrap(namespace.get(name))) for name in watch_list}
        for seen_type in seen_types:
            if not self._is_static_field_owner(seen_type):
                continue
            class_source = ".".join([module_alias, *seen_type.__qualname__.split(".")])
            for field, field_value in vars(seen_type).items():
                if self._should_ignore(field, field_value):
                    continue
                self._check_reference(namespace, f"{class_source}.{field}", position, trace)

    @staticmethod
    def _is_static_field_owner(seen_type: type) -> bool:
        """Check whether a type's class-level fields should be enumerated.

        Args:
            seen_type: The type of a currently watched object.

        Returns:
            True, if ``seen_type`` is a plain, SUT-module-defined class whose
            ``vars()`` can be walked for public static fields.
        """
        if (
            is_primitive_type(seen_type)
            or is_collection_type(seen_type)
            or is_ignorable_type(seen_type)
            or not hasattr(seen_type, "__dict__")
        ):
            return False
        if not hasattr(seen_type, "__module__") or not hasattr(seen_type, "__qualname__"):
            return False
        return (
            seen_type.__module__ == config.configuration.module_name
            and "<locals>" not in seen_type.__qualname__
        )

    @staticmethod
    def _should_ignore(field: str, attr_value: Any) -> bool:
        """Check whether a class/module attribute should be skipped.

        Private/dunder names, methods, and (sub-)modules are not asserted on.
        Also skips descriptors that ``callable()`` does not catch
        (``staticmethod``/``classmethod``/``property`` objects), which would
        otherwise fall through to a harmless-but-noisy ``TypeNameAssertion`` on
        e.g. ``builtins.classmethod``.

        Args:
            field: The attribute's name.
            attr_value: The attribute's value.

        Returns:
            True, if the attribute should not be asserted on.
        """
        return (
            field.startswith("_")
            or field.endswith("__")
            or callable(attr_value)
            or isinstance(attr_value, ModuleType | staticmethod | classmethod | property)
        )

    @staticmethod
    def _resolve_source(namespace: dict[str, Any], source: str) -> Any:
        """Resolve a (possibly dotted) reference path against the namespace.

        Args:
            namespace: The shared execution namespace.
            source: A bare variable name, or a dotted attribute-access path
                (e.g. ``"<module_alias>.ClassName.field"``) rooted at a name in
                the namespace.

        Returns:
            The resolved (still wrapped) value, or ``_UNRESOLVED`` if the root
            name is not in the namespace or an attribute access along the
            chain raised.
        """
        root, *attrs = source.split(".")
        if root not in namespace:
            return _UNRESOLVED
        value = namespace[root]
        try:
            for attr in attrs:
                value = getattr(value, attr)
        except BaseException as err:  # noqa: BLE001 - descriptors may raise anything
            _LOGGER.debug(err)
            return _UNRESOLVED
        return value

    def _check_reference(
        self,
        namespace: dict[str, Any],
        source: str,
        position: int,
        trace: at.AssertionTrace,
        *,
        depth: int = 0,
        max_depth: int = 1,
    ) -> None:
        """Check if we can generate an assertion for the given reference.

        Args:
            namespace: The shared execution namespace.
            source: The (possibly dotted) reference path that should be
                checked, e.g. a bare variable name or a class-static field
                path such as ``"<module_alias>.ClassName.field"``.
            position: The position of the test case after which the assertions
                are made.
            trace: The assertion trace where the observed assertions are stored.
            depth: The current recursion depth.
            max_depth: The maximum recursion depth.
        """
        resolved = self._resolve_source(namespace, source)
        if resolved is _UNRESOLVED:
            return
        value = tt.unwrap(resolved)
        self._check_value(source, value, position, trace, depth=depth, max_depth=max_depth)

    def _check_value(
        self,
        source: str,
        value: Any,
        position: int,
        trace: at.AssertionTrace,
        *,
        depth: int,
        max_depth: int,
    ) -> None:
        """Check if we can generate an assertion for the given (resolved) value.

        For complex types, we do one recursion step, i.e., try to assert
        anything on the public fields of the given object.

        Args:
            source: The (possibly dotted) reference path this value was
                resolved from.
            value: The already-resolved, already-unwrapped value.
            position: The position of the test case after which the assertions
                are made.
            trace: The assertion trace where the observed assertions are stored.
            depth: The current recursion depth.
            max_depth: The maximum recursion depth.
        """
        if isinstance(value, float):
            trace.add_entry(position, ass.FloatAssertion(source, value))
            return
        if is_assertable(value):
            trace.add_entry(position, ass.ObjectAssertion(source, copy.deepcopy(value)))
            return

        self._check_type_and_recurse(
            source, value, position, trace, depth=depth, max_depth=max_depth
        )

    def _check_type_and_recurse(
        self,
        source: str,
        value: Any,
        position: int,
        trace: at.AssertionTrace,
        *,
        depth: int,
        max_depth: int,
    ) -> None:
        """Assert on the type/length of a non-assertable value, then recurse.

        Args:
            source: The (possibly dotted) reference path this value was
                resolved from.
            value: The already-resolved, already-unwrapped value.
            position: The position of the test case after which the assertions
                are made.
            trace: The assertion trace where the observed assertions are stored.
            depth: The current recursion depth.
            max_depth: The maximum recursion depth.
        """
        # No precise assertion possible, so assert on type.
        typ = type(value)
        if hasattr(typ, "__module__") and hasattr(typ, "__qualname__"):
            if self._is_type_importable(typ):
                trace.add_entry(
                    position,
                    ass.IsInstanceAssertion(source, typ.__module__, typ.__qualname__),
                )
            else:
                trace.add_entry(
                    position,
                    ass.TypeNameAssertion(source, typ.__module__, typ.__qualname__),
                )
        if isinstance(value, Sized):
            try:
                length = len(value)
            except BaseException as err:  # noqa: BLE001
                # Could not get len, so continue down to the field recursion below.
                _LOGGER.debug(err)
            else:
                trace.add_entry(position, ass.CollectionLengthAssertion(source, length))
                return

        if depth < max_depth and hasattr(value, "__dict__"):
            # Reference is a complex object; try to assert something on its
            # public fields (one recursion step).
            for field, field_value in vars(value).items():
                if self._should_ignore(field, field_value):
                    continue
                self._check_value(
                    f"{source}.{field}",
                    tt.unwrap(field_value),
                    position,
                    trace,
                    depth=depth + 1,
                    max_depth=max_depth,
                )

    @staticmethod
    def _is_type_importable(typ: type) -> bool:
        """Check whether a type can be referenced from the generated test file.

        The exporter (``pynguin.testcase.export.TestSuiteWriter``) only ever
        imports the SUT module (under its alias) plus builtins; it does not
        track and import arbitrary modules referenced by assertions. An
        ``IsInstanceAssertion`` is therefore only safe for builtins or types
        defined in the SUT module itself -- anything else falls back to the
        always-safe ``TypeNameAssertion``, which only compares string names
        and needs no import.

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

    Instead of wrapping an exception-raising statement in ``pytest.raises``
    before execution, exception-only statements are checked directly against
    the real exception the executor already captured for that statement (the
    per-statement loop in ``TestCaseExecutor._execute_test_case`` gives us
    this for free). Regular value assertions are rendered to source via
    ``assertion_to_cst`` and executed directly against the shared namespace.
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
                # (clean) assertion violation.
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
