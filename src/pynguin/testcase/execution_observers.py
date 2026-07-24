#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Contains execution observers to gather trace data, return types, etc."""

from __future__ import annotations

import abc
import contextlib
import copy
import inspect
import logging
import threading
from typing import TYPE_CHECKING, Any, cast

import libcst as cst

import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.typetracing as tt
from pynguin.analyses.typesystem import Instance, TupleType
from pynguin.assertion.assertion_to_ast import assertion_to_cst

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import TestCluster
    from pynguin.analyses.typesystem import ProperType
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.execution_result import ExecutionResult

_LOGGER = logging.getLogger(__name__)


class RemoteExecutionObserver(abc.ABC):
    """A remote observer that can be used to observe the execution of a test case.

    Important Note: If an observer is stateful, then this state must be encapsulated
    in a threading.local, i.e., be bound to a thread. Note that thread local data
    is initialized per thread, so there is no need to clear any pre-existing data
    (because there is none), as every thread gets its own instance.

    Methods in this class are not allowed to interact with the 'outside' because this
    class could be sent to a remote environment. The only thing that should leave an
    observer are results when they are written to the execution result in
    RemoteExecutionObserver::after_test_case_execution.

    You may interact with the 'outside' in
    ExecutionObserver::after_remote_test_case_execution.

    Note: Usage of threading.local may interfere with debugging tools, such as pydevd.
    In such a case, disable Cython by setting the following environment variable:
    PYDEVD_USE_CYTHON=NO

    For more details, look at some implementations, e.g., AssertionTraceObserver.
    """

    def __init__(self) -> None:  # noqa: B027
        """Initializes the remote observer."""

    @property
    def state(self) -> dict[str, Any]:
        """The state of the observer.

        Returns:
            The state of the observer
        """
        return {}

    @state.setter  # noqa: B027
    def state(self, state: dict[str, Any]) -> None:
        """Set the state of the observer.

        Args:
            state: The new state
        """

    @abc.abstractmethod
    def before_test_case_execution(self, test_case: tc.TestCase):
        """Called before test case execution.

        Args:
            test_case: The test cases that will be executed.
        """

    def before_statement_execution(
        self,
        statement: tc.Statement,
        node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
        namespace: dict[str, Any],
    ) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        """Called before a single statement is executed.

        Returns ``node`` unchanged by default; observers that need to rewrite the
        node before it is executed (e.g. to inject proxies) should override this
        and return the modified node. The (possibly modified) node returned here is
        what actually gets executed, so overriders must return a valid node.

        Args:
            statement: The statement that is about to be executed.
            node: The CST node that is about to be executed for this statement.
            namespace: The shared namespace the statement will execute in.

        Returns:
            The CST node to execute (``node`` unchanged by default).
        """
        return node

    def after_statement_execution(  # noqa: B027
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        """Called after a single statement is executed.

        No-op by default; observers that need per-statement observation should
        override this.

        Args:
            statement: The statement that was executed.
            executor: The executor that executed the statement.
            namespace: The shared namespace the statement executed in.
            exception: The exception raised by the statement, if any.
        """

    @abc.abstractmethod
    def after_test_case_execution(
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        """Called after test case execution.

        The call happens from the remote environment that executed the test case. You
        should override this method to extract information from the thread local storage
        to the execution result.

        Note: When a timeout occurs, then this method might not be called at all.

        Args:
            executor: The executor that executed the test case
            test_case: The test cases that was executed
            result: The execution result
        """

    def __getstate__(self) -> dict[str, Any]:
        return self.state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__init__()  # type: ignore[misc]
        self.state = state


class ExecutionObserver(abc.ABC):
    """An observer that can be used to observe the execution of a test case."""

    @property
    @abc.abstractmethod
    def remote_observer(self) -> RemoteExecutionObserver:
        """The remote observer.

        Returns:
            The remote observer
        """

    @abc.abstractmethod
    def before_remote_test_case_execution(self, test_case: tc.TestCase) -> None:
        """Called before test case execution from the main thread.

        Note: This method can be called with several test cases before the
        after_remote_test_case_execution method is called.

        Args:
            test_case: The test cases that will be executed.
        """

    @abc.abstractmethod
    def after_remote_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        """Called after test case execution from the main thread.

        Note: This method is always called, though the data you expect in the execution
        might not be there, if the execution of the test case timed out.
        You are not allowed to access thread local state here (due to how
        threading.local works, it isn't even possible ;)), but you can do some
        postprocessing with the data from the execution result here.

        Args:
            test_case: The test cases that was executed
            result: The execution result
        """


class RemoteAssertionExecutionObserver(RemoteExecutionObserver):
    """A remote observer which executes the assertions of statements.

    Executes each statement's assertions right after the statement, with
    checked-coverage instrumentation enabled (when the executor was configured
    for it via ``set_instrument(True)``), and records their trace positions
    via the instrumentation tracer so they can later be sliced.

    Enables slicing on the recorded data.

    Note: this observer must only be registered together with
    ``executor.set_instrument(True)``; otherwise the assertion code executes
    uninstrumented and ``ExecutionTracer.track_assertion_position`` will fail
    to find a boolean-jump instruction to record.
    """

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: not used
        """

    def after_statement_execution(
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        """Execute the statement's assertions, instrumented, and track them.

        Args:
            statement: The statement that was executed.
            executor: The executor that executed the statement.
            namespace: The shared namespace the statement executed in.
            exception: The exception raised by the statement, if any.
        """
        tracer = executor.subject_properties.instrumentation_tracer
        with tracer.temporarily_enable():
            if statement.has_only_exception_assertion():
                if exception is not None:
                    tracer.track_exception_assertion(statement)
                return
            if exception is not None:
                # The bound variable (if any) is undefined; assertions on it
                # cannot meaningfully hold, so skip them.
                return
            for assertion in statement.assertions:
                cst_node = assertion_to_cst(assertion)
                if cst_node is None:
                    # E.g. an ExceptionAssertion mixed in with other
                    # assertions; handled structurally elsewhere.
                    continue
                code_str = cst.Module(body=[cst_node]).code
                assertion_exception = executor.execute_source(code_str, namespace)
                if assertion_exception is not None:
                    # A failed/erroring assertion has no meaningful boolean
                    # jump to record; skip tracking its position.
                    continue
                tracer.track_assertion_position(assertion)

    def after_test_case_execution(
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        """Not used.

        Args:
            executor: Not used
            test_case: Not used
            result: Not used
        """


class RemoteReturnTypeObserver(RemoteExecutionObserver):
    """An observer which observes the runtime types seen during execution."""

    class RemoteReturnTypeLocalState(threading.local):
        """Encapsulate observed return types."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.return_type_trace: dict[int, type] = {}
            self.return_type_generic_args: dict[int, tuple[type, ...]] = {}
            self.position: int = 0

    def __init__(self):
        """Initializes the remote observer."""
        super().__init__()
        self._return_type_local_state = RemoteReturnTypeObserver.RemoteReturnTypeLocalState()

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return {
            "return_type_trace": self._return_type_local_state.return_type_trace,
            "return_type_generic_args": self._return_type_local_state.return_type_generic_args,
        }

    @state.setter
    def state(self, state: dict[str, Any]):  # noqa: RUF100
        self._return_type_local_state.return_type_trace = state["return_type_trace"]
        self._return_type_local_state.return_type_generic_args = state["return_type_generic_args"]

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        position = self._return_type_local_state.position
        self._return_type_local_state.position = position + 1

        if exception is not None:
            return

        bound_variable = statement.bound_variable
        if bound_variable is None or bound_variable not in namespace:
            return

        value = namespace[bound_variable]
        self._return_type_local_state.return_type_trace[position] = type(value)

        # TODO(fk) Hardcoded support for generics.
        # Try to guess generic arguments from elements.
        # `value` may be an arbitrary SUT object (or, once type-tracing's proxy
        # is installed, an ObjectProxy) whose `__len__`/`__iter__` misbehave;
        # guard the probing so a misbehaving object cannot abort the trace.
        with contextlib.suppress(Exception):
            if type(value) in {set, list} and len(value) > 0:
                self._return_type_local_state.return_type_generic_args[position] = (
                    type(next(iter(value))),
                )
            elif isinstance(value, dict) and len(value) > 0:
                first_item = next(iter(value.items()))
                self._return_type_local_state.return_type_generic_args[position] = (
                    type(first_item[0]),
                    type(first_item[1]),
                )
            elif type(value) is tuple:
                self._return_type_local_state.return_type_generic_args[position] = tuple(
                    type(v) for v in value
                )

    def after_test_case_execution(  # noqa: D102
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ):
        result.raw_return_types = dict(self._return_type_local_state.return_type_trace)
        result.raw_return_type_generic_args = dict(
            self._return_type_local_state.return_type_generic_args
        )


class ReturnTypeObserver(ExecutionObserver):
    """Observes the runtime types seen during execution.

    Updates the return types of the called function with the observed types.
    """

    def __init__(self, test_cluster: TestCluster):
        """Initializes the observer.

        Args:
            test_cluster: The test cluster that shall be updated
        """
        self._test_cluster = test_cluster
        self._remote_observer = RemoteReturnTypeObserver()

    @property
    def remote_observer(self) -> RemoteExecutionObserver:
        """The remote observer.

        Returns:
            The remote observer
        """
        return self._remote_observer

    def before_remote_test_case_execution(self, test_case: tc.TestCase) -> None:
        """Not used.

        Args:
            test_case: Not used
        """

    def after_remote_test_case_execution(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        # We store the raw types, so we still need to convert them to proper types.
        # This must be done outside the executing thread.
        for idx, raw_type in result.raw_return_types.items():
            if raw_type is type(NotImplemented):
                continue
            proper_type = self._test_cluster.type_system.convert_type_hint(raw_type)
            proper_type = self.__infer_known_generics(result, idx, proper_type)
            result.proper_return_type_trace[idx] = proper_type
            statement = test_case.get_statement(idx)
            call_acc = getattr(statement, "accessible", None)
            if isinstance(call_acc, gao.GenericCallableAccessibleObject):
                self._test_cluster.update_return_type(call_acc, proper_type)

    def __infer_known_generics(
        self, result: ExecutionResult, idx: int, proper: ProperType
    ) -> ProperType:
        if idx not in result.raw_return_type_generic_args:
            return proper

        if isinstance(proper, TupleType):
            return TupleType(
                tuple(
                    self._test_cluster.type_system.convert_type_hint(t)
                    for t in result.raw_return_type_generic_args[idx]
                )
            )
        if isinstance(proper, Instance) and proper.type.raw_type in {list, set, dict}:
            return Instance(
                proper.type,
                tuple(
                    self._test_cluster.type_system.convert_type_hint(t)
                    for t in result.raw_return_type_generic_args[idx]
                ),
            )
        return proper


_UNRESOLVED = object()


def _find_call(
    node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
) -> cst.Call | None:
    """Return the top-level call of a statement node, if it wraps one.

    Covers ``var_0 = module_.f(...)``, ``var_0 = var_1.m(...)`` and demoted
    ``module_.f(...)`` expression statements.

    Args:
        node: The statement's CST node.

    Returns:
        The wrapped ``cst.Call``, or ``None`` if the node does not wrap one.
    """
    if not isinstance(node, cst.SimpleStatementLine) or not node.body:
        return None
    small = node.body[0]
    if not isinstance(small, cst.Assign | cst.AnnAssign | cst.Expr):
        return None
    value = small.value
    if isinstance(value, cst.Call):
        return value
    return None


def _map_args_to_params(
    call: cst.Call, signature: inspect.Signature
) -> list[tuple[int, str, inspect.Parameter]]:
    """Map each call argument to the parameter it binds.

    Keyword args resolve by name; positional args consume the signature's
    positional parameters (``POSITIONAL_ONLY`` / ``POSITIONAL_OR_KEYWORD``,
    skipping a leading ``self``) in declaration order. ``*args`` / ``**kwargs``
    expansions and unresolvable keyword args are skipped.

    Args:
        call: The call whose arguments to map.
        signature: The callable's inferred signature.

    Returns:
        A list of ``(arg_index, param_name, parameter)`` tuples.
    """
    parameters = signature.parameters
    positional = [
        param
        for param in parameters.values()
        if param.kind
        in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        and param.name != "self"
    ]
    result: list[tuple[int, str, inspect.Parameter]] = []
    pos_index = 0
    for index, arg in enumerate(call.args):
        if arg.star:
            # *args / **kwargs expansion; do not proxy.
            continue
        if arg.keyword is not None:
            name = arg.keyword.value
            param = parameters.get(name)
            if param is None:
                continue
            result.append((index, name, param))
        else:
            if pos_index >= len(positional):
                continue
            param = positional[pos_index]
            pos_index += 1
            result.append((index, param.name, param))
    return result


def _resolve_arg_value(arg: cst.Arg, namespace: dict[str, Any], renderer: cst.Module) -> Any:
    """Resolve the runtime value of a call argument in the namespace.

    A ``cst.Name`` argument is looked up directly; any other (inline literal)
    argument is evaluated against the namespace. Generated literals are
    side-effect-free and the instrumentation tracer is disabled here.

    Args:
        arg: The call argument.
        namespace: The shared execution namespace.
        renderer: A ``cst.Module`` used to render nodes to source.

    Returns:
        The resolved value, or ``_UNRESOLVED`` if it could not be obtained.
    """
    value = arg.value
    if isinstance(value, cst.Name):
        try:
            return namespace[value.value]
        except KeyError:
            return _UNRESOLVED
    try:
        return eval(renderer.code_for_node(value), namespace)  # noqa: S307
    except BaseException:  # noqa: BLE001
        return _UNRESOLVED


class RemoteTypeTracingObserver(RemoteExecutionObserver):
    """A remote observer used for type tracing."""

    class RemoteTypeTracingLocalState(threading.local):
        """Thread local data for type tracing."""

        def __init__(self):  # noqa: D107
            super().__init__()
            # Active proxies per statement position and argument name.
            self.proxies: dict[tuple[int, str], tt.ObjectProxy] = {}
            # Position counter, incremented once per statement. A fresh thread per
            # test case guarantees this starts at 0 and, because execution stops at
            # the first exception, equals the statement index.
            self.position: int = 0
            # Temp proxy names injected for the current statement, cleaned up in
            # after_statement_execution so proxies do not leak into later statements.
            self.current_temp_names: list[str] = []

    def __init__(self):
        """Initializes the remote observer."""
        super().__init__()
        self._local_state = RemoteTypeTracingObserver.RemoteTypeTracingLocalState()

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return dict(  # noqa: C408
            proxies=self._local_state.proxies,
        )

    @state.setter
    def state(self, state: dict[str, Any]) -> None:
        self._local_state.proxies = state["proxies"]

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def before_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        node: cst.SimpleStatementLine | cst.BaseCompoundStatement,
        namespace: dict[str, Any],
    ) -> cst.SimpleStatementLine | cst.BaseCompoundStatement:
        position = self._local_state.position
        self._local_state.position = position + 1
        self._local_state.current_temp_names = []
        accessible = statement.accessible
        if not isinstance(accessible, gao.GenericCallableAccessibleObject):
            return node
        call = _find_call(node)
        if call is None:
            return node
        signature = accessible.inferred_signature.signature
        mapping = _map_args_to_params(call, signature)
        if not mapping:
            return node
        new_args = list(call.args)
        renderer = cst.Module(body=[])
        changed = False
        for index, name, param in mapping:
            arg = call.args[index]
            value = _resolve_arg_value(arg, namespace, renderer)
            if value is _UNRESOLVED:
                continue
            proxy = tt.ObjectProxy(
                value,
                usage_trace=tt.UsageTraceNode(name=name),
                is_kwargs=param.kind == inspect.Parameter.VAR_KEYWORD,
            )
            temp = f"_pyn_proxy_{position}_{index}"
            namespace[temp] = proxy
            self._local_state.current_temp_names.append(temp)
            self._local_state.proxies[position, name] = proxy
            new_args[index] = arg.with_changes(value=cst.Name(temp))
            changed = True
        if not changed:
            return node
        return cast(
            "cst.SimpleStatementLine | cst.BaseCompoundStatement",
            node.deep_replace(call, call.with_changes(args=new_args)),
        )

    def after_statement_execution(  # noqa: D102
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        for temp in self._local_state.current_temp_names:
            namespace.pop(temp, None)
        self._local_state.current_temp_names = []
        if exception is None and statement.bound_variable is not None:
            bound_variable = statement.bound_variable
            if bound_variable in namespace:
                # Unwrap a possibly-proxied return value so proxies do not leak into
                # later statements. (Containers of proxies still leak.)
                namespace[bound_variable] = tt.unwrap(namespace[bound_variable])

    def after_test_case_execution(  # noqa: D102
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        for (stmt_pos, arg_name), proxy in self._local_state.proxies.items():
            result.proxy_knowledge[stmt_pos, arg_name] = copy.deepcopy(
                tt.UsageTraceNode.from_proxy(proxy)
            )


class TypeTracingObserver(ExecutionObserver):
    """An execution observer used for type tracing.

    It wraps parameters in proxies in order to make better guesses on their type.
    """

    def __init__(self, cluster: TestCluster):
        """Initializes the observer.

        Args:
            cluster: The test cluster that shall be updated by the observer
        """
        self._cluster = cluster
        self._remote_observer = RemoteTypeTracingObserver()

    @property
    def remote_observer(self) -> RemoteTypeTracingObserver:  # noqa: D102
        return self._remote_observer

    def before_remote_test_case_execution(self, test_case: tc.TestCase) -> None:
        """Not used.

        Args:
            test_case: Not used
        """

    def after_remote_test_case_execution(  # noqa: D102
        self, test_case: tc.TestCase, result: ExecutionResult
    ) -> None:
        for (stmt_pos, arg_name), knowledge in result.proxy_knowledge.items():
            statement = test_case.get_statement(stmt_pos)
            call_acc = getattr(statement, "accessible", None)
            if isinstance(call_acc, gao.GenericCallableAccessibleObject):
                self._cluster.update_parameter_knowledge(
                    call_acc,
                    arg_name,
                    knowledge,
                )
