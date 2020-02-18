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
import math
import re
import time

import pytest

from pynguin.utils.exceptions import TimerError
from pynguin.utils.statistics.timer import Timer

TIME_PREFIX = "Wasted time:"
TIME_MESSAGE = f"{TIME_PREFIX} {{:.4f}} seconds"
RE_TIME_MESSAGE = re.compile(TIME_PREFIX + r" 0\.\d{4} seconds")


def waste_time(num=1000):
    """Just waste a little bit of time."""
    sum(n ** 2 for n in range(num))


@Timer(text=TIME_MESSAGE)
def decorated_time_waste(num=1000):
    """Just waste a little bit of time."""
    sum(n ** 2 for n in range(num))


@Timer(name="accumulator", text=TIME_MESSAGE)
def accumulated_time_waste(num=1000):
    """Just waste a little bit of time."""
    sum(n ** 2 for n in range(num))


class CustomLogger:
    """Simple class used to test custom logging capabilities in Timer."""

    def __init__(self):
        self.messages = ""

    def __call__(self, message):
        self.messages += message


def test_timer_as_decorator(capsys):
    decorated_time_waste()
    stdout, stderr = capsys.readouterr()
    assert RE_TIME_MESSAGE.match(stdout)
    assert stdout.count("\n") == 1
    assert stderr == ""


def test_timer_as_context_manager(capsys):
    with Timer(text=TIME_MESSAGE):
        waste_time()
    stdout, stderr = capsys.readouterr()
    assert RE_TIME_MESSAGE.match(stdout)
    assert stdout.count("\n") == 1
    assert stderr == ""


def test_explicit_timer(capsys):
    t = Timer(text=TIME_MESSAGE)
    t.start()
    waste_time()
    t.stop()
    stdout, stderr = capsys.readouterr()
    assert RE_TIME_MESSAGE.match(stdout)
    assert stdout.count("\n") == 1
    assert stderr == ""


def test_error_if_timer_not_running():
    t = Timer(text=TIME_MESSAGE)
    with pytest.raises(TimerError):
        t.stop()


def test_access_timer_object_in_context(capsys):
    with Timer(text=TIME_MESSAGE) as t:
        assert isinstance(t, Timer)
        assert t.text.startswith(TIME_PREFIX)
    _, _ = capsys.readouterr()  # Do not print log message to standard out


def test_custom_logger():
    logger = CustomLogger()
    with Timer(text=TIME_MESSAGE, logger=logger):
        waste_time()
    assert RE_TIME_MESSAGE.match(logger.messages)


def test_timer_without_text(capsys):
    with Timer(logger=None):
        waste_time()
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""


def test_accumulated_decorator(capsys):
    accumulated_time_waste()
    accumulated_time_waste()
    stdout, stderr = capsys.readouterr()
    lines = stdout.strip().split("\n")
    assert len(lines) == 2
    assert RE_TIME_MESSAGE.match(lines[0])
    assert RE_TIME_MESSAGE.match(lines[1])
    assert stderr == ""


def text_accumulated_contextmanager(capsys):
    t = Timer(name="accumulator", text=TIME_MESSAGE)
    with t:
        waste_time()
    with t:
        waste_time()
    stdout, stderr = capsys.readouterr()
    lines = stdout.strip().split("\n")
    assert len(lines) == 2
    assert RE_TIME_MESSAGE.match(lines[0])
    assert RE_TIME_MESSAGE.match(lines[1])
    assert stderr == ""


def test_accumulated_explicit_timer(capsys):
    t = Timer(name="accumulated_explicit_timer", text=TIME_MESSAGE)
    total = 0
    t.start()
    waste_time()
    total += t.stop()
    t.start()
    waste_time()
    total += t.stop()
    stdout, stderr = capsys.readouterr()
    lines = stdout.strip().split("\n")
    assert len(lines) == 2
    assert RE_TIME_MESSAGE.match(lines[0])
    assert RE_TIME_MESSAGE.match(lines[1])
    assert stderr == ""
    assert total == Timer.timers["accumulated_explicit_timer"]


def test_error_if_restarting_running_timer():
    t = Timer(text=TIME_MESSAGE)
    t.start()
    with pytest.raises(TimerError):
        t.start()


def test_last_starts_as_nan():
    t = Timer()
    assert math.isnan(t.last)


def test_timer_sets_last():
    with Timer() as t:
        time.sleep(0.02)
    assert t.last >= 0.02


def test_timers_cleared():
    with Timer(name="timer_to_be_cleared"):
        waste_time()
    assert "timer_to_be_cleared" in Timer.timers
    Timer.timers.clear()
    assert not Timer.timers


def test_running_cleared_timers():
    t = Timer(name="timer_to_be_cleared")
    Timer.timers.clear()

    accumulated_time_waste()
    with t:
        waste_time()

    assert "accumulator" in Timer.timers
    assert "timer_to_be_cleared" in Timer.timers


def test_timers_stats():
    name = "timer_with_stats"
    t = Timer(name=name)
    for num in range(5, 10):
        with t:
            waste_time(num=100 * num)

    stats = Timer.timers
    assert stats.total(name) == stats[name]
    assert stats.count(name) == 5
    assert stats.min(name) <= stats.median(name) <= stats.max(name)
    assert stats.mean(name) >= stats.min(name)
    assert stats.std_dev(name) >= 0


def test_stats_missing_timers():
    with pytest.raises(KeyError):
        Timer.timers.count("non_existent_timer")
    with pytest.raises(KeyError):
        Timer.timers.std_dev("non_existent_timer")


def test_setting_timers_exception():
    with pytest.raises(TypeError):
        Timer.timers["set_timer"] = 1.23
