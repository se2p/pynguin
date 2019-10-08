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
from pynguin.utils.string import String


def test_eq():
    test = String("Test")
    var = test == "Search"
    assert "Search" in String.observed
    assert not var


def test_not_eq():
    test = String("Test")
    var = test == 42
    assert not var


def test_startswith():
    test = String("Test")
    var = test.startswith("Startswith")
    assert "Startswith" in String.observed
    assert not var


def test_endswith():
    test = String("Test")
    var = test.endswith("Endswith")
    assert "Endswith" in String.observed
    assert not var


def test_hash():
    test = String("Test")
    assert test.__hash__() == hash("Test")
