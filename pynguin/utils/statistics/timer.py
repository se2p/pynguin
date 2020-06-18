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
"""Definition of Timer

Based on the implementation of https://github.com/realpython/codetiming
"""
from __future__ import annotations

import math
import time
from contextlib import ContextDecorator
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Optional

from pynguin.utils.exceptions import TimerError
from pynguin.utils.statistics.timers import Timers


@dataclass
class Timer(ContextDecorator):
    """Time your code using a class, context manager, or decorator."""

    timers: ClassVar[Timers] = Timers()
    _start_time: Optional[float] = field(default=None, init=False, repr=False)
    name: Optional[str] = None
    text: str = "Elapsed time: {:0.4f} seconds"
    logger: Optional[Callable[[str], None]] = print
    last: float = field(default=math.nan, init=False, repr=False)

    def start(self) -> None:
        """Start a new timer.

        Raises:
            TimerError: in case a timer is already running
        """
        if self._start_time is not None:
            raise TimerError("Timer is running.  Use .stop() to stop it")
        self._start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop the timer and report the elapsed time.

        Returns:
            The elapsed time

        Raises:
            TimerError: in case no timer is running
        """
        if self._start_time is None:
            raise TimerError("Timer is not running.  Use .start() to start it")
        self.last = time.perf_counter() - self._start_time
        self._start_time = None
        if self.logger:
            self.logger(self.text.format(self.last))
        if self.name:
            self.timers.add(self.name, self.last)
        return self.last

    def __enter__(self) -> Timer:
        """Start a new timer as a context manager.

        Returns:
            The timer in the context
        """
        self.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        """Stop the context manager timer

        Args:
            exc_info: any execution information
        """
        self.stop()
