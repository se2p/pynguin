#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker
from pynguin.utils.statistics.timer import Timer


def test_singleton():
    tracker_1 = StatisticsTracker()
    tracker_2 = StatisticsTracker()
    assert tracker_1 is tracker_2


def test_tracker():
    tracker = StatisticsTracker()
    value = MagicMock(Timer)
    tracker.track_output_variable(RuntimeVariable.TotalTime, value)
    assert tracker.variables.get() == (RuntimeVariable.TotalTime, value)


def test_variables_generator():
    tracker = StatisticsTracker()
    value_1 = MagicMock(Timer)
    value_2 = MagicMock(Timer)
    tracker.track_output_variable(RuntimeVariable.TotalTime, value_1)
    tracker.track_output_variable(RuntimeVariable.TotalTime, value_2)
    result = [v for _, v in tracker.variables_generator]
    assert result == [value_1, value_2]
