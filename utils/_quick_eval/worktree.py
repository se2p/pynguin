# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Git-worktree and cached-venv management for baseline branch comparison."""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404
import sys
import tempfile
from pathlib import Path

from . import console

_GIT: str = shutil.which("git") or "git"
_VENV_CACHE_DIR = Path.home() / ".cache" / "pynguin-eval" / "venvs"


def git_ref() -> str:
    """Return the current git short hash, or 'unknown' if not in a repo."""
    try:
        return subprocess.check_output(  # noqa: S603
            [_GIT, "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _resolve_full_hash(git_ref_value: str) -> str:
    """Resolve a git ref to its full commit hash."""
    return subprocess.check_output(  # noqa: S603
        [_GIT, "rev-parse", git_ref_value], text=True
    ).strip()


def build_worktree_venv(git_ref_value: str) -> tuple[str | None, str]:
    """Return (worktree_dir_or_None, python_exe) for the given git ref.

    The venv is cached at ~/.cache/pynguin-eval/venvs/{full_hash}/ so repeated
    calls for the same commit reuse it without re-installing. Uses a non-editable
    install so the venv survives worktree removal.
    """
    full_hash = _resolve_full_hash(git_ref_value)
    venv_dir = _VENV_CACHE_DIR / full_hash
    venv_python = str(venv_dir / "bin" / "python")
    if venv_dir.exists() and Path(venv_python).exists():
        console.print(f"Reusing cached venv for {git_ref_value} ({full_hash[:12]}) at {venv_dir}")
        return None, venv_python
    worktree_dir = tempfile.mkdtemp(prefix=f"pynguin_worktree_{git_ref_value}_")
    console.print(
        f"Creating git worktree for '{git_ref_value}' ({full_hash[:12]}) at {worktree_dir} ..."
    )
    subprocess.run(  # noqa: S603
        [_GIT, "worktree", "add", "--detach", worktree_dir, git_ref_value],
        check=True,
    )
    venv_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Creating venv at {venv_dir} ...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)  # noqa: S603
    console.print("Installing pynguin from worktree (non-editable, cached) ...")
    subprocess.run(  # noqa: S603
        [venv_python, "-m", "pip", "install", worktree_dir, "--quiet"],
        check=True,
    )
    return worktree_dir, venv_python


def remove_worktree(worktree_dir: str | None) -> None:
    """Remove a git worktree created by build_worktree_venv, if any."""
    if worktree_dir is None:
        return
    subprocess.run(  # noqa: S603
        [_GIT, "worktree", "remove", "--force", worktree_dir],
        check=False,
    )
