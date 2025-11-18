#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for filesystem isolation utilities."""

import os
import shutil
import tempfile

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pynguin.utils.fs_isolation import FilesystemIsolation


@pytest.fixture
def isolation():
    """Create a FilesystemIsolation instance for testing."""
    return FilesystemIsolation()


def test_filesystem_isolation_init(isolation):
    """Test that FilesystemIsolation initializes correctly."""
    assert isolation._created == set()
    assert isolation._tmp is not None
    assert isolation._exit_stack is not None


@pytest.mark.parametrize(
    ("path", "expected_type", "expected_value"),
    [
        ("/some/path", str, "/some/path"),
        (Path("/some/path"), str, "/some/path"),
    ],
)
def test_abspath(path, expected_type, expected_value):
    """Test the _abspath static method."""
    result = FilesystemIsolation._abspath(path)
    assert isinstance(result, expected_type)
    assert result == expected_value


@pytest.mark.parametrize(
    ("paths_to_record", "expected_recorded"),
    [
        (["/test/path"], ["/test/path"]),
        (["/test/path1", "/test/path2"], ["/test/path1", "/test/path2"]),
        ([None], []),
        (["/test/path", None], ["/test/path"]),
    ],
)
def test_record_created(isolation, paths_to_record, expected_recorded):
    """Test the _record_created method."""
    isolation._record_created(*paths_to_record)
    for path in expected_recorded:
        assert FilesystemIsolation._abspath(path) in isolation._created
    if None not in paths_to_record:
        assert None not in isolation._created


def test_forget(isolation):
    """Test the _forget method."""
    # First record a path
    path = "/test/path"
    isolation._record_created(path)
    assert FilesystemIsolation._abspath(path) in isolation._created

    # Then forget it
    isolation._forget(path)
    assert FilesystemIsolation._abspath(path) not in isolation._created

    # Test forgetting None (should not raise)
    isolation._forget(None)


@pytest.mark.parametrize(
    ("mode", "is_write"),
    [
        ("w", True),
        ("a", True),
        ("x", True),
        ("r+", True),
        ("w+", True),
        ("wb", True),
        ("ab", True),
        ("r", False),
        ("rb", False),
        ("", False),
    ],
)
def test_is_write_mode(mode, is_write):
    """Test the _is_write_mode static method."""
    assert FilesystemIsolation._is_write_mode(mode) is is_write


def test_create_tracked_method_record_arg(isolation):
    """Test _create_tracked_method with record_arg_idx."""

    def mock_func(_path, _other_arg):
        return "result"

    tracked = isolation._create_tracked_method(mock_func, record_arg_idx=0)

    # Call the tracked method
    result = tracked("/test/path", "other_arg")

    assert result == "result"
    assert FilesystemIsolation._abspath("/test/path") in isolation._created


def test_create_tracked_method_forget_arg(isolation):
    """Test _create_tracked_method with forget_arg_idx."""
    # First record a path
    test_path = "/test/path"
    isolation._record_created(test_path)

    def mock_func(_path, _other_arg):
        return "result"

    tracked = isolation._create_tracked_method(mock_func, forget_arg_idx=0)

    # Call the tracked method
    result = tracked(test_path, "other_arg")

    assert result == "result"
    assert FilesystemIsolation._abspath(test_path) not in isolation._created


def test_create_tracked_method_forget_arg_permission_error(isolation):
    """Test _create_tracked_method with forget_arg_idx.

    Ensures it raises ``PermissionError`` for non-isolated paths.
    """
    mock_func = MagicMock()
    tracked = isolation._create_tracked_method(mock_func, forget_arg_idx=0)

    # Try to forget a path that wasn't created in isolation
    with pytest.raises(PermissionError, match="Attempted to modify non-isolated path"):
        tracked("/non/isolated/path")

    # Should not call the original function
    mock_func.assert_not_called()


def test_create_tracked_method_binding_error(isolation):
    """Test _create_tracked_method handles binding errors gracefully."""
    mock_func = MagicMock(return_value="result")
    tracked = isolation._create_tracked_method(mock_func, record_arg_idx=10)  # Invalid index

    # Call with fewer args than expected
    result = tracked("arg")

    assert result == "result"
    mock_func.assert_called_once_with("arg")


