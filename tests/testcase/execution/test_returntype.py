#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for return-type tracing (point 7 of the re-enablement plan).

Covers ``RemoteReturnTypeObserver``'s per-statement ``after_statement_execution``
hook and the downstream ``ReturnTypeObserver`` that turns the raw traces into
proper types and feeds them into ``TestCluster.update_return_type``.

Type tracing / proxy knowledge (point 8, ``RemoteTypeTracingObserver``) is
intentionally out of scope; see ``tests/testcase/execution/test_typetracing.py``
(still ignored) for those.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import NoneType, UnionType
from pynguin.testcase.execution import ReturnTypeObserver, TestCaseExecutor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.naming import get_module_alias
from tests.testcase._builders import assign, make_test_case, stmt

if TYPE_CHECKING:
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.instrumentation.tracer import SubjectProperties

MODULE_RETURN_TYPES = "tests.fixtures.type_tracing.return_types"
MODULE_GUESS_PARAMS = "tests.fixtures.type_tracing.guess_params"


def _accessible_for(test_cluster: ModuleTestCluster, function_name: str) -> GenericFunction:
    """Find the ``GenericFunction`` accessible object for *function_name*."""
    for acc in test_cluster.accessible_objects_under_test:
        if isinstance(acc, GenericFunction) and acc.function_name == function_name:
            return acc
    raise AssertionError(f"No accessible found for {function_name}")


def _call_statement(
    module_name: str, function_name: str, bound_variable: str
) -> tuple[tc.Statement, ModuleTestCluster]:
    """Build a statement calling *function_name* of *module_name*, bound to a variable."""
    test_cluster = generate_test_cluster(module_name)
    acc = _accessible_for(test_cluster, function_name)
    alias = get_module_alias(module_name)
    node = cst.parse_statement(f"{bound_variable} = {alias}.{function_name}()")
    statement = tc.Statement(node=node, bound_variable=bound_variable, accessible=acc)
    return statement, test_cluster


@pytest.mark.parametrize(
    ("test_func", "return_type"),
    [
        ("return_tuple", tuple[int, int]),
        ("return_list", list[int]),
        ("return_dict", dict[str, int]),
        ("return_set", set[str]),
        ("return_int", int),
        ("return_none", type(None)),
    ],
)
def test_type_reconstruction(
    test_func: str, return_type: type, subject_properties: SubjectProperties
) -> None:
    """The proper type (incl. reconstructed generics) is recorded for each call."""
    config.configuration.module_name = MODULE_RETURN_TYPES
    statement, test_cluster = _call_statement(MODULE_RETURN_TYPES, test_func, "var_0")
    test_case = make_test_case(statement)

    executor = TestCaseExecutor(subject_properties)
    observer = ReturnTypeObserver(test_cluster)
    executor.add_observer(observer)
    result = executor.execute(test_case)

    assert not result.has_test_exceptions()
    assert result.proper_return_type_trace[0] == test_cluster.type_system.convert_type_hint(
        return_type
    )


def test_statement_without_bound_variable_records_nothing_but_advances_position(
    subject_properties: SubjectProperties,
) -> None:
    """A statement with no ``bound_variable`` is skipped, but the position still advances."""
    config.configuration.module_name = MODULE_RETURN_TYPES
    call_statement, test_cluster = _call_statement(MODULE_RETURN_TYPES, "return_int", "int_0")
    test_case = make_test_case(
        call_statement,  # position 0: bound, recorded
        stmt("int_0"),  # position 1: bare expression, bound_variable=None, not recorded
        assign("int_1", "int_0 + 1", bound_type=int),  # position 2: bound, recorded
    )

    executor = TestCaseExecutor(subject_properties)
    observer = ReturnTypeObserver(test_cluster)
    executor.add_observer(observer)
    result = executor.execute(test_case)

    assert not result.has_test_exceptions()
    assert result.raw_return_types.keys() == {0, 2}
    assert result.raw_return_types[0] is int
    assert result.raw_return_types[2] is int


def test_update_return_type_is_driven(subject_properties: SubjectProperties) -> None:
    """Executing a call statement updates the accessible's inferred return type."""
    config.configuration.module_name = MODULE_GUESS_PARAMS
    test_cluster = generate_test_cluster(MODULE_GUESS_PARAMS)
    acc = _accessible_for(test_cluster, "foo")
    alias = get_module_alias(MODULE_GUESS_PARAMS)
    test_case = make_test_case(
        assign("int_0", "0", bound_type=int),
        assign("int_1", "0", bound_type=int),
        assign("int_2", "0", bound_type=int),
        tc.Statement(
            node=cst.parse_statement(f"var_0 = {alias}.foo(int_0, int_1, int_2)"),
            bound_variable="var_0",
            accessible=acc,
        ),
    )

    executor = TestCaseExecutor(subject_properties)
    observer = ReturnTypeObserver(test_cluster)
    executor.add_observer(observer)
    result = executor.execute(test_case)

    assert not result.has_test_exceptions()
    # foo() has no return statement, so it implicitly returns None.
    assert acc.inferred_signature.return_type == UnionType((NoneType(),))
