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
import pytest

from pynguin.utils.iterator import ListIterator


def test_iteration():
    test_list = [1, 2, 3]
    it = ListIterator(test_list)
    for i in test_list:
        it.next()
        assert it.current() == i


def test_iteration_end():
    test_list = [1, 2, 3]
    it = ListIterator(test_list)
    it.next()
    it.next()
    it.next()
    assert not it.next()


def test_empty_list_no_next():
    test_list = []
    it = ListIterator(test_list)
    assert not it.next()


def test_empty_list_no_previous():
    test_list = []
    it = ListIterator(test_list)
    assert not it.has_previous()


def test_has_previous():
    test_list = [1, 2]
    it = ListIterator(test_list)
    it.next()
    it.next()
    assert it.has_previous()


def test_no_has_previous():
    test_list = [1]
    it = ListIterator(test_list)
    assert not it.has_previous()


def test_previous_value():
    test_list = [1, 2]
    it = ListIterator(test_list)
    it.next()
    it.next()
    assert it.previous() == 1


def test_insert():
    test_list = [42, 1337]
    it = ListIterator(test_list)
    it.next()
    it.insert_before([1, 3, 5, 7, 11])
    assert all([a == b for a, b in zip(test_list, [1, 3, 5, 7, 11, 42, 1337])])


def test_insert_offset():
    test_list = [42, 1337]
    it = ListIterator(test_list)
    it.next()
    it.next()
    it.insert_before([1, 3, 5], 1)
    assert all([a == b for a, b in zip(test_list, [1, 3, 5, 42, 1337])])


def test_insert_current():
    test_list = [42, 1337]
    it = ListIterator(test_list)
    it.next()
    it.next()
    it.insert_before([1, 1, 2])
    assert it.current() == 1337


def test_insert_previous():
    test_list = [42, 1337]
    it = ListIterator(test_list)
    it.next()
    it.next()
    it.insert_before([1, 3, 5])
    assert it.previous() == 5


@pytest.mark.parametrize("test_list,result", [([], False), ([1], True)])
def test_can_peek(test_list, result):
    it = ListIterator(test_list)
    assert it.can_peek() == result


def test_peek_first():
    test = [1]
    it = ListIterator(test)
    assert it.peek() == 1


def test_peek_mid():
    test = [1, 2, 3]
    it = ListIterator(test)
    it.next()
    assert it.peek() == 2


def test_peek_no_more():
    test = [1]
    it = ListIterator(test)
    it.next()
    with pytest.raises(AssertionError):
        it.peek()


def test_peek_two():
    test = [1, 2]
    it = ListIterator(test)
    assert it.peek(2) == 2


def test_insert_after_current_empty():
    test = []
    it = ListIterator(test)
    it.insert_after_current([1, 2])
    assert test == [1, 2]


def test_insert_after_current_position():
    test = [1, 2]
    it = ListIterator(test)
    it.next()
    it.insert_after_current([42, 1337])
    assert test == [1, 42, 1337, 2]


def test_insert_after_current_end():
    test = [1, 2]
    it = ListIterator(test)
    it.next()
    it.next()
    it.insert_after_current([42, 1337])
    assert test == [1, 2, 42, 1337]


def test_insert_after_current_seen_again():
    test = [1, 2]
    it = ListIterator(test)
    it.next()
    it.next()
    it.insert_after_current([42, 1337])
    assert it.next()
    assert it.current() == 42
    assert it.next()
    assert it.current() == 1337
