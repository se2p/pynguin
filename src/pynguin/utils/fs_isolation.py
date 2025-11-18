#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Filesystem isolation utilities for executing SUT safely."""

from __future__ import annotations

from contextlib import ContextDecorator

from pyfakefs.fake_filesystem_unittest import FakeFilesystem
from pyfakefs.fake_filesystem_unittest import Patcher


class FilesystemIsolation(ContextDecorator):
    """Isolates filesystem side effects during test execution.

    Warning: Does also forbid read access to the real filesystem.

    Guarantees:
    - SUT cannot read or write the real filesystem.
    - All filesystem operations occur inside an in-memory fake FS.
    """

    def __init__(self) -> None:
        """Initialize the isolation context manager."""
        self._patcher: Patcher | None = None
        self.fs: FakeFilesystem | None = None

    def __enter__(self):
        """Enter the context manager."""
        self._patcher = Patcher()
        self._patcher.setUp()
        self.fs = self._patcher.fs
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exit the context manager."""
        if self._patcher:
            self._patcher.tearDown()
        return False
