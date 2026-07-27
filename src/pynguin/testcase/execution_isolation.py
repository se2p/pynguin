#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""OS-level isolation and output suppression helpers."""

from __future__ import annotations

import contextlib
import logging
import os
import random
import sys
import threading

import pynguin.configuration as config
from pynguin.utils import randomness


@contextlib.contextmanager
def suppress_logging():
    """Suppress all log messages during SUT execution.

    Yields:
        Nothing; restores logging on exit.
    """
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


class OutputSuppressionContext:
    """A context manager that suppresses stdout and stderr.

    Operates at two levels:

    - Python level: redirects ``sys.stdout`` / ``sys.stderr`` to ``/dev/null``.
    - OS level: saves file descriptors 0/1/2 via ``os.dup`` so that if the SUT
      closes them (e.g. ``with open(1, 'w')`` where the int happens to be a
      stdio fd), they are restored on exit.
    """

    # Repeatedly opening/closing devnull caused problems.
    # This is closed when Pynguin terminates, since we don't need this output
    # anyway this is acceptable.
    _null_file = open(os.devnull, mode="w")  # noqa: PLW1514, PTH123, SIM115

    def __init__(self) -> None:
        """Create a new context manager that suppress stdout and stderr."""
        self._restored = False
        self._restored_lock = threading.Lock()
        self._saved_fds: dict[int, int] = {}

    def restore(self) -> None:
        """Restore stdout and stderr at both Python and OS level."""
        with self._restored_lock:
            if self._restored:
                return
            self._restored = True
            # Restore OS-level fds first so that sys.__stdout__ / sys.__stderr__
            # point to live fds again before we reassign the Python objects.
            for fd, saved_fd in self._saved_fds.items():
                with contextlib.suppress(OSError):
                    os.dup2(saved_fd, fd)
                with contextlib.suppress(OSError):
                    os.close(saved_fd)
            self._saved_fds.clear()
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

    def __enter__(self) -> None:
        # Save OS-level fds before the SUT has a chance to close them.
        for fd in (0, 1, 2):
            with contextlib.suppress(OSError):
                self._saved_fds[fd] = os.dup(fd)
        sys.stdout = self._null_file
        sys.stderr = self._null_file

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.restore()


def _make_deterministic():
    """Make the execution deterministic.

    Reseed the module-level random and every SUT-related random.Random
    instance that was tracked by the _patch_random() hook.  Pynguin's own
    randomness.RNG is excluded so that Pynguin's own decisions remain
    unaffected.
    """
    seed = config.configuration.seeding.seed
    random.seed(seed)

    tracked = getattr(random.Random.seed, "__pynguin_instances__", None)
    if tracked is not None:
        for _inst in list(tracked):
            if _inst is not randomness.RNG:
                _inst.seed(seed)


class PatchRandomOnUnpickle:
    """A hook that patches random when unpickled in a subprocess.

    This ensures that random.Random.seed is patched before the SUT is unpickled
    and potentially creates new random.Random instances (e.g., mimesis).
    """

    def __init__(self):
        """Create a new hook."""
        self._config = config.configuration

    def __getstate__(self):
        return {"config": self._config}

    def __setstate__(self, state):
        config.configuration = state["config"]
        from pynguin.generator import _patch_random  # noqa: PLC0415

        _patch_random()
