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
from pynguin.utils.namingscope import NamingScope


def test_naming_scope_same():
    scope = NamingScope()
    some_object = "something"
    name1 = scope.get_name(some_object)
    name2 = scope.get_name(some_object)
    assert name1 == name2


def test_naming_scope_different():
    scope = NamingScope()
    name1 = scope.get_name("one name")
    name2 = scope.get_name("another")
    assert name1 != name2


def test_naming_scope_known_indices_empty():
    scope = NamingScope()
    assert scope.known_name_indices == {}


def test_naming_scope_known_indices_not_empty():
    scope = NamingScope()
    some_object = "something"
    scope.get_name(some_object)
    assert scope.known_name_indices == {some_object: 0}
