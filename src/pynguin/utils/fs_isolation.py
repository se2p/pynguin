#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Filesystem isolation utilities for executing SUT safely."""

from __future__ import annotations

import builtins
import functools
import inspect
import io
import logging
import os
import shutil

from contextlib import ContextDecorator
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch


if TYPE_CHECKING:
    from collections.abc import Callable


_LOGGER = logging.getLogger(__name__)


class FilesystemIsolation(ContextDecorator):
    """Isolates filesystem side effects during test execution.

    Provides a sandboxed environment that:
    - Tracks and records file and directory creations, deletions, and renames.
    - Prevents modifications to non-isolated (real) filesystem paths.
    - Redirects temporary paths (TMP, TEMP, TMPDIR) to a temporary directory.
    - Automatically cleans up all created files and directories on exit.
    - Works as both a context manager and decorator.
    """

    def __init__(self) -> None:
        """Initialize the isolation."""
        self._tmp = TemporaryDirectory()
        self._created: set[str] = set()
        self._exit_stack = ExitStack()

    @staticmethod
    def _abspath(path: os.PathLike | str) -> str:
        """Convert a path to an absolute path."""
        try:
            return Path(path).resolve().as_posix()
        except Exception:  # noqa: BLE001
            return str(path)

    def _record_created(self, *paths: os.PathLike | str | None) -> None:
        """Record a created path."""
        for p in paths:
            if p is not None:
                self._created.add(self._abspath(p))

    def _forget(self, *paths: os.PathLike | str | None) -> None:
        """Forget a path (e.g., on deletion)."""
        for p in paths:
            if p is not None:
                self._created.discard(self._abspath(p))

    @staticmethod
    def _is_write_mode(mode: str) -> bool:
        """Check if a mode is write mode."""
        return any(ch in mode for ch in ("w", "a", "x", "+"))

    def _create_tracked_method(
        self,
        original_func: Callable,
        *,
        record_arg_idx: int | None = None,
        record_dst_idx: int | None = None,
        forget_arg_idx: int | None = None,
    ) -> Callable:
        """Factory for creating tracked methods for creation, deletion, and renaming."""
        sig = inspect.signature(original_func)

        @functools.wraps(original_func)
        def tracked_method(*args, **kwargs):
            record_path = None
            record_dst_path = None
            forget_path = None

            try:
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                arguments = bound_args.arguments
                params = list(sig.parameters)

                if forget_arg_idx is not None:
                    param_name = params[forget_arg_idx]
                    forget_path = arguments[param_name]
                    abs_path = self._abspath(forget_path)
                    if abs_path not in self._created:
                        raise PermissionError(f"Attempted to modify non-isolated path: {abs_path}")

                if record_arg_idx is not None:
                    param_name = params[record_arg_idx]
                    record_path = arguments[param_name]

                if record_dst_idx is not None:
                    param_name = params[record_dst_idx]
                    record_dst_path = arguments[param_name]

            except (IndexError, KeyError, TypeError):
                # Ignore binding errors, proceed to original function
                pass

            res = original_func(*args, **kwargs)

            self._forget(forget_path)
            self._record_created(record_path, record_dst_path)

            return res

        return tracked_method

    def _create_open_tracked(self, original_func: Callable) -> Callable:
        """Factory for creating tracked 'open' methods."""

        @functools.wraps(original_func)
        def tracked_open(*args, **kwargs):
            file = args[0]
            mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
            f = original_func(*args, **kwargs)
            try:
                if self._is_write_mode(mode):
                    self._record_created(file)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Failed to record created file: %s", file)
            return f

        return tracked_open

    def _os_open_tracked(self, original_func: Callable) -> Callable:
        """Factory for creating tracked os.open methods."""

        @functools.wraps(original_func)
        def tracked_os_open(path, flags, *args, **kwargs):
            should_record = False
            try:
                write_flags = 0
                for flag_name in (
                    "O_WRONLY",
                    "O_RDWR",
                    "O_CREAT",
                    "O_TRUNC",
                    "O_APPEND",
                    "O_TMPFILE",
                ):
                    if hasattr(os, flag_name):
                        write_flags |= getattr(os, flag_name)
                should_record = bool(flags & write_flags)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Failed to check write flags for path: %s", path)

            fd = original_func(path, flags, *args, **kwargs)
            if should_record:
                try:
                    self._record_created(path)
                except Exception:  # noqa: BLE001
                    _LOGGER.warning("Failed to record created path: %s", path)
            return fd

        return tracked_os_open

    def _create_path_rename_replace_tracked(self, original_func: Callable) -> Callable:
        """Factory for creating tracked Path.rename/replace methods."""

        @functools.wraps(original_func)
        def tracked_method(path_self, target):
            abs_path = self._abspath(path_self)
            if abs_path not in self._created:
                raise PermissionError(f"Attempted to rename/replace non-isolated path: {abs_path}")
            res = original_func(path_self, target)
            try:
                self._forget(path_self)
                self._record_created(res)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Failed to record created path: %s", res)
            return res

        return tracked_method

    def _initialize_patches(self) -> None:
        """Initialize all method patches with their tracked versions."""
        patches = {
            (os, "mkdir"): {"record_arg_idx": 0},
            (os, "makedirs"): {"record_arg_idx": 0},
            (os, "rename"): {"forget_arg_idx": 0, "record_dst_idx": 1},
            (os, "replace"): {"forget_arg_idx": 0, "record_dst_idx": 1},
            (shutil, "copyfile"): {"record_dst_idx": 1},
            (shutil, "copy"): {"record_dst_idx": 1},
            (shutil, "copy2"): {"record_dst_idx": 1},
            (shutil, "copytree"): {"record_dst_idx": 1},
            (shutil, "move"): {"forget_arg_idx": 0, "record_dst_idx": 1},
            (Path, "mkdir"): {"record_arg_idx": 0},
            (Path, "touch"): {"record_arg_idx": 0},
            (Path, "write_text"): {"record_arg_idx": 0},
            (Path, "write_bytes"): {"record_arg_idx": 0},
            (os, "remove"): {"forget_arg_idx": 0},
            (os, "unlink"): {"forget_arg_idx": 0},
            (os, "rmdir"): {"forget_arg_idx": 0},
            (shutil, "rmtree"): {"forget_arg_idx": 0},
            (Path, "unlink"): {"forget_arg_idx": 0},
            (Path, "rmdir"): {"forget_arg_idx": 0},
        }
        for (module, method), track_kwargs in patches.items():
            original = getattr(module, method)
            tracked = self._create_tracked_method(original, **track_kwargs)
            self._exit_stack.enter_context(patch.object(module, method, new=tracked))

        for method_name in ("rename", "replace"):
            original = getattr(Path, method_name)
            tracked = self._create_path_rename_replace_tracked(original)
            self._exit_stack.enter_context(patch.object(Path, method_name, new=tracked))

        open_patches = [(builtins, "open"), (io, "open"), (Path, "open")]
        for module, method in open_patches:
            original = getattr(module, method)
            tracked = self._create_open_tracked(original)
            self._exit_stack.enter_context(patch.object(module, method, new=tracked))

        original_os_open = os.open
        tracked_os_open = self._os_open_tracked(original_os_open)
        self._exit_stack.enter_context(patch.object(os, "open", new=tracked_os_open))

    def __enter__(self):
        """Enter the filesystem isolation context."""
        self._exit_stack.enter_context(self._tmp)
        for key in ("TMPDIR", "TEMP", "TMP"):
            self._exit_stack.enter_context(patch.dict(os.environ, {key: self._tmp.name}))
        self._exit_stack.enter_context(patch("tempfile.tempdir", self._tmp.name))

        self._initialize_patches()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """Exit the filesystem isolation context."""
        self._exit_stack.close()

        for path in sorted(self._created, key=lambda p: (p.count(os.sep), p), reverse=True):
            try:
                if Path(path).is_symlink():
                    Path(path).unlink()
                elif Path(path).is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    Path(path).unlink()
            except FileNotFoundError:  # noqa: PERF203
                pass  # Already removed
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Failed to cleanup path: %s", path)
        return False
