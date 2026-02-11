#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
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
from typing import Any, cast

from _pytest.outcomes import Failed  # noqa: PLC2701

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.testcase.execution as ex
import pynguin.testcase.statement as st
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.typetracing as tt
from pynguin.analyses.typesystem import ANY, TypeInfo
from pynguin.utils.type_utils import (
    is_assertable,
    is_collection_type,
    is_ignorable_type,
    is_primitive_type,
)

_LOGGER = logging.getLogger(__name__)


class RemoteAssertionTraceObserver(ex.RemoteExecutionObserver):
    """Remote observer that creates assertions.

    Observes the execution of a test case and generates assertions from it.
    """

    class RemoteAssertionLocalState(threading.local):
        """Stores thread-local assertion data."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.trace: at.AssertionTrace = at.AssertionTrace()
            self.watch_list: list[vr.VariableReference] = []

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
                    module=executor.module_provider.get_module(type(exception).__module__).__name__,
                    exception_type_name=type(exception).__name__,
                ),
            )
            return
        if statement.affects_assertions:
            stmt = cast("st.VariableCreatingStatement", statement)
            self._handle(stmt, executor.module_provider, exec_ctx)

    def after_test_case_execution(  # noqa: D102
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ):
        result.assertion_trace = self.get_trace()
        self._add_proxy_knowledge_assertions(test_case, result, executor.module_provider)

    def _handle(  # noqa: C901
        self,
        statement: st.VariableCreatingStatement,
        module_provider: ex.ModuleProvider,
        exec_ctx: ex.ExecutionContext,
    ) -> None:
        """Actually handle the statement.

        Args:
            exec_ctx: the execution context.
            module_provider: the module provider.
            statement: the statement that is visited.
        """
        position = statement.get_position()

        trace = self._assertion_local_state.trace

        if not statement.ret_val.is_none_type():
            ret_value = tt.unwrap(exec_ctx.get_reference_value(statement.ret_val))
            if is_primitive_type(type(ret_value)):
                # Primitives won't change, so we only check them once.
                self._check_reference(module_provider, exec_ctx, statement.ret_val, position, trace)
            elif type(exec_ctx.get_reference_value(statement.ret_val)).__module__ != "builtins":
                # Everything else is continually checked, unless it is from builtins.
                self._assertion_local_state.watch_list.append(statement.ret_val)

        for var in self._assertion_local_state.watch_list:
            self._check_reference(module_provider, exec_ctx, var, position, trace)

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
                    module_provider,
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
            type(tt.unwrap(exec_ctx.get_reference_value(ref)))
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
                    module_provider,
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
        module_provider: ex.ModuleProvider,
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
            module_provider: The module provider.
            exec_ctx: The execution context.
            ref: The reference that should be checked.
            position: The position of the test case after which the assertions are made.
            trace: The assertion trace where the observed assertions are stored.
            depth: The current recursion depth
            max_depth: The maximum recursion depth.
        """
        value = exec_ctx.get_reference_value(ref)
        value = tt.unwrap(value)
        if isinstance(value, float):
            trace.add_entry(position, ass.FloatAssertion(ref, value))
            return
        if is_assertable(value):
            trace.add_entry(position, ass.ObjectAssertion(ref, copy.deepcopy(value)))
        else:
            # No precise assertion possible, so assert on type.
            typ = type(value)
            if hasattr(typ, "__module__") and hasattr(typ, "__qualname__"):
                # Check if the type is importable in the test context
                if self._is_type_importable(typ, module_provider):
                    # Use isinstance assertion for importable types
                    trace.add_entry(
                        position,
                        ass.IsInstanceAssertion(
                            ref,
                            module_provider.get_module(typ.__module__).__name__,
                            typ.__qualname__,
                        ),
                    )
                else:
                    # Fallback to TypeNameAssertion if type is not importable
                    trace.add_entry(
                        position,
                        ass.TypeNameAssertion(
                            ref,
                            module_provider.get_module(typ.__module__).__name__,
                            typ.__qualname__,
                        ),
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
                            module_provider,
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
    def _is_type_importable(
        typ: type,
        module_provider: ex.ModuleProvider,
    ) -> bool:
        """Check if a type can be imported in the test context.

        Args:
            typ: The type to check
            module_provider: The module provider

        Returns:
            True if the type is importable, False otherwise
        """
        try:
            if not hasattr(typ, "__module__") or not hasattr(typ, "__qualname__"):
                return False

            # Try to get the module
            module_provider.get_module(typ.__module__)

            # Check if it's a built-in type that doesn't need importing
            if typ.__module__ == "builtins":
                return True

            # For user-defined types, verify they're accessible
            # by checking if we can resolve the qualified name
            module = module_provider.get_module(typ.__module__)
            parts = typ.__qualname__.split(".")
            obj = module
            for part in parts:
                if not hasattr(obj, part):
                    return False
                obj = getattr(obj, part)

            return obj is typ

        except Exception:  # noqa: BLE001
            # If anything goes wrong, the type is not safely importable
            return False

    @staticmethod
    def _should_ignore(field, attr_value):
        return (
            field.startswith("_")
            or field.endswith("__")
            or callable(attr_value)
            or isinstance(attr_value, ModuleType)
        )

    def _add_proxy_knowledge_assertions(  # noqa: C901
        self,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
        module_provider: ex.ModuleProvider,
    ) -> None:
        """Add hasattr assertions based on proxy knowledge.

        Args:
            test_case: The test case being executed
            result: The execution result containing proxy knowledge
            module_provider: The module provider for imports
        """
        # Use proxy knowledge stored in test case from test generation phase
        proxy_knowledge = test_case.proxy_knowledge

        if not proxy_knowledge:
            _LOGGER.debug("No proxy knowledge available (not stored from test generation)")
            return

        _LOGGER.debug("Using stored proxy knowledge: %d entries", len(proxy_knowledge))
        for key, node in proxy_knowledge.items():
            _LOGGER.debug("Key %s: children=%s", key, list(node.children.keys()))

        trace = result.assertion_trace

        # Build mapping: variable_reference -> proxy knowledge entries where it was used
        var_to_proxy: dict[vr.VariableReference, list[tuple[int, str]]] = {}
        _LOGGER.debug("Building variable-to-proxy mapping...")

        # Scan all parametrized statements to find where variables were used as arguments
        for statement in test_case.statements:
            if isinstance(statement, st.ParametrizedStatement):
                stmt_pos = statement.get_position()
                for param_name, var_ref in statement.args.items():
                    # Track that var_ref was used as param_name at stmt_pos
                    if var_ref not in var_to_proxy:
                        var_to_proxy[var_ref] = []
                    var_to_proxy[var_ref].append((stmt_pos, param_name))
                    _LOGGER.debug("Mapped var_ref to (%d, %s)", stmt_pos, param_name)

        _LOGGER.debug("Variable-to-proxy mapping has %d entries", len(var_to_proxy))

        # Now generate hasattr assertions for variables that have proxy knowledge
        for statement in test_case.statements:
            if not isinstance(statement, st.VariableCreatingStatement):
                continue
            if statement.ret_val.is_none_type():
                continue

            var_ref = statement.ret_val
            position = statement.get_position()

            # Check if this variable was used as an argument anywhere
            if var_ref in var_to_proxy:
                _LOGGER.debug(
                    "Position %d: variable was used in %s", position, var_to_proxy[var_ref]
                )
                self._generate_hasattr_from_usages(
                    var_ref, position, var_to_proxy[var_ref], proxy_knowledge, trace
                )

    def _generate_hasattr_from_usages(
        self,
        var_ref: vr.VariableReference,
        position: int,
        usages: list[tuple[int, str]],
        proxy_knowledge: dict,
        trace: at.AssertionTrace,
    ) -> None:
        """Generate hasattr assertions from variable usages.

        Args:
            var_ref: The variable reference
            position: The position where assertions are added
            usages: List of (usage_pos, param_name) tuples
            proxy_knowledge: The proxy knowledge mapping
            trace: The assertion trace
        """
        for usage_pos, param_name in usages:
            # Look up proxy knowledge for where this variable was used
            knowledge_key = (usage_pos, param_name)
            if knowledge_key in proxy_knowledge:
                node = proxy_knowledge[knowledge_key]
                _LOGGER.debug(
                    "Found proxy knowledge at %s, children: %s",
                    knowledge_key,
                    list(node.children.keys()),
                )
                # Generate hasattr assertions from children
                for attr_name in node.children:
                    if self._should_generate_hasattr(attr_name):
                        _LOGGER.debug("Generating hasattr(%s, '%s')", var_ref, attr_name)
                        trace.add_entry(
                            position,
                            ass.HasAttrAssertion(var_ref, attr_name),
                        )
            else:
                _LOGGER.debug("No proxy knowledge found for key %s", knowledge_key)

    @staticmethod
    def _should_generate_hasattr(attr_name: str) -> bool:
        """Check if we should generate hasattr assertion for this attribute.

        Args:
            attr_name: The attribute name

        Returns:
            True if we should generate the assertion
        """
        # Skip private/dunder attributes
        if attr_name.startswith("_") or attr_name.endswith("__"):
            return False
        # Skip common magic methods that don't represent domain attributes
        return attr_name not in {"__class__", "__dict__", "__module__", "__doc__"}


class RemoteAssertionVerificationObserver(ex.RemoteExecutionObserver):
    """This remote observer is used to check if assertions hold."""

    class RemoteAssertionExecutorLocalState(threading.local):
        """Local state for assertion executor."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.trace = at.AssertionVerificationTrace()

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

    def after_test_case_execution(  # noqa: D102
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ) -> None:
        result.assertion_verification_trace = self._state.trace

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
                self._state.trace.failed[statement.get_position()].add(0)
            else:
                self._state.trace.error[statement.get_position()].add(0)
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
                    self._state.trace.failed[statement.get_position()].add(idx)
                else:
                    self._state.trace.error[statement.get_position()].add(idx)
