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
import io
import logging
import os
import shutil

from contextlib import ContextDecorator
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

import pynguin.configuration as config


if TYPE_CHECKING:
    from collections.abc import Callable


_LOGGER = logging.getLogger(__name__)


COMMON_KW_NAMES = ("src", "dst", "path", "target", "name", "filename", "file")


@lru_cache(maxsize=8192)
def _normalize_path_cached(path: str) -> str:
    """Fast path normalization without resolving symlinks.

    Uses os.path.abspath + normpath which avoids extra filesystem lookups from
    Path.resolve(). Caching avoids repeated allocations for hot paths.
    """
    try:
        # For performance, we avoid using Path here to prevent extra allocations.
        return os.path.normpath(os.path.abspath(path))  # noqa: PTH100
    except Exception:  # noqa: BLE001
        return str(path)


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
        self._enabled = config.configuration.filesystem_isolation
        if self._enabled:
            self._tmp = TemporaryDirectory()
            self._created: set[str] = set()
            self._exit_stack = ExitStack()

    @staticmethod
    def _abspath(path: os.PathLike | str) -> str:
        """Convert a path to an absolute path."""
        return _normalize_path_cached(str(path))

    def _record_created(self, *paths: os.PathLike | str | None) -> None:
        """Record newly created paths. Uses set.update for fewer allocations."""
        to_add = (self._abspath(p) for p in paths if p is not None)
        self._created.update(to_add)

    def _forget(self, *paths: os.PathLike | str | None) -> None:
        """Forget paths (on deletion/move). Uses discard to avoid exceptions."""
        for p in paths:
            if p is not None:
                self._created.discard(self._abspath(p))

    @staticmethod
    def _is_write_mode(mode: str) -> bool:
        """Check if a mode is write mode."""
        return any(ch in mode for ch in ("w", "a", "x", "+"))

    @staticmethod
    def _get_arg(args: tuple, kwargs: dict, index: int | None) -> os.PathLike | str | None:
        """Fast, heuristic argument resolver: prefer positional, then common kw names."""
        if index is None:
            return None
        if index < len(args):
            return args[index]
        for name in COMMON_KW_NAMES:
            if name in kwargs:
                return kwargs[name]
        return None

    def _create_tracked_method(
        self,
        original_func: Callable,
        *,
        record_arg_idx: int | None = None,
        record_dst_idx: int | None = None,
        forget_arg_idx: int | None = None,
    ) -> Callable:
        """Create a tracked wrapper that uses positional indices."""

        @functools.wraps(original_func)
        def tracked_method(*args, **kwargs):
            forget_path = self._get_arg(args, kwargs, forget_arg_idx)
            if forget_path:
                abs_forget = self._abspath(forget_path)
                # only allow modifications of previously-created (isolated) paths
                if abs_forget not in self._created:
                    raise PermissionError(f"Attempted to modify non-isolated path: {abs_forget}")

            res = original_func(*args, **kwargs)

            try:
                rec = self._get_arg(args, kwargs, record_arg_idx)
                dst = self._get_arg(args, kwargs, record_dst_idx)
                self._record_created(rec, dst)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Failed to update bookkeeping for %s", original_func)

            try:
                self._forget(forget_path)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Failed to forget path: %s", forget_path)

            return res

        return tracked_method

    def _create_open_tracked(self, original_func: Callable) -> Callable:
        """Tracked wrapper for open-like callables (builtins.open, io.open, Path.open)."""

        @functools.wraps(original_func)
        def tracked_open(*args, **kwargs):
            # first arg is a path-like or file descriptor
            # second positional arg may be mode, or kwargs['mode']
            file_arg = args[0] if args else kwargs.get("file")
            mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
            f = original_func(*args, **kwargs)
            if isinstance(mode, str) and self._is_write_mode(mode):
                try:
                    self._record_created(file_arg)
                except Exception:  # noqa: BLE001
                    _LOGGER.warning("Failed to record created file: %s", file_arg)
            return f

        return tracked_open

    def _os_open_tracked(self, original_func: Callable) -> Callable:
        """Tracked wrapper for os.open which receives flags rather than mode strings."""
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

        @functools.wraps(original_func)
        def tracked_os_open(path, flags, *args, **kwargs):
            should_record = bool(flags & write_flags)
            fd = original_func(path, flags, *args, **kwargs)
            if should_record:
                try:
                    self._record_created(path)
                except Exception:  # noqa: BLE001
                    _LOGGER.warning("Failed to record created path: %s", path)
            return fd

        return tracked_os_open

    def _create_path_rename_replace_tracked(self, original_func: Callable) -> Callable:
        """Tracked wrapper for Path.rename/replace preserving permission semantics."""

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
                _LOGGER.warning(
                    "Failed to update bookkeeping for rename/replace: %s -> %s", path_self, target
                )
            return res

        return tracked_method

    def _initialize_patches(self) -> None:
        """Initialize all patches with tracked wrappers."""
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

        # os.open (low-level file descriptor open)
        if hasattr(os, "open"):
            self._exit_stack.enter_context(
                patch.object(os, "open", new=self._os_open_tracked(os.open))
            )

    def __enter__(self):
        """Enter the isolation context: set up tmpdir and patches."""
        if not self._enabled:
            return self

        # mount the TemporaryDirectory
        self._exit_stack.enter_context(self._tmp)
        tmpdir = self._tmp.name
        # batch env update for all tmp variables
        self._exit_stack.enter_context(
            patch.dict(os.environ, {"TMPDIR": tmpdir, "TEMP": tmpdir, "TMP": tmpdir})
        )
        # patch tempfile.tempdir to this tmp
        self._exit_stack.enter_context(patch("tempfile.tempdir", tmpdir))

        self._initialize_patches()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """Exit the filesystem isolation context."""
        if not self._enabled:
            return False

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
        self._created.clear()
        return False
