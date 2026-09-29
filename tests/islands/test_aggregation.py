#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.testcase.testcase as tc
from pynguin.generator import ReturnCode
from pynguin.islands import aggregation
from pynguin.islands.island import IslandResult


def _fake_test_case(source: str) -> tc.TestCase:
    test_case = MagicMock(spec=tc.TestCase)
    test_case.to_code.return_value = source
    return test_case


def test_deduplicate_by_source_drops_identical_test_cases():
    shared = _fake_test_case("def test_0():\n    pass\n")
    duplicate = _fake_test_case("def test_0():\n    pass\n")
    distinct = _fake_test_case("def test_1():\n    pass\n")
    results = [
        IslandResult(0, [shared, distinct], ReturnCode.OK),
        IslandResult(1, [duplicate], ReturnCode.OK),
    ]

    deduplicated = aggregation._deduplicate_by_source(results)

    assert len(deduplicated) == 2
    assert shared in deduplicated
    assert distinct in deduplicated
    assert duplicate not in deduplicated  # first-island-wins on a hash collision


def test_deduplicate_by_source_keeps_all_distinct_test_cases():
    test_cases = [_fake_test_case(f"def test_{i}():\n    pass\n") for i in range(3)]
    results = [IslandResult(0, test_cases, ReturnCode.OK)]

    deduplicated = aggregation._deduplicate_by_source(results)

    assert len(deduplicated) == 3


def test_deduplicate_by_source_handles_empty_results():
    assert aggregation._deduplicate_by_source([]) == []
    assert aggregation._deduplicate_by_source([IslandResult(0, [], ReturnCode.OK)]) == []
