#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Timeout helper for guarding in-process execution of SUT-controlled code."""

import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pynguin.configuration as config


class TestExecutionTimeoutError(BaseException):
    """Raised when guarded code exceeds its execution time limit.

    Inherits from :class:`BaseException` rather than :class:`Exception` so that a
    ``try: ... except Exception:`` block inside the guarded code cannot swallow it --
    the whole point is that runaway code must not be able to keep running.
    """


def resolve_timeout(timeout: float | None) -> float:
    """Resolve an explicit timeout against the configured per-test execution timeout.

    Args:
        timeout: An explicit timeout in seconds, or *None* to use the configured
            ``stopping.maximum_test_execution_timeout``.

    Returns:
        The timeout in seconds; values <= 0 disable the limit.
    """
    if timeout is not None:
        return timeout
    try:
        val = config.configuration.stopping.maximum_test_execution_timeout
        if isinstance(val, (int, float)):
            return float(val)
    except AttributeError:
        pass
    return 5.0


def resolve_module_timeout(timeout: float | None = None) -> float:
    """Resolve an explicit timeout against the configured module execution timeout.

    Args:
        timeout: An explicit timeout in seconds, or *None* to use the configured
            ``stopping.maximum_module_execution_timeout``.

    Returns:
        The timeout in seconds; values <= 0 disable the limit.
    """
    if timeout is not None:
        return timeout
    try:
        val = config.configuration.stopping.maximum_module_execution_timeout
        if isinstance(val, (int, float)):
            return float(val)
    except AttributeError:
        pass
    return 5.0


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """Abort the wrapped block with a :class:`TestExecutionTimeoutError` after *seconds*.

    Uses ``SIGALRM``, which is only available on POSIX and only settable from the main
    thread; the limit is silently skipped when either precondition does not hold, or
    when *seconds* is <= 0.

    Note:
        Signal handlers only run between bytecode instructions, so a block spending its
        time inside a single long-running C call (a pathological regular-expression
        match, say) is only interrupted once that call returns.

    Args:
        seconds: The time limit in seconds; <= 0 disables the limit.

    Yields:
        Nothing; the wrapped block runs under the time limit.
    """
    can_alarm = (
        isinstance(seconds, (int, float))
        and seconds > 0
        and hasattr(signal, "SIGALRM")
        and threading.current_thread() is threading.main_thread()
    )
    if not can_alarm:
        yield
        return

    def _handler(_signum, _frame):
        raise TestExecutionTimeoutError(f"Execution exceeded the {seconds}s time limit")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
