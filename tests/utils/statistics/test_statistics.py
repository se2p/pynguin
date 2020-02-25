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

from pynguin.utils.statistics.statistics import StatisticsTracker, RuntimeVariable
from pynguin.utils.statistics.timer import Timer


def test_singleton():
    tracker_1 = StatisticsTracker()
    tracker_2 = StatisticsTracker()
    assert tracker_1 is tracker_2


def test_runtime_variable():
    variable = RuntimeVariable.total_time
    assert variable.value == "Total time spent by Pynguin to generate tests"


def test_tracker():
    tracker = StatisticsTracker()
    value = MagicMock(Timer)
    tracker.track_output_variable(RuntimeVariable.total_time, value)
    assert tracker.variables.get() == (RuntimeVariable.total_time, value)
