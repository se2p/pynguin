#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

from pynguin.analyses.constants import ConstantPool


@pytest.fixture()
def pool() -> ConstantPool:
    return ConstantPool()


def test_has_constant(pool):
    pool.add_constant(42)
    assert pool.has_constant_for(int)


def test_has_no_constant(pool):
    assert not pool.has_constant_for(int)


def test_get_constant_for(pool):
    pool.add_constant(42)
    assert pool.get_constant_for(int) == 42


def test_add_constant(pool):
    pool.add_constant(42)
    assert pool._constants[int] == {42}


def test_remove_constant(pool):
    pool.add_constant(42)
    pool.add_constant(17)
    assert len(pool) == 2
    pool.remove_constant(17)
    assert len(pool) == 1


def test_get_all_constants(pool):
    pool.add_constant(42)
    pool.add_constant(5)
    assert pool.get_all_constants_for(int) == {5, 42}


def test_len(pool):
    assert len(pool) == 0


def test_len_not_empty(pool):
    pool.add_constant(42)
    pool.add_constant(13.37)
    assert len(pool) == 2
