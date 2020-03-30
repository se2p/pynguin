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

from pynguin.analyses.seeding.staticstringseeding import StaticStringSeeding


@pytest.fixture
def seeding():
    seeding = StaticStringSeeding()
    seeding._strings = set()
    return seeding


@pytest.fixture
def fixture_dir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "fixtures",
    )


def test_singleton():
    seeding_1 = StaticStringSeeding()
    seeding_2 = StaticStringSeeding()
    assert seeding_1 is seeding_2


def test_collect_strings(seeding, fixture_dir):
    strings = seeding.collect_strings(fixture_dir)
    assert len(strings) == 17


def test_has_no_strings(seeding):
    assert not seeding.has_strings


def test_properties(seeding, fixture_dir):
    strings = seeding.collect_strings(fixture_dir)
    assert seeding.has_strings
    assert seeding.random_string in strings
