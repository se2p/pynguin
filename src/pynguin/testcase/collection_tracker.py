#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides collection tracking to record accesses during test execution."""

from __future__ import annotations

import contextlib
import dataclasses
import operator
import threading
from typing import TYPE_CHECKING, Any, SupportsIndex

from typing_extensions import Self

from pynguin.testcase.execution_observers import RemoteExecutionObserver

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.execution_result import ExecutionResult


def is_safe_key(key: object) -> bool:
    """Check whether a dictionary key can be safely serialized and rendered as a literal.

    Args:
        key: The key object to check.

    Returns:
        True if the key is safe to serialize and render as a literal, False otherwise.
    """
    if key is None or isinstance(key, str | int | float | bool | bytes | complex):
        return True
    if isinstance(key, tuple):
        return all(is_safe_key(elem) for elem in key)
    return False


@dataclasses.dataclass
class CollectionTrace:
    """Stores access trace data for a Pynguin-created collection statement."""

    # For lists and tuples:
    max_accessed_index: int | None = None
    accessed_indices: set[int] = dataclasses.field(default_factory=set)

    # For dictionaries:
    accessed_keys: set[object] = dataclasses.field(default_factory=set)
    missing_keys: set[object] = dataclasses.field(default_factory=set)


class TrackedList(list):  # noqa: FURB189
    """A list subclass that tracks accessed indices during test execution."""

    def __init__(self, iterable: Any = ()) -> None:
        """Initializes a tracked list.

        Args:
            iterable: An optional iterable to populate the list with.
        """
        super().__init__(iterable)
        self.max_accessed_index: int | None = None
        self.accessed_indices: set[int] = set()

    def _record_index(self, idx: int) -> None:
        """Record an accessed index, normalizing negative and out-of-bounds indices.

        Args:
            idx: The accessed index.
        """
        if idx >= 0:
            norm_idx = idx
        else:
            current_len = len(self)
            norm_idx = current_len + idx if current_len + idx >= 0 else -idx - 1

        self.accessed_indices.add(norm_idx)
        if self.max_accessed_index is None or norm_idx > self.max_accessed_index:
            self.max_accessed_index = norm_idx

    def _record_slice(self, s: slice) -> None:
        """Record all indices touched by a slice.

        Args:
            s: The accessed slice.
        """
        start, stop, step = s.indices(len(self))
        for i in range(start, stop, step):
            self.accessed_indices.add(i)
            if self.max_accessed_index is None or i > self.max_accessed_index:
                self.max_accessed_index = i

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            self._record_index(key)
        elif isinstance(key, slice):
            self._record_slice(key)
        return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(key, int):
            self._record_index(key)
        elif isinstance(key, slice):
            self._record_slice(key)
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        if isinstance(key, int):
            self._record_index(key)
        elif isinstance(key, slice):
            self._record_slice(key)
        super().__delitem__(key)

    def __iter__(self) -> Any:
        for i, item in enumerate(super().__iter__()):
            self._record_index(i)
            yield item

    def __reversed__(self) -> Any:
        current_len = len(self)
        for i in range(current_len - 1, -1, -1):
            self._record_index(i)
            yield super().__getitem__(i)

    def pop(self, index: SupportsIndex = -1) -> Any:  # noqa: D102
        with contextlib.suppress(TypeError, ValueError):
            self._record_index(operator.index(index))
        return super().pop(index)

    def index(self, value: Any, *args: Any) -> int:  # noqa: D102
        start = args[0] if len(args) > 0 else 0
        try:
            found_idx = super().index(value, *args)
            for i in range(start, found_idx + 1):
                self._record_index(i)
            return found_idx
        except ValueError:
            for i in range(start, len(self)):
                self._record_index(i)
            raise

    def count(self, value: Any) -> int:  # noqa: D102
        for i in range(len(self)):
            self._record_index(i)
        return super().count(value)

    def __contains__(self, value: object) -> bool:
        for i, item in enumerate(super().__iter__()):
            self._record_index(i)
            if item is value or item == value:
                return True
        return False

    def remove(self, value: Any) -> None:  # noqa: D102
        try:
            found_idx = super().index(value)
            for i in range(found_idx + 1):
                self._record_index(i)
        except ValueError:
            for i in range(len(self)):
                self._record_index(i)
            raise
        super().remove(value)

    def sort(self, *args: Any, **kwargs: Any) -> None:  # noqa: D102
        for i in range(len(self)):
            self._record_index(i)
        super().sort(*args, **kwargs)


