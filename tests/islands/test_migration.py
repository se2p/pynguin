#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import dataclasses
import pickle  # noqa: S403
import typing
from unittest.mock import MagicMock

import multiprocess as mp
import pytest

from pynguin.islands.migration import (
    MigrationChannel,
    MigrationMessage,
    build_migration_channels,
    build_migration_inboxes,
    compute_test_case_hash,
    pack,
    portable_execution_result,
    portable_test_case,
    unpack,
)
from pynguin.testcase.execution_result import ExecutionResult
from tests.testcase._builders import assign, int_stmt, make_test_case, stmt


@dataclasses.dataclass
class _FakeTestCase:
    """A plain, picklable stand-in for TestCase.

    MagicMock isn't picklable, and these messages cross a real Manager().Queue().
    """

    source: str

    def to_code(self) -> str:
        return self.source


def _fake_message(source_island: int, source: str) -> MigrationMessage:
    test_case = _FakeTestCase(source)
    return MigrationMessage(
        source_island=source_island,
        covered_goal=f"goal-for-{source}",  # type: ignore[arg-type]
        content_hash=compute_test_case_hash(test_case),  # type: ignore[arg-type]
        test_case=test_case,  # type: ignore[arg-type]
    )


def test_compute_test_case_hash_is_stable_for_identical_source():
    first = _FakeTestCase("def test_0():\n    pass\n")
    second = _FakeTestCase("def test_0():\n    pass\n")
    assert compute_test_case_hash(first) == compute_test_case_hash(second)  # type: ignore[arg-type]


def test_compute_test_case_hash_differs_for_different_source():
    a = _FakeTestCase("def test_0():\n    pass\n")
    b = _FakeTestCase("def test_1():\n    pass\n")
    assert compute_test_case_hash(a) != compute_test_case_hash(b)  # type: ignore[arg-type]


def test_build_migration_channels_returns_one_per_island():
    with mp.Manager() as manager:
        channels = build_migration_channels(3, manager)
        assert set(channels.keys()) == {0, 1, 2}


def test_broadcast_reaches_other_islands_not_sender():
    with mp.Manager() as manager:
        channels = build_migration_channels(3, manager)
        message = _fake_message(0, "def test_0():\n    pass\n")

        channels[0].broadcast(message)

        assert channels[1].drain_incoming() == [message]
        assert channels[2].drain_incoming() == [message]
        assert channels[0].drain_incoming() == []


def test_drain_incoming_is_non_blocking_and_empty_by_default():
    with mp.Manager() as manager:
        channels = build_migration_channels(2, manager)
        assert channels[0].drain_incoming() == []


def test_drain_incoming_respects_max_messages():
    with mp.Manager() as manager:
        channels = build_migration_channels(2, manager)
        for i in range(5):
            channels[1].broadcast(_fake_message(1, f"def test_{i}():\n    pass\n"))

        first_batch = channels[0].drain_incoming(max_messages=3)
        remaining = channels[0].drain_incoming()

        assert len(first_batch) == 3
        assert len(remaining) == 2


def test_broadcaster_delivers_to_every_island():
    with mp.Manager() as manager:
        inboxes = build_migration_inboxes(3, manager)
        broadcaster = MigrationChannel.for_broadcaster(inboxes)
        islands = {island_id: MigrationChannel(island_id, inboxes) for island_id in range(3)}
        message = _fake_message(-1, "def test_0():\n    pass\n")

        broadcaster.broadcast(message)

        assert islands[0].drain_incoming() == [message]
        assert islands[1].drain_incoming() == [message]
        assert islands[2].drain_incoming() == [message]


def test_broadcaster_has_no_own_inbox_to_drain():
    with mp.Manager() as manager:
        inboxes = build_migration_inboxes(2, manager)
        broadcaster = MigrationChannel.for_broadcaster(inboxes)
        assert broadcaster.drain_incoming() == []


def test_messages_pass_through_the_manager_as_bytes():
    with mp.Manager() as manager:
        inboxes = build_migration_inboxes(2, manager)
        message = _fake_message(0, "def test_0():\n    pass\n")

        MigrationChannel(0, inboxes).broadcast(message)

        raw = inboxes[1].get_nowait()
        assert isinstance(raw, bytes)
        assert unpack(raw) == message


def test_send_to_reaches_only_the_named_destination():
    with mp.Manager() as manager:
        channels = build_migration_channels(4, manager)
        message = _fake_message(0, "def test_0():\n    pass\n")

        channels[0].send_to(1, message)

        assert channels[1].drain_incoming() == [message]
        assert channels[2].drain_incoming() == []
        assert channels[3].drain_incoming() == []
        assert channels[0].drain_incoming() == []


