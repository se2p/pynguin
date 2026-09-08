#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import math
from unittest.mock import MagicMock

import libcst as cst
import pytest

from pynguin.testcase.collection_tracker import (
    RemoteCollectionTrackingObserver,
    TrackedDict,
    TrackedList,
    TrackedTuple,
    is_safe_key,
)
from pynguin.testcase.execution_result import ExecutionResult
from pynguin.testcase.testcase import Statement


def test_is_safe_key():
    assert is_safe_key("key")
    assert is_safe_key(42)
    assert is_safe_key(math.pi)
    bool_key = True
    assert is_safe_key(bool_key)
    assert is_safe_key(b"bytes")
    # A lambda cannot be pickled by standard pickle
    assert not is_safe_key(lambda x: x)


def test_tracked_list_positive_indexing():
    lst = TrackedList([10, 20, 30])
    assert lst[0] == 10
    assert lst[2] == 30
    assert lst.accessed_indices == {0, 2}
    assert lst.max_accessed_index == 2


def test_tracked_list_out_of_bounds_positive_indexing():
    lst = TrackedList([10, 20])
    with pytest.raises(IndexError):
        _ = lst[5]
    assert 5 in lst.accessed_indices
    assert lst.max_accessed_index == 5


def test_tracked_list_negative_indexing_within_bounds():
    lst = TrackedList([10, 20, 30])
    assert lst[-1] == 30
    assert lst[-2] == 20
    assert lst.accessed_indices == {1, 2}
    assert lst.max_accessed_index == 2


def test_tracked_list_negative_indexing_out_of_bounds():
    lst = TrackedList([10, 20])
    with pytest.raises(IndexError):
        _ = lst[-3]
    # Length 2 list, -3 requires length at least 3, normalized to index 2
    assert 2 in lst.accessed_indices
    assert lst.max_accessed_index == 2


def test_tracked_list_slice_access():
    lst = TrackedList([0, 1, 2, 3, 4])
    sub = lst[1:3]
    assert sub == [1, 2]
    assert lst.accessed_indices == {1, 2}
    assert lst.max_accessed_index == 2


def test_tracked_list_setitem_and_delitem():
    lst = TrackedList([10, 20, 30])
    lst[1] = 99
    assert lst[1] == 99
    del lst[0]
    assert lst == [99, 30]
    assert lst.accessed_indices == {0, 1}


def test_tracked_list_setitem_slice():
    lst = TrackedList([0, 1, 2, 3])
    lst[1:3] = [10, 20]
    assert 1 in lst.accessed_indices
    assert 2 in lst.accessed_indices


def test_tracked_list_delitem_slice():
    lst = TrackedList([0, 1, 2, 3])
    del lst[1:3]
    assert 1 in lst.accessed_indices
    assert 2 in lst.accessed_indices


def test_tracked_list_iteration():
    lst = TrackedList([10, 20, 30])
    seen = []
    for x in lst:
        seen.append(x)
        if x == 20:
            break
    assert seen == [10, 20]
    assert lst.accessed_indices == {0, 1}
    assert lst.max_accessed_index == 1


def test_tracked_list_reversed():
    lst = TrackedList([10, 20, 30])
    rev = list(reversed(lst))
    assert rev == [30, 20, 10]
    assert lst.accessed_indices == {0, 1, 2}
    assert lst.max_accessed_index == 2


def test_tracked_list_pop():
    lst = TrackedList([10, 20, 30])
    val = lst.pop()
    assert val == 30
    assert 2 in lst.accessed_indices


def test_tracked_list_index_found():
    lst = TrackedList([10, 20, 30])
    idx = lst.index(20)
    assert idx == 1
    assert lst.accessed_indices == {0, 1}


def test_tracked_list_index_not_found():
    lst = TrackedList([10, 20, 30])
    with pytest.raises(ValueError, match="is not in list"):
        lst.index(99)
    assert lst.accessed_indices == {0, 1, 2}


def test_tracked_list_count():
    lst = TrackedList([10, 20, 10])
    cnt = lst.count(10)
    assert cnt == 2
    assert lst.accessed_indices == {0, 1, 2}


def test_tracked_list_contains():
    lst = TrackedList([10, 20, 30])
    assert 20 in lst
    assert lst.accessed_indices == {0, 1}
    assert 99 not in lst
    assert lst.accessed_indices == {0, 1, 2}


def test_tracked_list_remove():
    lst = TrackedList([10, 20, 30])
    lst.remove(20)
    assert lst == [10, 30]
    assert 0 in lst.accessed_indices
    assert 1 in lst.accessed_indices


def test_tracked_list_remove_not_found():
    lst = TrackedList([10, 20])
    with pytest.raises(ValueError, match="is not in list"):
        lst.remove(99)
    assert lst.accessed_indices == {0, 1}


def test_tracked_list_sort():
    lst = TrackedList([30, 10, 20])
    lst.sort()
    assert lst == [10, 20, 30]
    assert lst.accessed_indices == {0, 1, 2}


def test_tracked_tuple_indexing_and_out_of_bounds():
    t = TrackedTuple([10, 20])
    assert t[0] == 10
    assert t.accessed_indices == {0}
    assert t.max_accessed_index == 0
    with pytest.raises(IndexError):
        _ = t[5]
    assert 5 in t.accessed_indices
    assert t.max_accessed_index == 5


def test_tracked_tuple_negative_indexing():
    t = TrackedTuple([10, 20, 30])
    assert t[-1] == 30
    assert t.accessed_indices == {2}
    with pytest.raises(IndexError):
        _ = t[-4]
    assert 3 in t.accessed_indices


