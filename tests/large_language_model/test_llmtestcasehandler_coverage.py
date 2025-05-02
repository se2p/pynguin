#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests to improve coverage for the LLMTestCaseHandler module."""

from unittest.mock import mock_open
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.large_language_model.llmtestcasehandler import save_llm_tests_to_file


def test_save_llm_tests_to_file_success(tmp_path, monkeypatch):
    """Test saving test cases to a file successfully."""
    # Mock the configuration to use the temporary directory
    monkeypatch.setattr(config.configuration.statistics_output, "report_dir", str(tmp_path))

    # Test data
    test_cases = "def test_example():\n    assert True"
    file_name = "test_output.py"

    # Call the function
    save_llm_tests_to_file(test_cases, file_name)

    # Check that the file was created and contains the expected content
    output_file = tmp_path / file_name
    assert output_file.exists()
    content = output_file.read_text()
    assert "# LLM generated and rewritten (in Pynguin format) test cases" in content
    assert "# Date and time:" in content
    assert "def test_example():\n    assert True" in content


@pytest.mark.usefixtures("monkeypatch")
def test_save_llm_tests_to_file_error():
    """Test error handling when saving test cases fails."""
    # Mock the open function to raise an OSError
    mock_open_func = mock_open()
    mock_open_func.side_effect = OSError("Test error")

    with patch("pathlib.Path.open", mock_open_func):
        # Call the function - it should handle the error without raising an exception
        save_llm_tests_to_file("Test content", "test_file.py")
        # The function should log the error, but we can't easily test that