@pytest.mark.parametrize(
    ("args", "kwargs", "should_record"),
    [
        (("w",), {}, True),
        (("r",), {}, False),
        ((), {"mode": "w"}, True),
        ((), {"mode": "r"}, False),
    ],
)
def test_create_open_tracked(isolation, args, kwargs, should_record):
    """Test _create_open_tracked records files based on open mode."""
    mock_open = MagicMock(return_value="file_object")
    tracked_open = isolation._create_open_tracked(mock_open)
    file_path = "/test/file.txt"

    result = tracked_open(file_path, *args, **kwargs)

    assert result == "file_object"
    mock_open.assert_called_once_with(file_path, *args, **kwargs)
    if should_record:
        assert FilesystemIsolation._abspath(file_path) in isolation._created
    else:
        assert FilesystemIsolation._abspath(file_path) not in isolation._created


@pytest.mark.parametrize(
    ("flag", "should_record"),
    [
        (os.O_WRONLY, True),
        (os.O_RDONLY, False),
        (os.O_RDWR, True),
        (os.O_APPEND, True),
        (os.O_CREAT, True),
    ],
)
def test_os_open_tracked(isolation, flag, should_record):
    """Test _os_open_tracked records files based on open flags."""
    mock_os_open = MagicMock(return_value=42)
    tracked_os_open = isolation._os_open_tracked(mock_os_open)
    file_path = "/test/file.txt"

    result = tracked_os_open(file_path, flag)

    assert result == 42
    mock_os_open.assert_called_once_with(file_path, flag)
    if should_record:
        assert FilesystemIsolation._abspath(file_path) in isolation._created
    else:
        assert FilesystemIsolation._abspath(file_path) not in isolation._created


def test_create_path_rename_replace_tracked(isolation):
    """Test _create_path_rename_replace_tracked."""
    # First record a path
    source_path = Path("/test/source")
    target_path = Path("/test/target")
    isolation._record_created(str(source_path))

    mock_func = MagicMock(return_value=target_path)
    tracked = isolation._create_path_rename_replace_tracked(mock_func)

    # Call the tracked method
    result = tracked(source_path, target_path)

    assert result == target_path
    mock_func.assert_called_once_with(source_path, target_path)
    assert FilesystemIsolation._abspath(str(source_path)) not in isolation._created
    assert FilesystemIsolation._abspath(str(target_path)) in isolation._created


def test_create_path_rename_replace_tracked_permission_error(isolation):
    """Test _create_path_rename_replace_tracked raises PermissionError for non-isolated paths."""
    source_path = Path("/test/source")
    target_path = Path("/test/target")

    mock_func = MagicMock()
    tracked = isolation._create_path_rename_replace_tracked(mock_func)

    # Try to rename a path that wasn't created in isolation
    with pytest.raises(PermissionError, match="Attempted to rename/replace non-isolated path"):
        tracked(source_path, target_path)

    mock_func.assert_not_called()


def test_context_manager_enter_exit(tmp_path):
    """Test FilesystemIsolation as a context manager."""
    with FilesystemIsolation() as isolation:
        # Test that temporary directory is set
        assert "TMP" in os.environ
        assert "TEMP" in os.environ
        assert "TMPDIR" in os.environ

        # Test that patches are in place
        assert hasattr(isolation, "_exit_stack")

        # Create a file inside the context
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")

        # The isolation should track this
        assert str(test_file.resolve()) in isolation._created


def test_context_manager_cleanup():
    """Test that FilesystemIsolation cleans up properly."""
    created_files = set()

    with FilesystemIsolation() as isolation:
        # Create some test files
        test_dir = Path(isolation._tmp.name) / "test_subdir"
        test_dir.mkdir()
        test_file = test_dir / "test_file.txt"
        test_file.write_text("test")

        # Manually track them
        isolation._record_created(str(test_dir))
        isolation._record_created(str(test_file))
        created_files = isolation._created.copy()

    # After exiting, files should be cleaned up
    for file_path in created_files:
        assert not Path(file_path).exists()


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


