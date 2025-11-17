#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A context manager for storing test cases before execution."""

from __future__ import annotations

import logging
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
