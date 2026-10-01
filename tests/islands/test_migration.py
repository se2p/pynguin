#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import dataclasses

import multiprocess as mp

from pynguin.islands.migration import (
    MigrationChannel,
    MigrationMessage,
    build_migration_channels,
    build_migration_inboxes,
    compute_test_case_hash,
)


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


def test_send_to_reaches_only_the_named_destination():
    with mp.Manager() as manager:
        channels = build_migration_channels(4, manager)
        message = _fake_message(0, "def test_0():\n    pass\n")

        channels[0].send_to(1, message)

        assert channels[1].drain_incoming() == [message]
        assert channels[2].drain_incoming() == []
        assert channels[3].drain_incoming() == []
        assert channels[0].drain_incoming() == []
