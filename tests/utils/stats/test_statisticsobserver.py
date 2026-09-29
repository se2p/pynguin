#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.utils.statistics.statisticsobserver as sso


def test_coverage_over_time_observer_records_one_sample_per_iteration():
    observer = sso.CoverageOverTimeObserver()
    first = MagicMock()
    first.get_coverage.return_value = 0.5
    second = MagicMock()
    second.get_coverage.return_value = 0.75

    observer.before_search_start(1_000_000_000)
    observer.after_search_iteration(first)
    observer.after_search_iteration(second)

    assert len(observer.coverage_samples) == 2
    assert observer.coverage_samples[0][1] == 0.5
    assert observer.coverage_samples[1][1] == 0.75


def test_coverage_over_time_observer_elapsed_seconds_relative_to_search_start():
    observer = sso.CoverageOverTimeObserver()
    best = MagicMock()
    best.get_coverage.return_value = 1.0

    observer.before_search_start(5_000_000_000)
    observer.after_search_iteration(best)

    elapsed_seconds, _ = observer.coverage_samples[0]
    assert elapsed_seconds >= 0


def test_coverage_over_time_observer_records_nothing_before_any_iteration():
    observer = sso.CoverageOverTimeObserver()

    observer.before_search_start(0)

    assert observer.coverage_samples == []
