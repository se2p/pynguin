#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

from pynguin.analyses.seeding.constantseeding import DynamicConstantSeeding


@pytest.fixture()
def dynamic_seeding() -> DynamicConstantSeeding:
    return DynamicConstantSeeding()


def test_random_int(dynamic_seeding):
    dynamic_seeding._dynamic_pool[int].add(5)
    value = dynamic_seeding.random_int

    assert value == 5


def test_random_float(dynamic_seeding):
    dynamic_seeding._dynamic_pool[float].add(5.0)
    value = dynamic_seeding.random_float

    assert value == 5.0


def test_random_string(dynamic_seeding):
    dynamic_seeding._dynamic_pool[str].add("5")
    value = dynamic_seeding.random_string

    assert value == "5"


def test_reset(dynamic_seeding):
    dynamic_seeding.add_value(5)
    dynamic_seeding.add_value("foo")
    assert dynamic_seeding.has_constants(int)
    assert dynamic_seeding.has_constants(str)
    dynamic_seeding.reset()
    assert not dynamic_seeding.has_constants(int)
    assert not dynamic_seeding.has_constants(str)