def test_filesystem_operations_integration():
    """Integration test for various filesystem operations."""
    with FilesystemIsolation() as isolation:
        # Test os.mkdir
        test_dir = Path(isolation._tmp.name) / "test_integration_dir"
        test_dir.mkdir()
        assert isolation._abspath(test_dir) in isolation._created

        # Test Path.mkdir
        test_subdir = test_dir / "subdir"
        test_subdir.mkdir()
        assert isolation._abspath(test_subdir) in isolation._created

        # Test file creation
        test_file = test_dir / "test_file.txt"
        test_file.write_text("test content", encoding="utf-8")
        assert isolation._abspath(test_file) in isolation._created

        # Test Path.write_text
        test_file2 = test_dir / "test_file2.txt"
        test_file2.write_text("test content 2")
        assert isolation._abspath(test_file2) in isolation._created

        # Test shutil.copy
        test_file3 = test_dir / "test_file3.txt"
        shutil.copy(str(test_file), str(test_file3))
        assert isolation._abspath(test_file3) in isolation._created

        # Test rename (should work because both files are isolated)
        test_file4 = test_dir / "test_file4.txt"
        test_file3.rename(test_file4)
        assert isolation._abspath(test_file4) in isolation._created
        assert isolation._abspath(test_file3) not in isolation._created

        # Test file deletion
        test_file4.unlink()
        assert isolation._abspath(test_file4) not in isolation._created


