#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for generator statement generation and execution."""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.analyses.module import generate_test_cluster
from pynguin.ga.stoppingcondition import MaxStatementExecutionsStoppingCondition
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction, GenericMethod

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pynguin.instrumentation.tracer import SubjectProperties

MODULE_ACCESSIBLE = "tests.fixtures.accessibles.accessible"


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


def test_generator_function_generation_and_execution_integration(
    subject_properties: SubjectProperties,
) -> None:
    """Tests end-to-end generator function emission and execution."""
    config.configuration.module_name = MODULE_ACCESSIBLE
    cluster = generate_test_cluster(MODULE_ACCESSIBLE)

    gen_func = next(
        acc
        for acc in cluster.accessible_objects_under_test
        if isinstance(acc, GenericFunction) and acc.function_name == "simple_generator_function"
    )
    assert gen_func.is_generator

    factory = tf.TestFactory(cluster)
    test_case = tc.TestCase()
    pos = factory.append_generic_accessible(test_case, gen_func)
    assert pos >= 0

    # The factory should have emitted the generator creation followed by a next() call
    code = test_case.to_code()
    assert "simple_generator_function(" in code
    assert "next(" in code

    condition = MaxStatementExecutionsStoppingCondition(10_000)
    with _executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        executor.add_observer(condition)
        result = executor.execute(test_case)

    assert not result.has_test_exceptions()
    assert result.num_executed_statements == test_case.size()
    assert condition.current_value() == test_case.size()


def test_generator_method_generation_and_execution_integration(
    subject_properties: SubjectProperties,
) -> None:
    """Tests end-to-end generator method emission and execution."""
    config.configuration.module_name = MODULE_ACCESSIBLE
    cluster = generate_test_cluster(MODULE_ACCESSIBLE)

    gen_method = next(
        acc
        for acc in cluster.accessible_objects_under_test
        if isinstance(acc, GenericMethod) and acc.method_name == "simple_generator_method"
    )
    assert gen_method.is_generator

    factory = tf.TestFactory(cluster)
    test_case = tc.TestCase()
    pos = factory.append_generic_accessible(test_case, gen_method)
    assert pos >= 0

    code = test_case.to_code()
    assert "simple_generator_method(" in code
    assert "next(" in code

    condition = MaxStatementExecutionsStoppingCondition(10_000)
    with _executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        executor.add_observer(condition)
        result = executor.execute(test_case)

    assert not result.has_test_exceptions()
    assert result.num_executed_statements == test_case.size()
    assert condition.current_value() == test_case.size()
