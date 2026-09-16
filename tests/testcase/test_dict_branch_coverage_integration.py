#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration test for key-dependent branch coverage on dictionaries and kwargs."""

import importlib

import libcst as cst

import pynguin.configuration as config
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.testcase import Statement, TestCase
from tests.fixtures.branchcoverage import dict_branch


def _stmt(
    code: str, bound_variable: str | None = None, bound_type: type | None = None
) -> Statement:
    node = cst.parse_module(code if code.endswith("\n") else code + "\n").body[0]
    return Statement(node=node, bound_variable=bound_variable, bound_type=bound_type)


def test_dict_branch_auxiliary_predicate_isolation(subject_properties: SubjectProperties):
    module_name = "tests.fixtures.branchcoverage.dict_branch"
    with (
        install_import_hook(
            module_name,
            subject_properties,
            coverage_metrics=(config.CoverageMetric.BRANCH, config.CoverageMetric.LINE),
        ),
        subject_properties.instrumentation_tracer,
    ):
        importlib.reload(dict_branch)

    # Auxiliary predicates should be registered with is_auxiliary=True
    aux_predicates = [
        pid for pid, meta in subject_properties.existing_predicates.items() if meta.is_auxiliary
    ]
    assert len(aux_predicates) > 0

    # Ensure auxiliary predicates are excluded from coverage_predicates goals
    for pid in aux_predicates:
        assert pid not in subject_properties.coverage_predicates


def test_dict_branch_execution_and_collection_trace(subject_properties: SubjectProperties):
    module_name = "tests.fixtures.branchcoverage.dict_branch"
    config.configuration.module_name = module_name
    with (
        install_import_hook(
            module_name,
            subject_properties,
            coverage_metrics=(config.CoverageMetric.BRANCH, config.CoverageMetric.LINE),
        ),
        subject_properties.instrumentation_tracer,
    ):
        importlib.reload(dict_branch)

    config.configuration.test_creation.track_collection_accesses = True
    executor = TestCaseExecutor(subject_properties)

    test_case = TestCase()
    test_case.add_statement(_stmt("var_0 = {}\n", bound_variable="var_0", bound_type=dict))
    test_case.add_statement(
        _stmt(
            "var_1 = check_dict(var_0)\n",
            bound_variable="var_1",
            bound_type=int,
        )
    )

    result = executor.execute(test_case)

    # Statement 1 raised KeyError because 'abcd' is missing from var_0
    assert 1 in result.exceptions
    assert isinstance(result.exceptions[1], KeyError)
    assert result.exceptions[1].args[0] == "abcd"

    # Collection trace should record 'abcd' as missing key for statement 0
    assert 0 in result.collection_trace
    assert "abcd" in result.collection_trace[0].missing_keys


def test_kwargs_branch_execution_and_collection_trace(subject_properties: SubjectProperties):
    module_name = "tests.fixtures.branchcoverage.dict_branch"
    config.configuration.module_name = module_name
    with (
        install_import_hook(
            module_name,
            subject_properties,
            coverage_metrics=(config.CoverageMetric.BRANCH, config.CoverageMetric.LINE),
        ),
        subject_properties.instrumentation_tracer,
    ):
        importlib.reload(dict_branch)

    config.configuration.test_creation.track_collection_accesses = True
    executor = TestCaseExecutor(subject_properties)

    test_case = TestCase()
    test_case.add_statement(_stmt("var_0 = {}\n", bound_variable="var_0", bound_type=dict))
    test_case.add_statement(
        _stmt(
            "var_1 = check_kwargs(**var_0)\n",
            bound_variable="var_1",
            bound_type=int,
        )
    )

    result = executor.execute(test_case)

    # Statement 1 raised KeyError because 'secret' is missing from kwargs
    assert 1 in result.exceptions
    assert isinstance(result.exceptions[1], KeyError)
    assert result.exceptions[1].args[0] == "secret"

    # In kwargs, CPython copied var_0 into a plain dict, but our unhandled KeyError handler
    # in collection_tracker associates 'secret' back to var_0!
    assert 0 in result.collection_trace
    assert "secret" in result.collection_trace[0].missing_keys
