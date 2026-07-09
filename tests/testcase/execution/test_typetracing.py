#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for type tracing / proxy knowledge (DISABLED_SUBSYSTEMS point 8).

These drive the libcst test-case representation: statements are built directly as
``tc.Statement`` objects wrapping ``cst`` nodes. The type-tracing observer wraps a
call's arguments in ``ObjectProxy`` objects (one per argument occurrence, keyed by
statement position + parameter name), records the usage trace into
``result.proxy_knowledge``, unwraps the return value afterward, and the downstream
``TypeTracingObserver`` feeds that knowledge into
``ModuleTestCluster.update_parameter_knowledge``.

Return-type tracing (point 7) is intentionally out of scope here.
"""

from __future__ import annotations

import inspect
from itertools import starmap
from typing import TYPE_CHECKING, cast

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.utils.typetracing as tt
from pynguin.analyses.module import generate_test_cluster
from pynguin.testcase.execution import (
    RemoteTypeTracingObserver,
    TestCaseExecutor,
    TypeTracingObserver,
    TypeTracingTestCaseExecutor,
    _find_call,  # noqa: PLC2701
    _map_args_to_params,  # noqa: PLC2701
)
from pynguin.utils.naming import get_module_alias

if TYPE_CHECKING:
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.utils.generic.genericaccessibleobject import (
        GenericCallableAccessibleObject,
    )


GUESS_PARAMS_MODULE = "tests.fixtures.type_tracing.guess_params"


def _accessible_for(test_cluster, name: str) -> GenericCallableAccessibleObject:
    """Return the callable accessible object for the function called *name*."""
    for accessible in test_cluster.accessible_objects_under_test:
        callable_ = getattr(accessible, "callable", None)
        if callable_ is not None and getattr(callable_, "__name__", None) == name:
            return cast("GenericCallableAccessibleObject", accessible)
    raise AssertionError(f"No accessible object under test named {name!r}")


@pytest.fixture
def guess_params_cluster_and_case():
    """Build a cluster + test case calling ``foo(a=int_0, b=int_0, c=int_0)``.

    ``foo`` uses ``a`` via ``3 * a`` (``__rmul__``), ``b`` via ``4 + b``
    (``__radd__``), and ``c`` via ``c / 5`` (``__truediv__``).
    """
    config.configuration.module_name = GUESS_PARAMS_MODULE
    test_cluster = generate_test_cluster(GUESS_PARAMS_MODULE)
    acc = _accessible_for(test_cluster, "foo")
    alias = get_module_alias(GUESS_PARAMS_MODULE)
    test_case = tc.TestCase()
    test_case.add_statement(
        tc.Statement(
            node=cst.parse_statement("int_0 = 0"),
            bound_variable="int_0",
            bound_type=int,
        )
    )
    test_case.add_statement(
        tc.Statement(
            node=cst.parse_statement(f"var_0 = {alias}.foo(a=int_0, b=int_0, c=int_0)"),
            bound_variable="var_0",
            accessible=acc,
        )
    )
    return test_cluster, test_case


# --------------------------------------------------------------------------- #
# Pure helpers: _find_call / _map_args_to_params
# --------------------------------------------------------------------------- #
def _call_of(code: str) -> cst.Call:
    call = _find_call(cst.parse_statement(code))
    assert call is not None
    return call


def test_find_call_assign():
    assert _find_call(cst.parse_statement("x = f(1)")) is not None


def test_find_call_expr():
    assert _find_call(cst.parse_statement("f(1)")) is not None


def test_find_call_method_receiver():
    assert _find_call(cst.parse_statement("x = obj.m(1)")) is not None


def test_find_call_no_call():
    assert _find_call(cst.parse_statement("x = 1 + 2")) is None


def _signature(**kinds: inspect._ParameterKind) -> inspect.Signature:
    return inspect.Signature(parameters=list(starmap(inspect.Parameter, kinds.items())))


def test_map_args_keyword():
    signature = _signature(
        a=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        b=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        c=inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    mapping = _map_args_to_params(_call_of("x = f(a=1, b=2, c=3)"), signature)
    assert [(idx, name) for idx, name, _ in mapping] == [(0, "a"), (1, "b"), (2, "c")]


def test_map_args_positional_only():
    signature = _signature(
        a=inspect.Parameter.POSITIONAL_ONLY,
        b=inspect.Parameter.POSITIONAL_ONLY,
    )
    mapping = _map_args_to_params(_call_of("x = f(1, 2)"), signature)
    assert [(idx, name) for idx, name, _ in mapping] == [(0, "a"), (1, "b")]


def test_map_args_skips_self_for_positional():
    signature = _signature(
        self=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        a=inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    mapping = _map_args_to_params(_call_of("x = obj.m(1)"), signature)
    assert [(idx, name) for idx, name, _ in mapping] == [(0, "a")]


def test_map_args_unknown_keyword_skipped():
    signature = _signature(a=inspect.Parameter.POSITIONAL_OR_KEYWORD)
    mapping = _map_args_to_params(_call_of("x = f(a=1, zzz=2)"), signature)
    assert [(idx, name) for idx, name, _ in mapping] == [(0, "a")]


def test_map_args_star_skipped():
    signature = _signature(a=inspect.Parameter.POSITIONAL_OR_KEYWORD)
    mapping = _map_args_to_params(_call_of("x = f(*args, a=1)"), signature)
    assert [(idx, name) for idx, name, _ in mapping] == [(1, "a")]


# --------------------------------------------------------------------------- #
# Observer behaviour
# --------------------------------------------------------------------------- #
def test_type_tracing_observer_separate_proxies_for_args(
    guess_params_cluster_and_case, subject_properties: SubjectProperties
):
    """Each argument occurrence gets its own proxy; usage is recorded per name."""
    test_cluster, test_case = guess_params_cluster_and_case
    executor = TestCaseExecutor(subject_properties)
    executor.add_observer(TypeTracingObserver(test_cluster))
    result = executor.execute(test_case)
    assert set(result.proxy_knowledge[1, "a"].children.keys()) == {"__rmul__"}
    assert set(result.proxy_knowledge[1, "b"].children.keys()) == {"__radd__"}
    assert set(result.proxy_knowledge[1, "c"].children.keys()) == {"__truediv__"}


def test_type_tracing_observer_literal_argument(subject_properties: SubjectProperties):
    """Inline-literal arguments are proxied too (eval path)."""
    config.configuration.module_name = GUESS_PARAMS_MODULE
    test_cluster = generate_test_cluster(GUESS_PARAMS_MODULE)
    acc = _accessible_for(test_cluster, "foo")
    alias = get_module_alias(GUESS_PARAMS_MODULE)
    test_case = tc.TestCase()
    test_case.add_statement(
        tc.Statement(
            node=cst.parse_statement(f"var_0 = {alias}.foo(a=3, b=4, c=5)"),
            bound_variable="var_0",
            accessible=acc,
        )
    )
    executor = TestCaseExecutor(subject_properties)
    executor.add_observer(TypeTracingObserver(test_cluster))
    result = executor.execute(test_case)
    assert set(result.proxy_knowledge[0, "a"].children.keys()) == {"__rmul__"}


def test_type_tracing_observer_unwraps_and_cleans_up(subject_properties: SubjectProperties):
    """After execution no proxy leaks: bound var unwrapped, temp names gone."""
    config.configuration.module_name = GUESS_PARAMS_MODULE
    test_cluster = generate_test_cluster(GUESS_PARAMS_MODULE)
    acc = _accessible_for(test_cluster, "identity")
    alias = get_module_alias(GUESS_PARAMS_MODULE)
    test_case = tc.TestCase()
    test_case.add_statement(
        tc.Statement(node=cst.parse_statement("int_0 = 7"), bound_variable="int_0", bound_type=int)
    )
    test_case.add_statement(
        tc.Statement(
            node=cst.parse_statement(f"var_0 = {alias}.identity(a=int_0)"),
            bound_variable="var_0",
            accessible=acc,
        )
    )

    observer = TypeTracingObserver(test_cluster)
    remote = observer.remote_observer
    original_after = remote.after_statement_execution
    captured: dict[str, object] = {}

    def _spy(statement, executor, namespace, exception):
        original_after(statement, executor, namespace, exception)
        captured.clear()
        captured.update(namespace)

    remote.after_statement_execution = _spy  # type: ignore[method-assign]

    executor = TestCaseExecutor(subject_properties)
    executor.add_observer(observer)
    executor.execute(test_case)

    assert not any(key.startswith("_pyn_proxy_") for key in captured)
    assert not isinstance(captured.get("var_0"), tt.ObjectProxy)
    assert not isinstance(captured.get("int_0"), tt.ObjectProxy)
    assert captured.get("var_0") == 7
    assert captured.get("int_0") == 7


def test_type_tracing_test_case_executor_integration(
    guess_params_cluster_and_case, subject_properties: SubjectProperties
):
    """End-to-end: usage trace flows into the cluster's inferred signature."""
    test_cluster, test_case = guess_params_cluster_and_case
    executor = TestCaseExecutor(subject_properties)
    t_executor = TypeTracingTestCaseExecutor(executor, test_cluster)
    t_executor.execute(test_case)
    acc = _accessible_for(test_cluster, "foo")
    assert "__rmul__" in acc.inferred_signature.usage_trace["a"].children
    # type_checks are only recorded under shim_isinstance (second execution).
    assert int in acc.inferred_signature.usage_trace["a"].type_checks


def test_type_tracing_test_case_executor_probability_zero(
    guess_params_cluster_and_case, subject_properties: SubjectProperties
):
    """With probability 0.0 nothing is recorded."""
    test_cluster, test_case = guess_params_cluster_and_case
    executor = TestCaseExecutor(subject_properties)
    t_executor = TypeTracingTestCaseExecutor(executor, test_cluster, 0.0)
    t_executor.execute(test_case)
    acc = _accessible_for(test_cluster, "foo")
    assert "__rmul__" not in acc.inferred_signature.usage_trace["a"].children
    assert int not in acc.inferred_signature.usage_trace["a"].type_checks


def test_before_hook_default_returns_node_unchanged():
    """A non-call statement is returned unchanged by the before-hook (contract)."""
    observer = RemoteTypeTracingObserver()
    node = cst.parse_statement("var_0 = 1")
    statement = tc.Statement(node=node, bound_variable="var_0", bound_type=int)
    assert observer.before_statement_execution(statement, node, {}) is node
