# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest.mock import MagicMock

from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker
from pynguin.utils.statistics.timer import Timer


def test_singleton():
    tracker_1 = StatisticsTracker()
    tracker_2 = StatisticsTracker()
    assert tracker_1 is tracker_2


def test_runtime_variable():
    variable = RuntimeVariable.TotalTime
    assert variable.description == "Total time spent by Pynguin to generate tests"


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
