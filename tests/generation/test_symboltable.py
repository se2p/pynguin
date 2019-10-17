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
from typing import Iterator

import black
import pytest

from pynguin.generation.symboltable import SymbolTable
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.string import String


def test_get_default_domain():
    table = SymbolTable.get_default_domain()
    assert table == {int, String, float, complex, bool}


def test_set_get_item():
    table = SymbolTable(None)
    table[int] = 42
    assert table[int] == 42


def test_delitem():
    table = SymbolTable(None)
    table["int"] = 42
    assert table["int"] == 42
    del table["int"]
    assert "int" not in table


def test_len():
    table = SymbolTable(None)
    assert len(table) == 0
    table["int"] = 42
    assert table.__len__() == 1


def test_iter():
    table = SymbolTable(None, domains={int, float})
    assert isinstance(table.__iter__(), Iterator)


def test_add_callable():
    def foo():
        return 42

    table = SymbolTable(None)
    table.add_callable(foo)


def test_add_class_callable():
    class Dummy:
        x = 0

        def set_x(self, x):
            self.x = x

    table = SymbolTable(None)
    table.add_callable(Dummy.set_x)


@pytest.mark.skip()
def test_add_crap_callable():
    table = SymbolTable(None)
    with pytest.raises(GenerationException):
        table.add_callable(int)


def test_add_path_callable():
    table = SymbolTable(None)
    table.add_callable(black.BracketTracker)


def test_add_constraint():
    table = SymbolTable(None)
    with pytest.raises(Exception):
        table.add_constraint(test_delitem, None)


def test_add_constraints():
    table = SymbolTable(None)
    with pytest.raises(Exception):
        table.add_constraints(test_delitem, [None, None])


def test_add_constraints_empty_list():
    table = SymbolTable(None)
    table.add_constraints(test_delitem, [])
