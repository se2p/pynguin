#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A context manager for storing test cases before execution."""

from __future__ import annotations

import logging
import pickle  # noqa: S403

from pathlib import Path
from typing import TYPE_CHECKING

import pynguin.configuration as config

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.testcase import export
from pynguin.testcase.export import PyTestChromosomeToAstVisitor


if TYPE_CHECKING:
    import types

    from typing_extensions import Self

    import pynguin.testcase.testcase as tc

_LOGGER = logging.getLogger(__name__)


def store_binary(test_case: tc.TestCase, target_file: Path) -> None:
    """Store the test case as a binary file.

    Warning: Does not work for SUT classes. Thus do not use this!

    Args:
        test_case: The test case to store.
        target_file: The file to store the test case to.
    """
    try:
        with Path(target_file).open("wb") as f:
            pickle.dump(test_case, f)

    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Failed to pickle dump test case: %s", e)


def store_pytest(test_case: tc.TestCase, target_file: Path) -> None:
    """Store the test case as a pytest file.

    Args:
        test_case: The test case to store.
        target_file: The file to store the test case to.
    """
    try:
        chromosome = TestCaseChromosome(test_case)
        exporter = PyTestChromosomeToAstVisitor()
        chromosome.accept(exporter)
        export.save_module_to_file(exporter.to_module(), target_file, format_with_black=False)

    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Failed to export test case to code: %s", e)


class ExecutionRecorder:
    """A context manager to store the test case to be executed.

    Warning: Does not work for SUT classes. Thus do not use this!

    This recorder writes the test case to a file before execution and removes it after
    execution. If the test execution process causes Pynguin to crash, the file remains.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
    ) -> None:
        """Initialize the recorder.

        Args:
            test_case: The test case to record (will be converted to code)
        """
        self._test_case = test_case
        self._should_record = config.configuration.statistics_output.store_test_before_execution
        self._target_file = (
            Path(config.configuration.test_case_output.output_path).resolve()
            / "last_executed_test.py"
        )

        # Ensure the directory exists
        if self._should_record:
            self._target_file.parent.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> Self:
        """Write the test case to the recording file before execution."""
        if not self._should_record:
            return self
        store_pytest(self._test_case, self._target_file)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        """Delete the recording file after successful execution."""
        if not self._should_record:
            return

        try:
            if self._target_file.exists():
                self._target_file.unlink()
                _LOGGER.debug("Test executed successfully, removed '%s'", self._target_file)
        except OSError as e:
            _LOGGER.error("Failed to remove recording file '%s': %s", self._target_file, e)


class OnceOpeningExecutionRecorder:
    """A recorder to store the test case to be executed. Keeps the file to write to open.

    This recorder writes the test case to a file and keeps the file open. If requested,
    the file is closed or all content is removed.

    Does not speed things up compared to ExecutionRecorder.
    """

    def __init__(
        self,
    ) -> None:
        """Initialize the recorder."""
        self._should_record = config.configuration.statistics_output.store_test_before_execution
        self._target_file = (
            Path(config.configuration.test_case_output.output_path).resolve()
            / "last_executed_test.py"
        )

        # Ensure the directory exists
        if self._should_record:
            self._target_file.parent.mkdir(parents=True, exist_ok=True)

        # Create and open the file if it does not exist
        self._file = open(self._target_file, "wb") if self._should_record else None  # noqa: SIM115, PTH123

    def record_test_case(self, test_case: tc.TestCase) -> None:
        """Record the test case.

        Args:
            test_case: The test case to record.
        """
        if not self._should_record:
            return

        try:
            pickle.dump(test_case, self._file)  # type: ignore[arg-type]
            self._file.flush()  # type: ignore[union-attr]

        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Failed to pickle dump test case: %s", e)

    def clear(self) -> None:
        """Clear the file."""
        if not self._should_record:
            return

        if self._file is None:
            raise RuntimeError("The file was closed.")

        self._file.seek(0)
        self._file.truncate(0)
