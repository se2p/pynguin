#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import os

import pytest

from pynguin.analyses.seeding.staticconstantseeding import StaticConstantSeeding


@pytest.fixture
def seeding():
    seeding = StaticConstantSeeding()
    seeding._constants = {"float": set(), "int": set(), "str": set()}
    return seeding


@pytest.fixture
def fixture_dir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "fixtures",
    )


def test_singleton():
    seeding_1 = StaticConstantSeeding()
    seeding_2 = StaticConstantSeeding()
    assert seeding_1 is seeding_2


@pytest.mark.parametrize(
    "type_, result",
    [pytest.param("str", 29), pytest.param("int", 6), pytest.param("float", 1)],
)
def test_collect_constants(type_, result, seeding, fixture_dir):
    constants = seeding.collect_constants(fixture_dir)
    assert len(constants[type_]) == result


@pytest.mark.parametrize(
    "field_name",
    [
        pytest.param("has_strings"),
        pytest.param("has_ints"),
        pytest.param("has_floats"),
    ],
)
def test_has_no_strings(field_name, seeding):
    assert not getattr(seeding, field_name)


@pytest.mark.parametrize(
    "has_field_name, get_field_name, type_",
    [
        pytest.param("has_strings", "random_string", "str"),
        pytest.param("has_ints", "random_int", "int"),
        pytest.param("has_floats", "random_float", "float"),
    ],
)
def test_properties(has_field_name, get_field_name, type_, seeding, fixture_dir):
    constants = seeding.collect_constants(fixture_dir)
    assert getattr(seeding, has_field_name)
    assert getattr(seeding, get_field_name) in constants[type_]