class TrackedTuple(tuple):  # noqa: SLOT001
    """A tuple subclass that tracks accessed indices during test execution."""

    max_accessed_index: int | None
    accessed_indices: set[int]

    def __new__(cls, iterable: Any = ()) -> Self:
        """Create a new tracked tuple instance.

        Args:
            iterable: An optional iterable to populate the tuple with.

        Returns:
            The newly created TrackedTuple instance.
        """
        obj = super().__new__(cls, iterable)
        obj.max_accessed_index = None
        obj.accessed_indices = set()
        return obj

    def _record_index(self, idx: int) -> None:
        """Record an accessed index, normalizing negative and out-of-bounds indices.

        Args:
            idx: The accessed index.
        """
        if idx >= 0:
            norm_idx = idx
        else:
            current_len = len(self)
            norm_idx = current_len + idx if current_len + idx >= 0 else -idx - 1

        self.accessed_indices.add(norm_idx)
        if self.max_accessed_index is None or norm_idx > self.max_accessed_index:
            self.max_accessed_index = norm_idx

    def _record_slice(self, s: slice) -> None:
        """Record all indices touched by a slice.

        Args:
            s: The accessed slice.
        """
        start, stop, step = s.indices(len(self))
        for i in range(start, stop, step):
            self.accessed_indices.add(i)
            if self.max_accessed_index is None or i > self.max_accessed_index:
                self.max_accessed_index = i

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            self._record_index(key)
        elif isinstance(key, slice):
            self._record_slice(key)
        return super().__getitem__(key)

    def __iter__(self) -> Any:
        for i, item in enumerate(super().__iter__()):
            self._record_index(i)
            yield item

    def __reversed__(self) -> Any:
        current_len = len(self)
        for i in range(current_len - 1, -1, -1):
            self._record_index(i)
            yield super().__getitem__(i)

    def index(self, value: Any, *args: Any) -> int:  # noqa: D102
        start = args[0] if len(args) > 0 else 0
        try:
            found_idx = super().index(value, *args)
            for i in range(start, found_idx + 1):
                self._record_index(i)
            return found_idx
        except ValueError:
            for i in range(start, len(self)):
                self._record_index(i)
            raise

    def count(self, value: Any) -> int:  # noqa: D102
        for i in range(len(self)):
            self._record_index(i)
        return super().count(value)

    def __contains__(self, value: object) -> bool:
        for i, item in enumerate(super().__iter__()):
            self._record_index(i)
            if item is value or item == value:
                return True
        return False


class TrackedDict(dict):  # noqa: FURB189
    """A dict subclass that tracks accessed and missing keys during test execution."""

    accessed_keys: set[object]
    missing_keys: set[object]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new tracked dict instance.

        Args:
            *args: Positional arguments to dict.
            **kwargs: Keyword arguments to dict.

        Returns:
            The newly created TrackedDict instance.
        """
        instance = super().__new__(cls, *args, **kwargs)
        instance.accessed_keys = set()
        instance.missing_keys = set()
        return instance

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes a tracked dict.

        Args:
            *args: Positional arguments to dict.
            **kwargs: Keyword arguments to dict.
        """
        super().__init__(*args, **kwargs)
        if not hasattr(self, "accessed_keys"):
            self.accessed_keys = set()
        if not hasattr(self, "missing_keys"):
            self.missing_keys = set()

    def __getitem__(self, key: Any) -> Any:
        self.accessed_keys.add(key)
        if key not in self:
            self.missing_keys.add(key)
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:  # noqa: D102
        self.accessed_keys.add(key)
        if key not in self:
            self.missing_keys.add(key)
        return super().get(key, default)

    def __contains__(self, key: object) -> bool:
        self.accessed_keys.add(key)
        if not super().__contains__(key):
            self.missing_keys.add(key)
        return super().__contains__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self.accessed_keys.add(key)
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self.accessed_keys.add(key)
        if key not in self:
            self.missing_keys.add(key)
        super().__delitem__(key)

    def pop(self, key: Any, *args: Any) -> Any:  # noqa: D102
        self.accessed_keys.add(key)
        if key not in self:
            self.missing_keys.add(key)
        return super().pop(key, *args)

    def popitem(self) -> tuple[Any, Any]:  # noqa: D102
        item = super().popitem()
        self.accessed_keys.add(item[0])
        return item

    def setdefault(self, key: Any, default: Any = None) -> Any:  # noqa: D102
        self.accessed_keys.add(key)
        if key not in self:
            self.missing_keys.add(key)
        return super().setdefault(key, default)

    def update(self, *args: Any, **kwargs: Any) -> None:  # noqa: D102
        super().update(*args, **kwargs)
        if args:
            other = args[0]
            if hasattr(other, "keys"):
                self.accessed_keys.update(other.keys())
            else:
                self.accessed_keys.update(k for k, _ in other)
        if kwargs:
            self.accessed_keys.update(kwargs.keys())

    def __iter__(self) -> Any:
        for k in super().__iter__():
            self.accessed_keys.add(k)
            yield k

    def keys(self) -> Any:  # noqa: D102
        self.accessed_keys.update(super().keys())
        return super().keys()

    def items(self) -> Any:  # noqa: D102
        self.accessed_keys.update(super().keys())
        return super().items()

    def values(self) -> Any:  # noqa: D102
        self.accessed_keys.update(super().keys())
        return super().values()


