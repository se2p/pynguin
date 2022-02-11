#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import os

import pytest

from pynguin.analyses.seeding import _StaticConstantSeeding, static_constant_seeding


@pytest.fixture
def seeding():
    seeding = static_constant_seeding
    seeding._constants = {float: set(), int: set(), str: set()}
    return seeding


@pytest.fixture
def fixture_dir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "",
        "..",
        "fixtures",
        "seeding",
        "staticconstantseeding",
    )


@pytest.mark.parametrize(
    "type_, result",
    [pytest.param(str, 2), pytest.param(int, 2), pytest.param(float, 1)],
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
        pytest.param("has_strings", "random_string", str),
        pytest.param("has_ints", "random_int", int),
        pytest.param("has_floats", "random_float", float),
    ],
)
def test_properties(has_field_name, get_field_name, type_, seeding, fixture_dir):
    constants = seeding.collect_constants(fixture_dir)
    assert getattr(seeding, has_field_name)
    assert getattr(seeding, get_field_name) in constants[type_]


def test_has_constant_without_type():
    seeding = _StaticConstantSeeding()
    assert not seeding.has_constants(int)
