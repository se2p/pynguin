#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for filesystem isolation utilities."""

import tempfile

from pathlib import Path

import pytest

from pynguin.utils.fs_isolation import FilesystemIsolation


def test_decorator_usage():
    """Test FilesystemIsolation as a decorator."""

    @FilesystemIsolation()
    def test_function():
        # Create a temporary file
        temp_file = Path(tempfile.gettempdir()) / "decorator_test.txt"
        temp_file.write_text("test content")
        return temp_file

    # Call the decorated function
    created_file = test_function()

    # File should be cleaned up after function returns
    assert not created_file.exists()


def test_permission_error_on_non_isolated_operations():
    """Integration test for permission errors on non-isolated operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a file outside isolation
        external_file = Path(temp_dir) / "external_file.txt"
        external_file.write_text("external content")

        with FilesystemIsolation():
            # Try to delete external file (should raise PermissionError)
            with pytest.raises(FileNotFoundError):
                external_file.unlink()

            # Try to rename external file (should raise PermissionError)
            with pytest.raises(FileNotFoundError):
                external_file.rename(external_file.parent / "renamed.txt")
