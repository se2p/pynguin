#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pynguin.configuration import configuration
from pynguin.testcase.localsearch import LocalSearchTimer


def test_timer_limit_reached(monkeypatch, result) -> None:
    monkeypatch.setattr("pynguin.config.LocalSearchConfiguration.local_search_time", -1)
    timer = LocalSearchTimer.get_instance()
    timer.start_local_search()
    assert timer.limit_reached()

def test_timer_limit_not_reached(monkeypatch, result) -> None:
    monkeypatch.setattr("pynguin.config.LocalSearchConfiguration.local_search_time", 1000000000)
    timer = LocalSearchTimer.get_instance()
    timer.start_local_search()
    assert not timer.limit_reached()

def test_timer_not_started(monkeypatch, result) -> None:
    timer = LocalSearchTimer.get_instance()
    assert timer.limit_reached()
