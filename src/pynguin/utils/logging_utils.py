#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Logging utilities for Pynguin.

This module centralizes logging format strings and provides helpers for
conditional worker-aware formatting and safe scoping of LogRecordFactory
changes.
"""

from __future__ import annotations

import logging
import os
from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable


DATE_LOG_FORMAT: Final[str] = "[%X]"
NO_WORKER_LOG_FORMAT: Final[str] = (
    "%(asctime)s [%(levelname)s](%(name)s:%(funcName)s:%(lineno)d): %(message)s"
)
WORKER_LOG_FORMAT: Final[str] = (
    "%(asctime)s [%(levelname)s] %(worker)s(%(name)s:%(funcName)s:%(lineno)d): %(message)s"
)
RICH_WORKER_LOG_FORMAT: Final[str] = "%(worker)s %(message)s"
RICH_NO_WORKER_LOG_FORMAT: Final[str] = "%(message)s"


class OptionalWorkerFormatter(logging.Formatter):
    """Formatter that conditionally includes the worker field.

    If a log record contains a non-empty attribute ``worker``, the formatter uses a
    format string that includes the worker. Otherwise, it falls back to a format
    that omits the worker.
    """

    def __init__(
        self,
        fmt_with_worker: str = WORKER_LOG_FORMAT,
        fmt_without_worker: str = NO_WORKER_LOG_FORMAT,
        datefmt: str | None = DATE_LOG_FORMAT,
    ) -> None:
        """Initialize the formatter.

        Args:
            fmt_with_worker: Format string used when ``record.worker`` is present.
            fmt_without_worker: Format string used when no worker is present.
            datefmt: Optional date format for the underlying formatters.
        """
        super().__init__()
        self._with_worker = logging.Formatter(fmt_with_worker, datefmt=datefmt)
        self._without_worker = logging.Formatter(fmt_without_worker, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record based on the presence of the worker attribute."""
        if getattr(record, "worker", None):
            return self._with_worker.format(record)
        return self._without_worker.format(record)


class WorkerFormatting(ContextDecorator):
    """Temporarily install a LogRecordFactory that injects ``record.worker``.

    Can be used both as a context manager and as a decorator. Restores the
    previously configured factory on exit, even if an exception occurs.
    """

    _FALLBACK_WORKER_ID: Final[int] = 10000

    def __init__(self, tag: str | Callable[[], str] | None = None) -> None:
        """Initialize the context manager."""
        self._tag: str | Callable[[], str]
        if tag is None:
            self._tag = lambda: f"[Worker-{os.getpid() or self._FALLBACK_WORKER_ID}]"
        else:
            self._tag = tag
        self._old_factory: Callable[..., logging.LogRecord] | None = None
        self._installed_factory: Callable[..., logging.LogRecord] | None = None

    def __enter__(self):
        """Install the factory and return self."""
        old = logging.getLogRecordFactory()
        self._old_factory = old

        def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = old(*args, **kwargs)
            if not getattr(record, "worker", None):
                tag_val = self._tag() if callable(self._tag) else self._tag
                record.worker = tag_val
            return record

        logging.setLogRecordFactory(factory)
        self._installed_factory = factory
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Restore the previous factory."""
        if self._old_factory is not None:
            logging.setLogRecordFactory(self._old_factory)
        self._old_factory = None
        self._installed_factory = None
