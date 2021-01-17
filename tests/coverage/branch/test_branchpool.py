#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
from unittest.mock import MagicMock

import pytest
from bytecode import BasicBlock, Instr

from pynguin.coverage.branch.branchcoveragegoal import Branch
from pynguin.coverage.branch.branchpool import INSTANCE
from pynguin.instrumentation.branch_distance import BranchDistanceInstrumentation
from pynguin.testcase.execution.executiontracer import ExecutionTracer


@pytest.fixture
def branch_pool():
    INSTANCE.clear()
    return INSTANCE


@pytest.fixture
def basic_block():
    return MagicMock(BasicBlock)


@pytest.fixture
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


@pytest.fixture
def tracer_mock():
    tracer = MagicMock(ExecutionTracer)
    tracer.register_code_object.side_effect = range(100)
    tracer.register_predicate.side_effect = range(100)
    return tracer


def test_register_branchless_method(branch_pool):
    branch_pool.register_branchless_function("foo", 42, 23)
    assert branch_pool.branchless_functions == {"foo"}
    assert branch_pool.is_branchless_function("foo")
    assert branch_pool.get_num_branchless_functions() == 1
    assert branch_pool.get_branchless_function_line_number("foo") == 42
    assert branch_pool.get_branchless_function_code_object_id("foo") == 23


def test_register_branch(branch_pool, basic_block):
    branch_pool.register_branch(basic_block, 0, 1, 2, MagicMock(Instr))
    assert branch_pool.is_known_as_branch(basic_block)
    assert branch_pool.get_actual_branch_id_for_normal_branch(basic_block) == 1
    assert isinstance(branch_pool.get_branch_for_block(basic_block), Branch)
    assert len(branch_pool.all_branches) == 1
    assert branch_pool.branch_counter == 1


def test_register_branch_2(branch_pool, basic_block):
    branch_pool.register_branch(MagicMock(BasicBlock), 1, 2, 3, MagicMock(Instr))
    branch_pool.register_branch(basic_block, 0, 1, 2, MagicMock(Instr))
    assert branch_pool.get_actual_branch_id_for_normal_branch(basic_block) == 2


def test_register_branch_twice(branch_pool, basic_block):
    instr = MagicMock(Instr)
    branch_pool.register_branch(basic_block, 0, 1, 2, instr)
    with pytest.raises(ValueError):
        branch_pool.register_branch(basic_block, 0, 1, 2, instr)


def test_get_branchless_function_line_number_non_existing(branch_pool):
    with pytest.raises(ValueError):
        branch_pool.get_branchless_function_line_number("bar")


def test_get_branchless_function_code_object_id_non_existing(branch_pool):
    with pytest.raises(ValueError):
        branch_pool.get_branchless_function_code_object_id("bar")


def test_get_actual_branch_id_for_normal_branch_non_existing(branch_pool):
    with pytest.raises(ValueError):
        branch_pool.get_actual_branch_id_for_normal_branch(None)


def test_get_branch_for_block_none(branch_pool):
    with pytest.raises(ValueError):
        branch_pool.get_branch_for_block(None)


def test_get_branch_for_block_non_existing(branch_pool, basic_block):
    with pytest.raises(ValueError):
        branch_pool.get_branch_for_block(basic_block)


def test_get_id_for_registered_block(branch_pool):
    with pytest.raises(ValueError):
        branch_pool._get_id_for_registered_block(None)


@pytest.mark.parametrize(
    "function_name, branchless_function_count, branches_count",
    [
        pytest.param("simple_function", 1, 0),
        pytest.param("cmp_predicate", 0, 1),
        pytest.param("bool_predicate", 0, 1),
        pytest.param("for_loop", 0, 1),
        pytest.param("full_for_loop", 0, 1),
        pytest.param("multi_loop", 0, 3),
        pytest.param("comprehension", 1, 2),
        pytest.param("lambda_func", 1, 1),
        pytest.param("conditional_assignment", 0, 1),
        pytest.param("conditionally_nested_class", 2, 1),
    ],
)
def test_integrate_branch_distance_instrumentation(
    simple_module,
    tracer_mock,
    branch_pool,
    function_name,
    branchless_function_count,
    branches_count,
):
    function_callable = getattr(simple_module, function_name)
    instr = BranchDistanceInstrumentation(tracer_mock)
    function_callable.__code__ = instr._instrument_code_recursive(
        function_callable.__code__, True
    )
    assert branch_pool.get_num_branchless_functions() == branchless_function_count
    assert len(list(branch_pool.all_branches)) == branches_count


def test_tracer(branch_pool):
    tracer = MagicMock(ExecutionTracer)
    branch_pool.tracer = tracer
    assert branch_pool.tracer == tracer


def test_tracer_without_one(branch_pool):
    with pytest.raises(AssertionError):
        branch_pool.tracer
