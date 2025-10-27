#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import pynguin.configuration as config

from pynguin.testcase.localsearchtimer import LocalSearchTimer


def test_timer_limit_reached() -> None:
    config.configuration.local_search.local_search_time = -1000000
    timer = LocalSearchTimer()
    timer.start_timer()
    assert timer.limit_reached()


def test_timer_limit_not_reached() -> None:
    config.configuration.local_search.local_search_time = 1000000000
    timer = LocalSearchTimer()
    timer.start_timer()
    assert not timer.limit_reached()


def test_timer_not_started() -> None:
    timer = LocalSearchTimer()
    assert timer.limit_reached()
