#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the implementation of an ordered set.

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
import types
from collections.abc import Hashable, Iterable, Iterator, MutableSet, Sequence
from collections.abc import Set as AbstractSet
from typing import Any, TypeVar, cast, get_args, overload

from typing_extensions import Self

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class _AbstractOrderedSet(AbstractSet[T], Sequence[T]):  # noqa: PLW1641
    """Common functionality shared between OrderedSet and FrozenOrderedSet."""

    @overload
    def __getitem__(self, index: int) -> T:
        pass

    @overload
    def __getitem__(self, index: slice) -> _AbstractOrderedSet[T]:
        pass

    def __getitem__(self, index: int | slice) -> T:  # type: ignore[misc]
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
        self._items: dict[T, None] = dict.fromkeys(iterable or ())

    def __len__(self) -> int:
        return len(self._items)

    def __copy__(self) -> Self:
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return len(self._items) == len(other._items) and all(
            x == y for x, y in zip(self._items, other._items, strict=True)
        )

    def __or__(self, other: Iterable[T]) -> Self:  # type: ignore[override]
        return self.union(other)

    def union(self, *others: Iterable[T]) -> Self:
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
        merged_iterables = itertools.chain([cast("Iterable[T]", self)], others)
        return self.__class__(itertools.chain.from_iterable(merged_iterables))

    def __and__(self, other: Iterable[T]) -> Self:
        # The parent class's implementation of this is backwards.
        return self.intersection(other)

    def intersection(self, *others: Iterable[T]) -> Self:
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

    def difference(self, *others: Iterable[T]) -> Self:
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

    def __xor__(self, other: Iterable[T]) -> Self:  # type: ignore[override]
        return self.symmetric_difference(other)

    def symmetric_difference(self, other: Iterable[T]) -> Self:
        """Computes the symmetric difference.

        Return the symmetric difference of this OrderedSet and another set as a new
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

    def discard(self, value: T) -> None:  # noqa: D102
        self._items.pop(value, None)

    def clear(self) -> None:  # noqa: D102
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
        self._items = {item: None for item in self._items if item not in items_to_remove}

    def intersection_update(self, other: Iterable[T]) -> None:
        """Computes the intersection inplace.

        Update this OrderedSet to keep only items in another set, preserving their
        order in this set.

        Args:
            other: The set to intersection update with.
        """
        other = set(other)
        self._items = {item: None for item in self._items if item in other}

    def symmetric_difference_update(self, other: Iterable[T]) -> None:
        """Computes the symmetric difference inplace.

        Update this OrderedSet to remove items from another set, then add items from
        the other set that were not present in this set.

        Args:
            other: The other set.
        """
        items_to_add = [item for item in other if item not in self]
        items_to_remove = cast("set[T]", set(other))
        self._items = {item: None for item in self._items if item not in items_to_remove}
        for item in items_to_add:
            self._items[item] = None


class OrderedTypeSet(Sequence[type]):  # noqa: PLR0904
    """A set that resolves | operators between types.

    When `add()` is called with a union type (e.g., `int | float`), it extracts
    the individual types and adds them separately.
    """

    def __init__(self, iterable: Iterable[type | types.UnionType] = ()) -> None:
        """Initialize the set with an iterable of types."""
        self._ordered_set = OrderedSet[type]()
        self.update(iterable)

    def __contains__(self, value: Any) -> bool:
        """Check if a type is in the set."""
        if not isinstance(value, (type | types.UnionType)):
            return False
        return value in self._ordered_set

    def __iter__(self):
        """Return an iterator over the set."""
        return iter(self._ordered_set)

    def __len__(self) -> int:
        """Return the number of types in the set."""
        return len(self._ordered_set)

    @overload
    def __getitem__(self, index: int) -> type:
        pass

    @overload
    def __getitem__(self, index: slice) -> Sequence[type]:
        pass

    def __getitem__(  # type: ignore[misc]
        self,
        index: int | slice,
    ) -> type | OrderedTypeSet:
        """Lookup item at given position."""
        if isinstance(index, slice):
            return OrderedTypeSet(self._ordered_set[index])
        return self._ordered_set[index]

    def __eq__(self, other: object) -> bool:
        """Check equality with another OrderedTypeSet."""
        if not isinstance(other, OrderedTypeSet):
            return NotImplemented
        return self._ordered_set == other._ordered_set

    def __repr__(self) -> str:
        """Return a string representation of the set."""
        return f"OrderedTypeSet({list(self._ordered_set)!r})"

    def __and__(self, other):
        """Return the intersection of this set with another."""
        return self.intersection(other)

    def __or__(self, other):
        """Return the union of this set with another."""
        return self.union(other)

    def __xor__(self, other):
        """Return the symmetric difference of this set with another."""
        return self.symmetric_difference(other)

    def __hash__(self) -> int:
        """Return a hash based on the set's contents."""
        return hash(tuple(self._ordered_set))

    def add(self, value: type | types.UnionType) -> None:
        """Add a type or a union of types to the set."""
        self._ordered_set.update(get_args(value) or (value,))

    def discard(self, value: type | types.UnionType) -> None:
        """Remove a type or a union of types from the set."""
        for subtype in get_args(value) or (value,):
            self._ordered_set.discard(subtype)

    def update(self, iterable: Iterable[type | types.UnionType]) -> None:
        """Update the set with multiple types or union types."""
        for item in iterable:
            self.add(item)

    def clear(self) -> None:
        """Remove all items from the set."""
        self._ordered_set.clear()

    def union(self, *others: Iterable[type | types.UnionType]) -> OrderedTypeSet:
        """Return the union of this set with others."""
        return OrderedTypeSet(self._ordered_set.union(*(OrderedTypeSet(other) for other in others)))

    def intersection(self, *others: Iterable[type | types.UnionType]) -> OrderedTypeSet:
        """Return the intersection of this set with others."""
        return OrderedTypeSet(
            self._ordered_set.intersection(*(OrderedTypeSet(other) for other in others))
        )

    def difference(self, *others: Iterable[type | types.UnionType]) -> OrderedTypeSet:
        """Return the difference of this set with others."""
        return OrderedTypeSet(
            self._ordered_set.difference(*(OrderedTypeSet(other) for other in others))
        )

    def issubset(self, other: Iterable[type | types.UnionType]) -> bool:
        """Check if this set is a subset of another."""
        return self._ordered_set.issubset(OrderedTypeSet(other))

    def issuperset(self, other: Iterable[type | types.UnionType]) -> bool:
        """Check if this set is a superset of another."""
        return self._ordered_set.issuperset(OrderedTypeSet(other))

    def symmetric_difference(self, other: Iterable[type | types.UnionType]) -> OrderedTypeSet:
        """Return the symmetric difference of this set with another."""
        return OrderedTypeSet(self._ordered_set.symmetric_difference(OrderedTypeSet(other)))

    def difference_update(self, *others: Iterable[type | types.UnionType]) -> None:
        """Update this set to remove elements in others."""
        self._ordered_set.difference_update(*(OrderedTypeSet(other) for other in others))

    def intersection_update(self, other: Iterable[type | types.UnionType]) -> None:
        """Update this set to keep only items in another set."""
        self._ordered_set.intersection_update(OrderedTypeSet(other))

    def symmetric_difference_update(self, other: Iterable[type | types.UnionType]) -> None:
        """Update this set to remove items from another set, then add items from the other set."""
        self._ordered_set.symmetric_difference_update(OrderedTypeSet(other))


class FrozenOrderedSet(_AbstractOrderedSet[T_co], Hashable):  # type: ignore[type-var]
    """A frozen (i.e. immutable) set that retains its order.

    This is safe to use with the V2 engine.
    """

    def __init__(self, iterable: Iterable[T_co] | None = None) -> None:  # noqa: D107
        super().__init__(iterable)
        self.__hash: int | None = None

    def __hash__(self) -> int:
        if self.__hash is None:
            self.__hash = 0
            for item in self._items:
                self.__hash ^= hash(item)
        return self.__hash