def test_permission_error_on_non_isolated_operations():
    """Integration test for permission errors on non-isolated operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a file outside isolation
        external_file = Path(temp_dir) / "external_file.txt"
        external_file.write_text("external content")

        with FilesystemIsolation():
            # Try to delete external file (should raise PermissionError)
            with pytest.raises(PermissionError, match="Attempted to modify non-isolated path"):
                external_file.unlink()

            # Try to rename external file (should raise PermissionError)
            with pytest.raises(
                PermissionError, match="Attempted to rename/replace non-isolated path"
            ):
                external_file.rename(external_file.parent / "renamed.txt")


def test_temporary_directory_redirection():
    """Test that temporary directories are properly redirected."""
    original_tmp = os.environ.get("TMP")
    original_temp = os.environ.get("TEMP")
    original_tmpdir = os.environ.get("TMPDIR")

    with FilesystemIsolation() as isolation:
        # Check that environment variables are redirected
        assert os.environ["TMP"] == isolation._tmp.name
        assert os.environ["TEMP"] == isolation._tmp.name
        assert os.environ["TMPDIR"] == isolation._tmp.name

        # Test that tempfile operations use the isolated directory
        with tempfile.NamedTemporaryFile() as tmp:
            temp_file = tmp.name
            assert temp_file.startswith(isolation._tmp.name)

    # Check that environment is restored
    assert os.environ.get("TMP") == original_tmp
    assert os.environ.get("TEMP") == original_temp
    assert os.environ.get("TMPDIR") == original_tmpdir


def test_exit_returns_false():
    """Test that __exit__ returns False to propagate exceptions."""
    isolation = FilesystemIsolation()

    # __exit__ should return False to propagate exceptions
    result = isolation.__exit__(None, None, None)
    assert result is False


def test_cleanup_handles_missing_files():
    """Test that cleanup gracefully handles already-deleted files."""
    with patch("pathlib.Path.unlink") as mock_unlink:
        mock_unlink.side_effect = FileNotFoundError("File not found")

        isolation = FilesystemIsolation()
        isolation._record_created("/test/missing_file.txt")

        # Should not raise an exception
        isolation.__exit__(None, None, None)


def test_cleanup_handles_cleanup_errors(caplog):
    """Test that cleanup logs warnings for cleanup failures."""
    with patch("pathlib.Path.unlink") as mock_unlink:
        mock_unlink.side_effect = PermissionError("Permission denied")

        isolation = FilesystemIsolation()
        isolation._record_created("/test/problematic_file.txt")

        # Should not raise an exception but should log a warning
        isolation.__exit__(None, None, None)

        assert "Failed to cleanup path" in caplog.text


def test_cleanup_handles_different_path_types():
    """Test that cleanup can handle different types of paths."""
    isolation = FilesystemIsolation()

    # Record some test paths
    isolation._record_created("/test/file.txt")
    isolation._record_created("/test/dir")
    isolation._record_created("/test/symlink")

    # Mock the necessary Path methods to avoid actual filesystem operations
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.is_symlink", return_value=False),
        patch("pathlib.Path.is_dir", return_value=False),
        patch("pathlib.Path.unlink"),
    ):
        # Should not raise any exceptions
        result = isolation.__exit__(None, None, None)
        assert result is False


def test_symlink_handling():
    """Integration test for symlink cleanup."""
    with FilesystemIsolation() as isolation:
        # Create a file and a symlink to it
        base_dir = Path(isolation._tmp.name)
        target_file = base_dir / "target.txt"
        target_file.write_text("target content")

        symlink_file = base_dir / "link.txt"
        symlink_file.symlink_to(target_file)

        # Record both
        isolation._record_created(str(target_file))
        isolation._record_created(str(symlink_file))

    # Both should be cleaned up without errors
    assert not target_file.exists()
    assert not symlink_file.exists()


def test_os_open_tracked_exception_handling():
    """Test that _os_open_tracked handles flag checking exceptions gracefully."""
    mock_os_open = MagicMock(return_value=42)
    isolation = FilesystemIsolation()

    # Test with a flag value that doesn't correspond to any OS constant
    # This should trigger the exception handling path
    tracked_os_open = isolation._os_open_tracked(mock_os_open)

    # This should work normally - testing that the function doesn't break
    result = tracked_os_open("/test/file.txt", 999999)  # Non-standard flag
    assert result == 42
    mock_os_open.assert_called_once_with("/test/file.txt", 999999)


def test_path_rename_exception_handling(caplog):
    """Test that path rename/replace handles recording exceptions gracefully."""
    source_path = Path("/test/source")
    target_path = Path("/test/target")

    isolation = FilesystemIsolation()
    isolation._record_created(str(source_path))

    mock_func = MagicMock(return_value=target_path)
    tracked = isolation._create_path_rename_replace_tracked(mock_func)

    # Mock _record_created to raise an exception
    with patch.object(isolation, "_record_created", side_effect=Exception("Test error")):
        result = tracked(source_path, target_path)

        assert result == target_path
        assert "Failed to update bookkeeping" in caplog.text


def test_cleanup_symlink_branch():
    """Test that cleanup properly handles symlinks using the symlink branch."""
    isolation = FilesystemIsolation()

    # Record a test symlink path
    symlink_path = "/test/symlink"
    isolation._record_created(symlink_path)

    # Mock Path methods to simulate a symlink
    with (
        patch("pathlib.Path.is_symlink", return_value=True) as mock_is_symlink,
        patch("pathlib.Path.unlink") as mock_unlink,
        patch("pathlib.Path.is_dir", return_value=False),
    ):
        # Should not raise any exceptions
        result = isolation.__exit__(None, None, None)
        assert result is False

        # Should have called is_symlink check
        mock_is_symlink.assert_called()
        # Should have called unlink for the symlink
        mock_unlink.assert_called()


def test_cleanup_directory_branch():
    """Test that cleanup properly handles directories using the directory branch."""
    isolation = FilesystemIsolation()

    # Record a test directory path
    dir_path = "/test/directory"
    isolation._record_created(dir_path)

    # Mock Path methods to simulate a directory
    with (
        patch("pathlib.Path.is_symlink", return_value=False),
        patch("pathlib.Path.is_dir", return_value=True) as mock_is_dir,
        patch("pathlib.Path.exists", return_value=True),
        patch("shutil.rmtree") as mock_rmtree,
    ):
        # Should not raise any exceptions
        result = isolation.__exit__(None, None, None)
        assert result is False

        # Should have called is_dir check
        mock_is_dir.assert_called()
        # Should have called rmtree for the directory among other possible calls
        mock_rmtree.assert_any_call(dir_path, ignore_errors=True)


def test_cleanup_mixed_path_types():
    """Test cleanup with a mix of symlinks, directories, and files."""
    isolation = FilesystemIsolation()

    # Record different types of paths
    file_path = "/test/file.txt"
    dir_path = "/test/directory"
    symlink_path = "/test/symlink"

    isolation._record_created(file_path)
    isolation._record_created(dir_path)
    isolation._record_created(symlink_path)

    def mock_is_symlink(self):
        return str(self) == symlink_path

    def mock_is_dir(self):
        return str(self) == dir_path

    with (
        patch("pathlib.Path.is_symlink", mock_is_symlink),
        patch("pathlib.Path.is_dir", mock_is_dir),
        patch("pathlib.Path.unlink") as mock_unlink,
        patch("shutil.rmtree") as mock_rmtree,
    ):
        # Should not raise any exceptions
        result = isolation.__exit__(None, None, None)
        assert result is False

        # Should have called unlink for file and symlink (2 times)
        assert mock_unlink.call_count == 2
        # Should have called rmtree for directory (1 time)
        mock_rmtree.assert_called_once_with(dir_path, ignore_errors=True)