def test_tracked_tuple_slice_and_iter():
    t = TrackedTuple([0, 1, 2, 3])
    assert t[1:3] == (1, 2)
    assert t.accessed_indices == {1, 2}
    seen = list(t)
    assert seen == [0, 1, 2, 3]
    assert t.accessed_indices == {0, 1, 2, 3}


def test_tracked_tuple_reversed_and_contains():
    t = TrackedTuple([10, 20])
    assert list(reversed(t)) == [20, 10]
    assert 20 in t
    assert 99 not in t


def test_tracked_tuple_index_and_count():
    t = TrackedTuple([10, 20, 10])
    assert t.index(20) == 1
    assert t.count(10) == 2


def test_tracked_dict_getitem_existing_and_missing():
    d = TrackedDict({"a": 1, "b": 2})
    assert d["a"] == 1
    assert "a" in d.accessed_keys
    assert not d.missing_keys

    with pytest.raises(KeyError):
        _ = d["c"]
    assert "c" in d.accessed_keys
    assert "c" in d.missing_keys


def test_tracked_dict_get():
    d = TrackedDict({"a": 1})
    assert d.get("a") == 1
    assert d.get("missing", 42) == 42
    assert "missing" in d.missing_keys


def test_tracked_dict_contains():
    d = TrackedDict({"a": 1})
    assert "a" in d
    assert "b" not in d
    assert "b" in d.missing_keys


def test_tracked_dict_setitem_and_delitem():
    d = TrackedDict({"a": 1})
    d["b"] = 2
    assert "b" in d.accessed_keys
    del d["a"]
    assert "a" in d.accessed_keys

    with pytest.raises(KeyError):
        del d["missing"]
    assert "missing" in d.missing_keys


def test_tracked_dict_pop_and_setdefault():
    d = TrackedDict({"a": 1})
    assert d.pop("a") == 1
    assert d.pop("missing", 0) == 0
    assert "missing" in d.missing_keys

    assert d.setdefault("c", 3) == 3
    assert "c" in d.missing_keys
    assert d["c"] == 3


def test_tracked_dict_iter_items_values():
    d = TrackedDict({"x": 10, "y": 20})
    keys = list(d)
    assert set(keys) == {"x", "y"}
    assert d.accessed_keys == {"x", "y"}

    d.accessed_keys.clear()
    items = list(d.items())
    assert len(items) == 2
    assert d.accessed_keys == {"x", "y"}

    d.accessed_keys.clear()
    vals = list(d.values())
    assert len(vals) == 2
    assert d.accessed_keys == {"x", "y"}


def test_observer_workflow():
    observer = RemoteCollectionTrackingObserver()
    test_case = MagicMock()
    executor = MagicMock()
    namespace = {"var_0": [1, 2, 3], "var_1": {"k": "v"}, "var_2": (10, 20)}

    observer.before_test_case_execution(test_case)

    # Pynguin-created statement for var_0
    stmt_0 = Statement(
        node=cst.SimpleStatementLine(body=[]),
        bound_variable="var_0",
        bound_type=list,
        accessible=None,
    )
    observer.after_statement_execution(stmt_0, executor, namespace, None)
    assert isinstance(namespace["var_0"], TrackedList)

    # Pynguin-created statement for var_1
    stmt_1 = Statement(
        node=cst.SimpleStatementLine(body=[]),
        bound_variable="var_1",
        bound_type=dict,
        accessible=None,
    )
    observer.after_statement_execution(stmt_1, executor, namespace, None)
    assert isinstance(namespace["var_1"], TrackedDict)

    # Pynguin-created statement for var_2
    stmt_2 = Statement(
        node=cst.SimpleStatementLine(body=[]),
        bound_variable="var_2",
        bound_type=tuple,
        accessible=None,
    )
    observer.after_statement_execution(stmt_2, executor, namespace, None)
    assert isinstance(namespace["var_2"], TrackedTuple)

    # Simulate access by SUT
    _ = namespace["var_0"][1]
    _ = namespace["var_1"]["k"]
    _ = namespace["var_2"][0]

    result = ExecutionResult()
    observer.after_test_case_execution(executor, test_case, result)

    assert 0 in result.collection_trace
    assert result.collection_trace[0].max_accessed_index == 1
    assert 1 in result.collection_trace
    assert "k" in result.collection_trace[1].accessed_keys
    assert 2 in result.collection_trace
    assert result.collection_trace[2].max_accessed_index == 0


def test_observer_ignores_sut_returned_collections():
    observer = RemoteCollectionTrackingObserver()
    test_case = MagicMock()
    executor = MagicMock()
    namespace = {"var_0": [1, 2, 3]}

    observer.before_test_case_execution(test_case)

    # Statement with accessible object (SUT call)
    stmt = Statement(
        node=cst.SimpleStatementLine(body=[]),
        bound_variable="var_0",
        bound_type=list,
        accessible=MagicMock(),
    )
    observer.after_statement_execution(stmt, executor, namespace, None)
    # Should NOT be wrapped in TrackedList
    assert type(namespace["var_0"]) is list


def test_observer_state_roundtrip():
    observer = RemoteCollectionTrackingObserver()
    observer._local_state.position = 5
    t_list = TrackedList([1, 2])
    observer._local_state.tracked_collections[2] = t_list

    state = observer.state
    assert state["position"] == 5
    assert 2 in state["tracked_collections"]

    observer2 = RemoteCollectionTrackingObserver()
    observer2.state = state
    assert observer2._local_state.position == 5
    assert observer2._local_state.tracked_collections[2] is t_list
