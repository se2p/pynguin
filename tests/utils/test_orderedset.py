#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import copy

import pytest

from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.orderedset import OrderedTypeSet


@pytest.mark.parametrize("length, iterable", [(0, []), (3, [1, 2, 3]), (2, [1, 2, 2])])
def test_orderedset_len(length, iterable):
    assert len(OrderedSet(iterable)) == length


def test_orderedset_copy():
    ordered = OrderedSet([1, 2, 3])
    copied = copy.copy(ordered)
    assert ordered == copied


@pytest.mark.parametrize("element, result", [(0, False), (3, True)])
def test_orderedset_contains(element, result):
    assert (element in OrderedSet([1, 2, 3])) == result


def test_orderedset_reversed():
    ordered = OrderedSet([1, 2, 3])
    assert tuple(reversed(ordered)) == (3, 2, 1)


@pytest.mark.parametrize(
    "first,second,result",
    [
        ([1, 2, 3], [1, 2, 3], True),
        ([1, 2, 3], [1, 2], False),
        ([1, 2, None], [1, 2], False),
        ([1, 2, 3], [1, 3, 2], False),
    ],
)
def test_orderedset_eq(first, second, result):
    assert (OrderedSet(first) == OrderedSet(second)) == result


@pytest.mark.parametrize(
    "first, second, result",
    [([], [], []), ([1], [], [1]), ([], [1], [1]), ([1], [2], [1, 2])],
)
def test_ordereset_or_union(first, second, result):
    assert OrderedSet(first) | OrderedSet(second) == OrderedSet(result)
    assert OrderedSet(first).union(OrderedSet(second)) == OrderedSet(result)


@pytest.mark.parametrize(
    "first, second, result",
    [([], [], []), ([1], [], []), ([], [1], []), ([1], [2], []), ([1, 2], [2, 3], [2])],
)
def test_ordereset_and_intersection(first, second, result):
    assert OrderedSet(first) & OrderedSet(second) == OrderedSet(result)
    assert OrderedSet(first).intersection(OrderedSet(second)) == OrderedSet(result)


@pytest.mark.parametrize(
    "length, iterable", [(0, []), (3, [int, float, str]), (2, [int, float, int])]
)
def test_orderedtypeset_len(length, iterable):
    assert len(OrderedTypeSet(iterable)) == length


def test_orderedtypeset_copy():
    ordered = OrderedTypeSet([int, float, str])
    copied = copy.copy(ordered)
    assert ordered == copied


@pytest.mark.parametrize("element, result", [(bool, False), (str, True)])
def test_orderedtypeset_contains(element, result):
    assert (element in OrderedTypeSet([int, float, str])) == result


def test_orderedtypeset_reversed():
    ordered = OrderedTypeSet([int, float, str])
    assert tuple(reversed(ordered)) == (str, float, int)


@pytest.mark.parametrize(
    "first, second, result",
    [
        ([int, float, str], [int, float, str], True),
        ([int, float, str], [int, float], False),
        ([int, float, None], [int, float], False),
        ([int, float, str], [str, float, int], False),
    ],
)
def test_orderedtypeset_eq(first, second, result):
    assert (OrderedTypeSet(first) == OrderedTypeSet(second)) == result


@pytest.mark.parametrize(
    "first, second, result",
    [([], [], []), ([int], [], [int]), ([], [int], [int]), ([int], [float], [int, float])],
)
def test_orderedtypeset_or_union(first, second, result):
    assert OrderedTypeSet(first) | OrderedTypeSet(second) == OrderedTypeSet(result)
    assert OrderedTypeSet(first).union(OrderedTypeSet(second)) == OrderedTypeSet(result)


@pytest.mark.parametrize(
    "first, second, result",
    [
        ([], [], []),
        ([int], [], []),
        ([], [int], []),
        ([int], [float], []),
        ([int, float], [float, str], [float]),
    ],
)
def test_orderedtypeset_and_intersection(first, second, result):
    assert OrderedTypeSet(first) & OrderedTypeSet(second) == OrderedTypeSet(result)
    assert OrderedTypeSet(first).intersection(OrderedTypeSet(second)) == OrderedTypeSet(result)


def test_ordered_type_set_add():
    ordered_type_set = OrderedTypeSet()
    ordered_type_set.add(float | int)
    assert float in ordered_type_set
    assert int in ordered_type_set


def test_ordered_type_set_discard():
    ordered_type_set = OrderedTypeSet()
    ordered_type_set.add(float | int)
    ordered_type_set.discard(float)
    assert float not in ordered_type_set
    assert int in ordered_type_set


