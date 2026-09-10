#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for tuple deconstruction and execution of deconstructed elements."""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.typesystem import Instance
from pynguin.ga.stoppingcondition import MaxStatementExecutionsStoppingCondition
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction, GenericMethod

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pynguin.instrumentation.tracer import SubjectProperties

MODULE_TUPLE = "tests.fixtures.cluster.tuple_return"


@contextlib.contextmanager
def _executor_for(
    module_name: str, subject_properties: SubjectProperties
) -> Iterator[TestCaseExecutor]:
    config.configuration.module_name = module_name
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        yield TestCaseExecutor(subject_properties)


def test_tuple_deconstruction_and_execution_integration(
    subject_properties: SubjectProperties,
) -> None:
    """Tests end-to-end tuple deconstruction and execution."""
    config.configuration.module_name = MODULE_TUPLE
    cluster = generate_test_cluster(MODULE_TUPLE)

    give_me_a_tuple = next(
        acc
        for acc in cluster.accessible_objects_under_test
        if isinstance(acc, GenericFunction) and acc.function_name == "give_me_a_tuple"
    )
    use_bar = next(
        acc
        for acc in cluster.accessible_objects_under_test
        if isinstance(acc, GenericFunction) and acc.function_name == "use_bar"
    )
    get_val = next(
        acc
        for acc in cluster.accessible_objects_under_test
        if isinstance(acc, GenericMethod) and acc.method_name == "get_val"
    )

    # Verify that give_me_a_tuple is registered as a generator for Foo and Bar
    foo_type_info = cluster.type_system.find_type_info(f"{MODULE_TUPLE}.Foo")
    bar_type_info = cluster.type_system.find_type_info(f"{MODULE_TUPLE}.Bar")
    assert foo_type_info is not None
    assert bar_type_info is not None

    foo_proper = Instance(foo_type_info)
    bar_proper = Instance(bar_type_info)
    assert give_me_a_tuple in cluster.get_generators_for(foo_proper)
    assert give_me_a_tuple in cluster.get_generators_for(bar_proper)

    factory = tf.TestFactory(cluster)
    test_case = tc.TestCase()

    # Emit give_me_a_tuple
    pos = factory.append_generic_accessible(test_case, give_me_a_tuple)
    assert pos == 0
    # Must have deconstructed: var_0 (tuple), var_1 (Foo), var_2 (Bar)
    assert test_case.size() == 3
    assert test_case.get_statement(0).bound_variable == "var_0"
    assert test_case.get_statement(1).bound_variable == "var_1"
    assert test_case.get_statement(2).bound_variable == "var_2"

    # Now append get_val (method on Foo): should use var_1 as receiver
    pos_method = factory.append_generic_accessible(test_case, get_val)
    assert pos_method >= 3
    assert "var_1.get_val()" in test_case.to_code()

    # Now append use_bar: should pass var_2 as argument
    pos_use_bar = factory.append_generic_accessible(test_case, use_bar)
    assert pos_use_bar >= 4
    assert "var_2" in test_case.to_code()

    condition = MaxStatementExecutionsStoppingCondition(10_000)
    with _executor_for(MODULE_TUPLE, subject_properties) as executor:
        executor.add_observer(condition)
        result = executor.execute(test_case)

    assert not result.has_test_exceptions()
    assert result.num_executed_statements == test_case.size()
    assert condition.current_value() == test_case.size()
