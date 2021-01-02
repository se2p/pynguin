#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest
from bytecode import BasicBlock, Instr

from pynguin.coverage.branch.branchcoveragegoal import Branch
from pynguin.coverage.branch.branchpool import INSTANCE


@pytest.fixture
def branch_pool():
    INSTANCE.clear()
    return INSTANCE


@pytest.fixture
def basic_block():
    return MagicMock(BasicBlock)


def test_register_branchless_method(branch_pool):
    branch_pool.register_branchless_function("foo", 42)
    assert branch_pool.branchless_functions == {"foo"}
    assert branch_pool.is_branchless_function("foo")
    assert branch_pool.get_num_branchless_functions() == 1
    assert branch_pool.get_branchless_function_line_number("foo") == 42


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
