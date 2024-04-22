#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import copy

import pytest

from pynguin.utils.orderedset import OrderedSet


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
