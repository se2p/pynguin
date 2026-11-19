#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provide message transport between island processes.

Supports direct sends, broadcasts, and non-blocking receives. Migration
triggers and migrant selection are handled by the calling components.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import queue
from typing import TYPE_CHECKING, Any

from multiprocess.reduction import ForkingPickler

from pynguin.testcase.execution_result import ExecutionResult
from pynguin.utils.type_utils import is_multiprocess_picklable

if TYPE_CHECKING:
    import multiprocess.managers as mp_managers

    import pynguin.ga.coveragegoals as bg
    import pynguin.testcase.testcase as tc


def compute_test_case_hash(test_case: tc.TestCase) -> str:
    """Return a stable hash for a test case.

    The hash is computed from the test case source representation so equivalent
    tests produce the same value across processes.

    Args:
        test_case: The test case to hash.

    Returns:
        The SHA-256 digest of the test case source.
    """
    return hashlib.sha256(test_case.to_code().encode()).hexdigest()


_can_part_be_sent = functools.cache(is_multiprocess_picklable)


def pack(message: object) -> bytes:
    """Pickle a message to put it into a Manager queue.

    A Manager queue unpickles what is put into it and pickles it again for every
    get. Pickling a test case again in the Manager process can pull in whole
    module namespaces, which takes very long and can exhaust the memory. Messages
    therefore pass through the queues as bytes that the Manager does not unpickle.

    Args:
        message: The message to put into a Manager queue.

    Returns:
        The pickled message.
    """
    return bytes(ForkingPickler.dumps(message))


def unpack(raw: bytes) -> Any:
    """Unpickle a message taken from a Manager queue.

    Args:
        raw: The pickled message, as created by pack().

    Returns:
        The message.
    """
    return ForkingPickler.loads(raw)


def portable_test_case(test_case: tc.TestCase) -> tc.TestCase | None:
    """Return a copy of a test case that can be sent to another process.

    Test cases are pickled when they cross process boundaries, and pickle refers
    to classes and type variables by their module attribute. A statement whose
    callable signature or bound type uses one that is not reachable that way,
    e.g. a TypeVar not stored under its own name or an internal builtin type,
    therefore cannot be pickled. The copy drops such a callable or type: the
    statement keeps its code and becomes an unresolved call, like the ones the
    LLM test deserializer creates. The check uses the pickler multiprocess sends
    with, which differs from the standard one in what it can pickle.

    Args:
        test_case: The test case to send.

    Returns:
        The copy, or None if it cannot be pickled even so.
    """
    copy = test_case.clone()
    for index, statement in enumerate(copy.statements()):
        accessible = statement.accessible if _can_part_be_sent(statement.accessible) else None
        bound_type = statement.bound_type if _can_part_be_sent(statement.bound_type) else None
        if accessible is not statement.accessible or bound_type is not statement.bound_type:
            copy.replace_statement(
                index,
                dataclasses.replace(statement, accessible=accessible, bound_type=bound_type),
            )
    return copy if is_multiprocess_picklable(copy) else None


def portable_execution_result(result: ExecutionResult) -> ExecutionResult | None:
    """Return the parts of an execution result the final merge reuses, sendable.

    The merge computes coverage from the execution results the islands recorded
    during their search instead of executing the test cases again: a test case can
    cover a branch only because of state an earlier test case of the same search
    left behind, so its coverage changes when it runs again in another process.
    The copy keeps the execution trace, the timeout and the positions of the raised
    exceptions. It holds no object of the SUT: unpickling one runs SUT code, e.g.
    an exception's constructor, in the receiving process, outside any test
    execution. Each exception is therefore replaced by a plain one named after its
    type, and the trace drops the assertions it recorded, which can hold SUT values.

    Args:
        result: The execution result to send.

    Returns:
        The copy, or None if it cannot be pickled even so.
    """
    copy = ExecutionResult(timeout=result.timeout)
    copy.execution_trace = dataclasses.replace(result.execution_trace, executed_assertions=[])
    for position, exception in result.exceptions.items():
        copy.report_new_thrown_exception(position, Exception(type(exception).__name__))
    return copy if is_multiprocess_picklable(copy) else None


