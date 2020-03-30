# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
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
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "fixtures",
    )


def test_singleton():
    seeding_1 = StaticConstantSeeding()
    seeding_2 = StaticConstantSeeding()
    assert seeding_1 is seeding_2


@pytest.mark.parametrize(
    "type_, result",
    [pytest.param("str", 17), pytest.param("int", 3), pytest.param("float", 1)],
)
def test_collect_strings(type_, result, seeding, fixture_dir):
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