def test_ordered_type_set_discard_2():
    ordered_type_set = OrderedTypeSet()
    ordered_type_set.add(float | int)
    ordered_type_set.add(str)
    ordered_type_set.discard(float | str)
    assert int in ordered_type_set


def test_ordered_type_set_union():
    ordered_type_set_1 = OrderedTypeSet([str | int])
    ordered_type_set_2 = OrderedTypeSet([str])
    union = ordered_type_set_1 | ordered_type_set_2
    assert str in union
    assert int in union


def test_ordered_type_set_init():
    ordered_type_set = OrderedTypeSet([int, float | str])
    assert int in ordered_type_set
    assert float in ordered_type_set
    assert str in ordered_type_set


def test_ordered_type_set_len():
    ordered_type_set = OrderedTypeSet([int, float])
    assert len(ordered_type_set) == 2


def test_ordered_type_set_getitem():
    ordered_type_set = OrderedTypeSet([int, float, str])
    assert ordered_type_set[0] is int
    assert ordered_type_set[1] is float
    assert ordered_type_set[2] is str


def test_ordered_type_set_getitem_slice():
    ordered_type_set = OrderedTypeSet([int, float, str])
    with pytest.raises(NotImplementedError):
        ordered_type_set[1:2]


def test_ordered_type_set_eq():
    assert OrderedTypeSet([int, float]) == OrderedTypeSet([int, float])
    assert OrderedTypeSet([int, float]) != OrderedTypeSet([str, float])


def test_ordered_type_set_eq_other_type():
    assert OrderedTypeSet([int, float]) != "foo"


def test_ordered_type_set_clear():
    ordered_type_set = OrderedTypeSet([int, float])
    ordered_type_set.clear()
    assert len(ordered_type_set) == 0


def test_ordered_type_set_intersection():
    ordered_type_set_1 = OrderedTypeSet([int, float, str])
    ordered_type_set_2 = OrderedTypeSet([float, str])
    intersection = ordered_type_set_1 & ordered_type_set_2
    assert float in intersection
    assert str in intersection
    assert int not in intersection


def test_ordered_type_set_difference():
    ordered_type_set_1 = OrderedTypeSet([int, float, str])
    ordered_type_set_2 = OrderedTypeSet([str])
    difference = ordered_type_set_1.difference(ordered_type_set_2)
    assert int in difference
    assert float in difference
    assert str not in difference


def test_ordered_type_set_symmetric_difference():
    ordered_type_set_1 = OrderedTypeSet([int, float])
    ordered_type_set_2 = OrderedTypeSet([float, str])
    sym_diff = ordered_type_set_1 ^ ordered_type_set_2
    assert int in sym_diff
    assert str in sym_diff
    assert float not in sym_diff


def test_ordered_type_set_issubset():
    ordered_type_set_1 = OrderedTypeSet([int, float])
    ordered_type_set_2 = OrderedTypeSet([int, float, str])
    assert ordered_type_set_1.issubset(ordered_type_set_2)
    assert not ordered_type_set_2.issubset(ordered_type_set_1)


def test_ordered_type_set_issuperset():
    ordered_type_set_1 = OrderedTypeSet([int, float, str])
    ordered_type_set_2 = OrderedTypeSet([int, float])
    assert ordered_type_set_1.issuperset(ordered_type_set_2)
    assert not ordered_type_set_2.issuperset(ordered_type_set_1)


def test_ordered_type_set_difference_update():
    ordered_type_set = OrderedTypeSet([int, float, str])
    ordered_type_set.difference_update([float, str])
    assert int in ordered_type_set
    assert float not in ordered_type_set
    assert str not in ordered_type_set


def test_ordered_type_set_intersection_update():
    ordered_type_set = OrderedTypeSet([int, float, str])
    ordered_type_set.intersection_update([float, str])
    assert float in ordered_type_set
    assert str in ordered_type_set
    assert int not in ordered_type_set


def test_ordered_type_set_symmetric_difference_update():
    ordered_type_set = OrderedTypeSet([int, float])
    ordered_type_set.symmetric_difference_update([float, str])
    assert int in ordered_type_set
    assert str in ordered_type_set
    assert float not in ordered_type_set


def test_ordered_type_set_repr():
    ordered_type_set = OrderedTypeSet([int, float])
    assert repr(ordered_type_set) == "OrderedTypeSet([<class 'int'>, <class 'float'>])"


def test_ordered_type_set_hash():
    ordered_type_set = OrderedTypeSet([int, float])
    assert hash(ordered_type_set) == hash((int, float))
