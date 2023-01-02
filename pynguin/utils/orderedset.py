#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

"""
The following code is taken from https://github.com/pantsbuild/pants
We made minor changes so that our linting pipeline accepts the code.

Copyright 2020 Pants project contributors.
Licensed under the Apache License, Version 2.0.
SPDX-FileCopyrightText: 2020 Pants project contributors
SPDX-License-Identifier: Apache-2.0

An OrderedSet is a set that remembers its insertion order, and a FrozenOrderedSet is
one that is also immutable. Based on the library `ordered-set` developed by
Elia Robyn Lake (Robyn Speer) and released under the MIT license:
https://github.com/LuminosoInsight/ordered-set.
Copyright (c) 2012-2022 Elia Robyn Lake
SPDX-FileCopyrightText: 2012-2022 Elia Robyn Lake
SPDX-License-Identifier: MIT


The library `ordered-set` is itself originally based on a recipe originally posted to
ActivateState Recipes by Raymond Hettiger and released under the MIT license:
http://code.activestate.com/recipes/576694/.
Copyright (c) 2009 Raymond Hettiger
SPDX-FileCopyrightText: 2009 Raymond Hettiger
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import itertools
from typing import (
    AbstractSet,
    Any,
    Hashable,
    Iterable,
    Iterator,
    MutableSet,
    Sequence,
    Set,
    TypeVar,
    cast,
    overload,
)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
# pylint:disable=invalid-name
_TAbstractOrderedSet = TypeVar("_TAbstractOrderedSet", bound="_AbstractOrderedSet")


class _AbstractOrderedSet(AbstractSet[T], Sequence[T]):
    """Common functionality shared between OrderedSet and FrozenOrderedSet."""

    @overload
    def __getitem__(self, index: int) -> T:
        pass

    @overload
    def __getitem__(self, index: slice) -> _AbstractOrderedSet[T]:
        pass

    def __getitem__(self, index: int | slice) -> T:  # type:ignore
        """Lookup item at given position. Caution, as this runs in O(n).

        Args:
            index: The index whose value we want to retrieve.

        Returns:
            The value of the given index.

        Raises:
            NotImplementedError: When given a slice.
            IndexError: When the index is out of range.
        """
        if isinstance(index, slice):
            raise NotImplementedError("Slicing currently not supported.")
        for i, key in enumerate(self._items.keys()):
            if i == index:
                return key
        raise IndexError("Index out of range.")

    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        # Using a dictionary, rather than using the recipe's original
        # `self |= iterable`, results in a ~20% performance increase for the
        # constructor.
        #
        # NB: Dictionaries are ordered in Python 3.6+. While this was not formalized
        # until Python 3.7, Python 3.6 uses this behavior; Pants requires CPython 3.6+
        # to run, so this assumption is safe for us to rely on.
        self._items: dict[T, None] = {v: None for v in iterable or ()}

    def __len__(self) -> int:
        return len(self._items)

    def __copy__(self: _TAbstractOrderedSet) -> _TAbstractOrderedSet:
        return self.__class__(self)

    def __contains__(self, key: Any) -> bool:
        return key in self._items

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __reversed__(self) -> Iterator[T]:
        return reversed(tuple(self._items.keys()))

    def __repr__(self) -> str:
        name = self.__class__.__name__
        if not self:
            return f"{name}()"
        return f"{name}({list(self)!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return len(self._items) == len(other._items) and all(
            x == y for x, y in zip(self._items, other._items, strict=True)
        )

    # pylint:disable-next=line-too-long, arguments-renamed
    def __or__(  # type: ignore[override]
        self: _TAbstractOrderedSet, other: Iterable[T]
    ) -> _TAbstractOrderedSet:
        return self.union(other)

    def union(self: _TAbstractOrderedSet, *others: Iterable[T]) -> _TAbstractOrderedSet:
        """Combines all unique items.
        Each item's order is defined by its first appearance # noqa: DAR201,DAR101.

        Args:
            *others: the iterables to union with

        Returns:
            A new ordered set containing the union.
        """
        # Differences with AbstractSet: our set union forces "other" to have the same
        # type. That is, while AbstractSet allows {1, 2, 3} | {(True, False)} resulting
        # in set[int | tuple[bool, bool]], the analogous for descendants  of
        # _TAbstractOrderedSet is not allowed.
        #
        # GOTCHA: given _TAbstractOrderedSet[S]:
        #   if T is a subclass of S => _TAbstractOrderedSet[S] => *appears* to perform
        #     unification but it doesn't
        #   if S is a subclass of T => type error (while AbstractSet would resolve to
        #     AbstractSet[T])
        merged_iterables = itertools.chain([cast(Iterable[T], self)], others)
        return self.__class__(itertools.chain.from_iterable(merged_iterables))

    def __and__(self: _TAbstractOrderedSet, other: Iterable[T]) -> _TAbstractOrderedSet:
        # The parent class's implementation of this is backwards.
        return self.intersection(other)

    def intersection(
        self: _TAbstractOrderedSet, *others: Iterable[T]
    ) -> _TAbstractOrderedSet:
        """Returns elements in common between all sets.
        Order is defined only by the first set.

        Args:
            *others: The iterable to intersect with

        Returns:
            A new set containing the intersection.
        """
        cls = self.__class__
        if not others:
            return cls(self)
        common = set.intersection(*(set(other) for other in others))
        return cls(item for item in self if item in common)

    def difference(
        self: _TAbstractOrderedSet, *others: Iterable[T]
    ) -> _TAbstractOrderedSet:
        """Returns all elements that are in this set but not the others.

        Args:
            *others: The iterable to intersect with

        Returns:
            A new set containing the difference.
        """
        cls = self.__class__
        if not others:
            return cls(self)
        other = set.union(*(set(other) for other in others))
        return cls(item for item in self if item not in other)

    def issubset(self, other: Iterable[T]) -> bool:
        """Report whether another set contains this set.

        Args:
            other: The set to check

        Returns:
            True, if this is a subset of other.
        """
        try:
            # Fast check for obvious cases
            if len(self) > len(other):  # type: ignore[arg-type]
                return False
        except TypeError:
            pass
        return all(item in other for item in self)

    def issuperset(self, other: Iterable[T]) -> bool:
        """Report whether this set contains another set.

        Args:
            other: The set to check

        Returns:
            True, if this is a superset of other.
        """
        try:
            # Fast check for obvious cases
            if len(self) < len(other):  # type: ignore[arg-type]
                return False
        except TypeError:
            pass
        return all(item in self for item in other)

    # pylint:disable-next=line-too-long, arguments-renamed
    def __xor__(  # type: ignore[override]
        self: _TAbstractOrderedSet, other: Iterable[T]
    ) -> _TAbstractOrderedSet:
        return self.symmetric_difference(other)

    def symmetric_difference(
        self: _TAbstractOrderedSet, other: Iterable[T]
    ) -> _TAbstractOrderedSet:
        """Return the symmetric difference of this OrderedSet and another set as a new
        OrderedSet. That is, the new set will contain all elements that are in exactly
        one of the sets. Their order will be preserved, with elements from `self`
        preceding elements from `other`.

        Args:
            other: The other set

        Returns:
            The symmetric difference.
        """
        cls = self.__class__
        diff1 = cls(self).difference(other)
        diff2 = cls(other).difference(self)
        return diff1.union(diff2)


class OrderedSet(_AbstractOrderedSet[T], MutableSet[T]):
    """A mutable set that retains its order.
    This is not safe to use with the V2 engine.
    """

    def add(self, value: T) -> None:
        """Add `value` as an item to this OrderedSet.

        Args:
            value: the object to add
        """
        self._items[value] = None

    def update(self, iterable: Iterable[T]) -> None:
        """Update the set with the given iterable sequence.

        Args:
            iterable: The iterable to insert into this set
        """
        for item in iterable:
            self._items[item] = None

    def discard(self, value: T) -> None:
        self._items.pop(value, None)

    def clear(self) -> None:
        self._items.clear()

    def difference_update(self, *others: Iterable[T]) -> None:
        """Update this OrderedSet to remove items from one or more other sets.

        Args:
            *others: The sets to difference update with.
        """
        items_to_remove: set[T] = set()
        for other in others:
            items_as_set = set(other)
            items_to_remove |= items_as_set
        self._items = {
            item: None for item in self._items.keys() if item not in items_to_remove
        }

    def intersection_update(self, other: Iterable[T]) -> None:
        """Update this OrderedSet to keep only items in another set, preserving their
        order in this set.

        Args:
            other: The set to intersection update with.
        """
        other = set(other)
        self._items = {item: None for item in self._items.keys() if item in other}

    def symmetric_difference_update(self, other: Iterable[T]) -> None:
        """Update this OrderedSet to remove items from another set, then add items from
        the other set that were not present in this set.

        Args:
            other: The other set.
        """
        items_to_add = [item for item in other if item not in self]
        items_to_remove = cast(Set[T], set(other))
        self._items = {
            item: None for item in self._items.keys() if item not in items_to_remove
        }
        for item in items_to_add:
            self._items[item] = None


class FrozenOrderedSet(_AbstractOrderedSet[T_co], Hashable):  # type:ignore
    """A frozen (i.e. immutable) set that retains its order.
    This is safe to use with the V2 engine.
    """

    def __init__(self, iterable: Iterable[T_co] | None = None) -> None:
        super().__init__(iterable)
        self.__hash: int | None = None

    def __hash__(self) -> int:
        if self.__hash is None:
            self.__hash = 0
            for item in self._items.keys():
                self.__hash ^= hash(item)
        return self.__hash
