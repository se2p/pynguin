#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import dataclasses

import multiprocess as mp

from pynguin.analyses.module import generate_test_cluster
from pynguin.islands.llm_worker_protocol import (
    LLMWorkerResult,
    StatusReport,
    build_llm_worker_channels,
    callable_first_line,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)


@dataclasses.dataclass
class _FakeTestCase:
    source: str

    def to_code(self) -> str:
        return self.source


def _fake_result(target_island: int, first_line: int) -> LLMWorkerResult:
    return LLMWorkerResult(
        target_island=target_island,
        first_line=first_line,
        test_case=_FakeTestCase("def test_0():\n    pass\n"),  # type: ignore[arg-type]
        content_hash="deadbeef",
    )


def test_callable_first_line_matches_inspect_for_real_module():
    cluster = generate_test_cluster("tests.fixtures.cluster.no_dependencies")
    functions = [
        gao
        for gao in cluster.accessible_objects_under_test
        if isinstance(gao, GenericCallableAccessibleObject)
        and gao.callable.__name__ == "a_test_function"
    ]

    assert len(functions) == 1
    assert callable_first_line(functions[0]) == 17


def test_build_llm_worker_channels_returns_one_channel_and_inbox_per_island():
    with mp.Manager() as manager:
        status_queue, result_inboxes, channels = build_llm_worker_channels(3, manager)

        assert set(result_inboxes.keys()) == {0, 1, 2}
        assert set(channels.keys()) == {0, 1, 2}
        assert status_queue.empty()


def test_report_reaches_shared_status_queue():
    with mp.Manager() as manager:
        status_queue, _result_inboxes, channels = build_llm_worker_channels(2, manager)
        status = StatusReport(island_id=0, first_line=17, coverage=0.5, covered=False)

        channels[0].report(status)

        assert status_queue.get_nowait() == status


def test_drain_incoming_delivers_only_to_the_addressed_island():
    with mp.Manager() as manager:
        _status_queue, result_inboxes, channels = build_llm_worker_channels(2, manager)
        result = _fake_result(target_island=1, first_line=17)
        result_inboxes[1].put(result)

        assert channels[1].drain_incoming() == [result]
        assert channels[0].drain_incoming() == []


def test_drain_incoming_is_non_blocking_and_empty_by_default():
    with mp.Manager() as manager:
        _status_queue, _result_inboxes, channels = build_llm_worker_channels(1, manager)
        assert channels[0].drain_incoming() == []