def test_portable_test_case_keeps_a_picklable_test_case_unchanged():
    test_case = make_test_case(int_stmt("int_0", 3), assign("list_0", "[int_0]", bound_type=list))

    portable = portable_test_case(test_case)

    assert portable is not None
    assert portable is not test_case
    assert portable.to_code() == test_case.to_code()
    assert [s.bound_type for s in portable.statements()] == [int, list]


def test_portable_test_case_drops_an_unpicklable_bound_type():
    test_case = make_test_case(
        assign("bytes_0", "b'ab'", bound_type=bytes),
        stmt("iterator_0 = iter(bytes_0)", "iterator_0", type(iter(b""))),
    )

    portable = portable_test_case(test_case)

    assert portable is not None
    assert [s.bound_type for s in portable.statements()] == [bytes, None]
    assert portable.to_code() == test_case.to_code()
    restored = pickle.loads(pickle.dumps(portable))  # noqa: S301
    assert restored.to_code() == test_case.to_code()


def test_portable_test_case_drops_an_unpicklable_accessible_and_keeps_the_original():
    call = stmt("int_0 = len('ab')", "int_0", int)
    call.accessible = typing.TypeVar("_Unreachable")  # type: ignore[assignment]
    test_case = make_test_case(call)

    portable = portable_test_case(test_case)

    assert portable is not None
    assert portable.statements()[0].accessible is None
    assert portable.statements()[0].bound_type is int
    assert test_case.statements()[0].accessible is call.accessible
    assert portable.to_code() == test_case.to_code()


def _multiprocess_pickles_functions_by_value() -> bool:
    """Whether multiprocess's dill can pickle a lambda, which dill 0.4 cannot on Python 3.15."""
    try:
        pack(lambda: None)
    except Exception:  # noqa: BLE001
        return False
    return True


def test_portable_test_case_keeps_an_accessible_only_the_multiprocess_pickler_can_send():
    if not _multiprocess_pickles_functions_by_value():
        pytest.skip("The multiprocess pickler cannot pickle functions by value on this Python")
    call = stmt("int_0 = len('ab')", "int_0", int)
    call.accessible = lambda: None  # type: ignore[assignment]

    portable = portable_test_case(make_test_case(call))

    assert portable is not None
    assert portable.statements()[0].accessible is call.accessible


def test_portable_test_case_returns_none_when_the_copy_is_still_unpicklable():
    statement = int_stmt("int_0", 3)
    statement.assertions.append(_ for _ in ())  # type: ignore[arg-type]

    assert portable_test_case(make_test_case(statement)) is None


class _RebuiltOnlyWithTwoArgumentsError(Exception):
    def __init__(self, first, second):
        super().__init__(first)
        self.second = second


def _result_with_exception(exception: BaseException) -> ExecutionResult:
    result = ExecutionResult(timeout=True)
    result.execution_trace.true_distances[0] = 0.0
    result.execution_trace.executed_assertions.append(MagicMock())
    result.report_new_thrown_exception(2, exception)
    return result


def test_portable_execution_result_keeps_the_coverage_timeout_and_exception_positions():
    result = _result_with_exception(ValueError("x"))

    portable = portable_execution_result(result)

    assert portable is not None
    assert portable.timeout
    assert portable.execution_trace.true_distances == {0: 0.0}
    assert portable.execution_trace.executed_assertions == []
    assert type(portable.exceptions[2]) is Exception
    assert portable.exceptions[2].args == ("ValueError",)
    assert portable.get_first_position_of_thrown_exception() == 2


def test_portable_execution_result_leaves_the_original_result_unchanged():
    result = _result_with_exception(ValueError("x"))

    portable_execution_result(result)

    assert len(result.execution_trace.executed_assertions) == 1
    assert isinstance(result.exceptions[2], ValueError)


def test_portable_execution_result_can_be_received_without_rebuilding_a_sut_exception():
    result = _result_with_exception(_RebuiltOnlyWithTwoArgumentsError("first", "second"))

    portable = portable_execution_result(result)

    assert portable is not None
    received = unpack(pack(portable))
    assert received.exceptions[2].args == ("_RebuiltOnlyWithTwoArgumentsError",)


def test_portable_execution_result_returns_none_when_the_trace_is_unpicklable():
    result = ExecutionResult()
    result.execution_trace.executed_instructions.append(_ for _ in ())  # type: ignore[arg-type]

    assert portable_execution_result(result) is None