class RemoteCollectionTrackingObserver(RemoteExecutionObserver):
    """An observer that tracks accesses to Pynguin-created collections."""

    class RemoteCollectionTrackingLocalState(threading.local):
        """Thread-local state for collection tracking."""

        def __init__(self) -> None:
            """Initialize thread-local state."""
            super().__init__()
            self.tracked_collections: dict[int, TrackedList | TrackedTuple | TrackedDict] = {}
            self.position: int = 0

    def __init__(self) -> None:
        """Initializes the remote collection tracking observer."""
        super().__init__()
        self._local_state = RemoteCollectionTrackingObserver.RemoteCollectionTrackingLocalState()

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return {
            "tracked_collections": self._local_state.tracked_collections,
            "position": self._local_state.position,
        }

    @state.setter
    def state(self, state: dict[str, Any]) -> None:
        self._local_state.tracked_collections = state["tracked_collections"]
        self._local_state.position = state["position"]

    def before_test_case_execution(self, test_case: tc.TestCase) -> None:
        """Reset tracking state before executing a test case.

        Args:
            test_case: The test case being executed.
        """
        self._local_state.tracked_collections.clear()
        self._local_state.position = 0

    def after_statement_execution(
        self,
        statement: tc.Statement,
        executor: TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        """Wrap Pynguin-created collections in tracked wrappers.

        Args:
            statement: The statement that was executed.
            executor: The test case executor.
            namespace: The execution namespace.
            exception: The exception raised, if any.
        """
        position = self._local_state.position
        self._local_state.position = position + 1

        if exception is not None:
            return

        bound_variable = statement.bound_variable
        if bound_variable is None or bound_variable not in namespace:
            return

        # Only track Pynguin-created literal/collection statements.
        if statement.accessible is not None:
            return

        val = namespace[bound_variable]
        if isinstance(val, list) and not isinstance(val, TrackedList):
            tracked_list = TrackedList(val)
            self._local_state.tracked_collections[position] = tracked_list
            namespace[bound_variable] = tracked_list
        elif isinstance(val, dict) and not isinstance(val, TrackedDict):
            tracked_dict = TrackedDict(val)
            self._local_state.tracked_collections[position] = tracked_dict
            namespace[bound_variable] = tracked_dict
        elif isinstance(val, tuple) and not isinstance(val, TrackedTuple):
            tracked_tuple = TrackedTuple(val)
            self._local_state.tracked_collections[position] = tracked_tuple
            namespace[bound_variable] = tracked_tuple

    def after_test_case_execution(
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ) -> None:
        """Transfer tracked collection access data to ExecutionResult.

        Args:
            executor: The test case executor.
            test_case: The executed test case.
            result: The execution result to populate.
        """
        for pos, tracked in self._local_state.tracked_collections.items():
            if isinstance(tracked, TrackedList | TrackedTuple):
                result.collection_trace[pos] = CollectionTrace(
                    max_accessed_index=tracked.max_accessed_index,
                    accessed_indices=set(tracked.accessed_indices),
                )
            elif isinstance(tracked, TrackedDict):
                result.collection_trace[pos] = CollectionTrace(
                    accessed_keys={k for k in tracked.accessed_keys if is_safe_key(k)},
                    missing_keys={k for k in tracked.missing_keys if is_safe_key(k)},
                )
