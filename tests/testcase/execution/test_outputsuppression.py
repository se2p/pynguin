#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import contextlib
import os
import sys
from unittest.mock import patch

import pytest

from pynguin.testcase.execution import OutputSuppressionContext


@pytest.fixture
def _protected_fds():
    """Save and restore fds 0/1/2 around the test to prevent cross-test corruption.

    Used by tests that deliberately close stdio fds inside a
    OutputSuppressionContext.  If the test assertion fails *after* the context
    has already restored the fd, this fixture is a no-op safety net.  If the
    context itself fails to restore a fd, this fixture ensures the rest of the
    suite still sees a healthy process.
    """
    saved: dict[int, int] = {}
    for fd in (0, 1, 2):
        with contextlib.suppress(OSError):
            saved[fd] = os.dup(fd)
    yield
    for fd, saved_fd in saved.items():
        with contextlib.suppress(OSError):
            os.dup2(saved_fd, fd)
        with contextlib.suppress(OSError):
            os.close(saved_fd)


def test_stdout_redirected_inside_context():
    with OutputSuppressionContext():
        assert sys.stdout is not sys.__stdout__


def test_stderr_redirected_inside_context():
    with OutputSuppressionContext():
        assert sys.stderr is not sys.__stderr__


def test_stdout_restored_after_context():
    with OutputSuppressionContext():
        pass
    assert sys.stdout is sys.__stdout__


def test_stderr_restored_after_context():
    with OutputSuppressionContext():
        pass
    assert sys.stderr is sys.__stderr__


@pytest.mark.usefixtures("_protected_fds")
def test_fd1_restored_after_close_inside_context():
    """Fd 1 (stdout) survives being closed by SUT code inside the context."""
    os.fstat(1)  # pre-check: must be open

    with OutputSuppressionContext():
        os.close(1)
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(1)  # confirm it really is closed

    # OutputSuppressionContext.__exit__ must have restored fd 1
    os.fstat(1)


@pytest.mark.usefixtures("_protected_fds")
def test_fd2_restored_after_close_inside_context():
    """Fd 2 (stderr) survives being closed by SUT code inside the context."""
    os.fstat(2)

    with OutputSuppressionContext():
        os.close(2)
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(2)

    os.fstat(2)


@pytest.mark.usefixtures("_protected_fds")
def test_multiple_fds_restored_after_close():
    """Both fd 1 and fd 2 are restored when closed simultaneously."""
    os.fstat(1)
    os.fstat(2)

    with OutputSuppressionContext():
        os.close(1)
        os.close(2)

    os.fstat(1)
    os.fstat(2)


@pytest.mark.usefixtures("_protected_fds")
def test_fd_replaced_inside_context_is_restored():
    """If SUT replaces fd 1 via dup2, the original is restored on exit."""
    # Record what fd 1 currently points to
    orig_stat = os.fstat(1)

    with OutputSuppressionContext():
        # Replace fd 1 with /dev/null — simulates a SUT that redirects stdout
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, 1)
        os.close(devnull_fd)

    # After exit, fd 1 should be back to the original
    assert os.fstat(1) == orig_stat


def test_already_closed_fd_does_not_crash():
    """__enter__ and __exit__ are safe when a fd is already closed.

    We mock os.dup to simulate fd 0 being closed before the context is entered.
    The context must not raise on either __enter__ or __exit__.
    """
    real_dup = os.dup

    def dup_raising_on_0(fd):
        if fd == 0:
            raise OSError(9, "Bad file descriptor")
        return real_dup(fd)

    with patch("os.dup", side_effect=dup_raising_on_0), OutputSuppressionContext():
        pass  # must not raise


@pytest.mark.usefixtures("_protected_fds")
def test_explicit_restore_restores_fds():
    """Calling restore() directly (timeout path) restores fds and Python objects."""
    ctx = OutputSuppressionContext()
    ctx.__enter__()  # noqa: PLC2801

    os.close(1)  # simulate SUT closing stdout

    ctx.restore()

    # fd 1 and Python stdout must both be back
    os.fstat(1)
    assert sys.stdout is sys.__stdout__


def test_restore_is_idempotent():
    """Calling restore() multiple times never raises."""
    ctx = OutputSuppressionContext()
    ctx.__enter__()  # noqa: PLC2801
    ctx.restore()
    ctx.restore()  # second call: _restored flag is True, must be a no-op
    assert sys.stdout is sys.__stdout__


def test_restore_then_exit_is_safe():
    """restore() followed by __exit__ (the timeout cleanup sequence) is safe."""
    ctx = OutputSuppressionContext()
    ctx.__enter__()  # noqa: PLC2801
    ctx.restore()
    ctx.__exit__(None, None, None)
    assert sys.stdout is sys.__stdout__
