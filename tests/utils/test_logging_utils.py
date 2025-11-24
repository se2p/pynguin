#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for logging utilities."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import pytest

from pynguin.cli import _setup_logging  # noqa: PLC2701
from pynguin.utils.logging_utils import OptionalWorkerFormatter, WorkerFormatting

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


def _make_isolated_logger(name: str) -> logging.Logger:
    """Create a logger that does not propagate to root handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # Remove any pre-existing handlers to isolate the logger between tests.
    for h in list(logger.handlers):
        logger.removeHandler(h)
    return logger


def test_optional_worker_formatter_switches_based_on_worker_presence() -> None:
    """Formatter should use the respective format with or without a worker field."""
    fmt = OptionalWorkerFormatter(
        fmt_with_worker="W:%(worker)s %(message)s",
        fmt_without_worker="NW:%(message)s",
        datefmt=None,
    )

    with_worker = logging.makeLogRecord({"msg": "hello", "worker": "[A]"})
    without_worker = logging.makeLogRecord({"msg": "hello"})
    empty_worker = logging.makeLogRecord({"msg": "hello", "worker": ""})

    assert fmt.format(with_worker) == "W:[A] hello"
    assert fmt.format(without_worker) == "NW:hello"
    assert fmt.format(empty_worker) == "NW:hello"


def test_worker_formatting_injects_tag_and_restores_factory() -> None:
    """`WorkerFormatting` injects a tag during its scope and restores after exit."""
    logger = _make_isolated_logger("pynguin.tests.logging.workerfmt")
    stream = io.StringIO()

    # Use OptionalWorkerFormatter so formatting still works when no worker is present.
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        OptionalWorkerFormatter(
            fmt_with_worker="%(worker)s %(message)s",
            fmt_without_worker="%(message)s",
            datefmt=None,
        )
    )
    logger.addHandler(handler)

    with WorkerFormatting(tag="[Tag]"):
        logger.info("hello")

    # During the context, a worker tag should be present.
    output_lines = [line for line in stream.getvalue().splitlines() if line]
    assert output_lines[-1] == "[Tag] hello"

    # After leaving the context manager, the previous factory must be restored
    # and no worker should be injected automatically.
    stream.truncate(0)
    stream.seek(0)
    logger.info("bye")
    output_lines = [line for line in stream.getvalue().splitlines() if line]
    assert output_lines[-1] == "bye"

    # Cleanup handler
    logger.removeHandler(handler)


@pytest.mark.parametrize(
    ("no_rich", "worker_set"),
    [
        (True, False),
        (True, True),
        (False, False),
        (False, True),
    ],
)
def test_logging_with_and_without_rich_and_worker(
    capsys: CaptureFixture[str], *, no_rich: bool, worker_set: bool
) -> None:
    """Test that logging works with and without rich and with and without worker tag."""
    _setup_logging(verbosity=1, no_rich=no_rich, log_file=None)

    message = "hello"
    if worker_set:
        logging.info(message, extra={"worker": "[W]"})  # noqa: LOG015
    else:
        logging.info(message)  # noqa: LOG015

    # Handlers write to stderr by default (both StreamHandler and Rich Console).
    captured = capsys.readouterr()
    text = captured.out + captured.err

    assert message in text
    if worker_set:
        assert "[W]" in text
    else:
        assert "[W]" not in text