@dataclasses.dataclass
class MigrationMessage:
    """One migrated test case, sent by the island or LLM worker that found it."""

    source_island: int
    covered_goal: bg.BranchGoal | None
    content_hash: str
    test_case: tc.TestCase


class MigrationChannel:
    """One island's view of the migration mailbox mesh.

    It holds the island's own inbox and every other island's inbox to broadcast into.
    """

    def __init__(self, island_id: int | None, inboxes: dict[int, mp_managers.BaseProxy]) -> None:
        """Creates a channel for one island, or a broadcast-only.

        Args:
            island_id: This island's own id, or None for a broadcast-only channel
                with no island of its own (see for_broadcaster()).
            inboxes: Every island's inbox, keyed by island id.
        """
        self._island_id = island_id
        self._inboxes = inboxes
        if island_id is None:
            self._own_inbox = None
            self._other_inboxes = list(inboxes.values())
        else:
            self._own_inbox = inboxes[island_id]
            self._other_inboxes = [q for i, q in inboxes.items() if i != island_id]

    @classmethod
    def for_broadcaster(cls, inboxes: dict[int, mp_managers.BaseProxy]) -> MigrationChannel:
        """Builds a broadcast-only channel with no island of its own.

        Used by the LLM worker to deliver Global Broadcast Migration results to
        every island via the same mechanism peer-covered test cases use.

        Args:
            inboxes: Every island's inbox, keyed by island id.

        Returns:
            A channel that can only broadcast(), never drain_incoming().
        """
        return cls(None, inboxes)

    def open_connections(self) -> None:
        """Opens this thread's connection to the Manager holding the inboxes now.

        The inbox proxies otherwise open it on first use.
        """
        for inbox in self._inboxes.values():
            inbox.qsize()

    def broadcast(self, message: MigrationMessage) -> None:
        """Sends a message to every other island's inbox, not this island's own.

        Args:
            message: The message to broadcast.
        """
        raw = pack(message)
        for inbox in self._other_inboxes:
            inbox.put(raw)

    def send_to(self, destination_island_id: int, message: MigrationMessage) -> None:
        """Send a migration message to one island.

        Args:
            destination_island_id: The single island to deliver the message to.
            message: The message to send.
        """
        self._inboxes[destination_island_id].put(pack(message))

    def drain_incoming(self, max_messages: int = 256) -> list[MigrationMessage]:
        """Non-blockingly drains up to max_messages from this island's own inbox.

        Args:
            max_messages: Upper bound on how many messages to drain in one call, so
                a burst of migrants can't stall a generation indefinitely.

        Returns:
            The drained messages, oldest first; empty if nothing was waiting.
        """
        drained: list[MigrationMessage] = []
        for _ in range(max_messages):
            message = self._try_get_nowait()
            if message is None:
                break
            drained.append(message)
        return drained

    def _try_get_nowait(self) -> MigrationMessage | None:
        if self._own_inbox is None:
            return None
        try:
            return unpack(self._own_inbox.get_nowait())
        except queue.Empty:
            return None


def build_migration_inboxes(
    num_islands: int, manager: mp_managers.SyncManager
) -> dict[int, mp_managers.BaseProxy]:
    """Builds one shared inbox Queue per island.

    Args:
        num_islands: How many islands (and inboxes) to build.
        manager: Manager used to create the shared queues.

    Returns:
        One inbox per island id, 0..num_islands-1.
    """
    return {island_id: manager.Queue() for island_id in range(num_islands)}


def build_migration_channels(
    num_islands: int, manager: mp_managers.SyncManager
) -> dict[int, MigrationChannel]:
    """Builds one MigrationChannel per island, sharing one inbox per island.

    Args:
        num_islands: How many islands (and channels/inboxes) to build.
        manager: The Manager whose Queues back the inboxes.

    Returns:
        One channel per island id, 0..num_islands-1.
    """
    inboxes = build_migration_inboxes(num_islands, manager)
    return {island_id: MigrationChannel(island_id, inboxes) for island_id in range(num_islands)}
