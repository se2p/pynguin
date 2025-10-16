#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import patch

import pynguin.configuration as config

from pynguin.testcase.localsearch import LocalSearchTimer


def test_timer_limit_reached() -> None:
    with patch.object(LocalSearchTimer, "_instance", None):
        config.configuration.local_search.local_search_time = -1000000
        timer = LocalSearchTimer.get_instance()
        timer.start_local_search()
        assert timer.limit_reached()


def test_timer_limit_not_reached() -> None:
    with patch.object(LocalSearchTimer, "_instance", None):
        config.configuration.local_search.local_search_time = 1000000000
        timer = LocalSearchTimer.get_instance()
        timer.start_local_search()
        assert not timer.limit_reached()


def test_timer_not_started() -> None:
    with patch.object(LocalSearchTimer, "_instance", None):
        timer = LocalSearchTimer.get_instance()
        assert timer.limit_reached()
