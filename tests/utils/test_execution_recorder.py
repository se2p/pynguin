#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pathlib import Path
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.utils.execution_recorder import ExecutionRecorder


def test_file_created_and_deleted(tmp_path):
    config.configuration.statistics_output.store_test_before_execution = True
    config.configuration.test_case_output.output_path = str(tmp_path)

    test_case = MagicMock(tc.TestCase)
    target_file = Path(tmp_path) / "last_executed_test.py"

    # Ensure file does not exist before
    assert not target_file.exists()

    with ExecutionRecorder(test_case):
        # File should exist inside context
        assert target_file.exists()

    # After context exit, file should be removed
    assert not target_file.exists()


def test_file_persists_on_crash(tmp_path):
    config.configuration.statistics_output.store_test_before_execution = True
    config.configuration.test_case_output.output_path = str(tmp_path)

    test_case = MagicMock(tc.TestCase)
    target_file = Path(tmp_path) / "last_executed_test.py"

    class CrashExecutionRecorder(ExecutionRecorder):
        def __exit__(self, exc_type, exc_val, traceback):
            # Simulate crash: do not remove file
            pass

    with CrashExecutionRecorder(test_case):
        assert target_file.exists()
    # File should remain
    assert target_file.exists()


def test_no_recording_if_disabled(tmp_path):
    config.configuration.statistics_output.store_test_before_execution = True
    config.configuration.test_case_output.output_path = str(tmp_path)

    test_case = MagicMock(tc.TestCase)
    target_file = Path(tmp_path) / "last_executed_test.py"
    config.configuration.statistics_output.store_test_before_execution = False

    with ExecutionRecorder(test_case):
        # File should never be created
        assert not target_file.exists()


def test_export_exception_handling(monkeypatch, tmp_path):
    config.configuration.statistics_output.store_test_before_execution = True
    config.configuration.test_case_output.output_path = str(tmp_path)

    test_case = MagicMock(tc.TestCase)

    def mock_accept():
        raise Exception("fail")

    monkeypatch.setattr("pynguin.ga.testcasechromosome.TestCaseChromosome.accept", mock_accept)

    target_file = Path(tmp_path) / "last_executed_test.py"
    with ExecutionRecorder(test_case):
        # Should recover and not raise
        assert not target_file.exists() or not target_file.read_text()
