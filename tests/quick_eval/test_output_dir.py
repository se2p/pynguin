# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Tests for quick_eval's run-directory handling (``--output-dir`` persistence).

The quick_eval harness lives in ``utils/_quick_eval`` (outside ``src``); make it
importable the same way the ``utils/quick_eval.py`` entry point does.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UTILS_DIR = Path(__file__).resolve().parents[2] / "utils"
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

from _quick_eval.runner import _run_dir  # noqa: E402, PLC2701


def test_run_dir_without_output_dir_is_temporary():
    with _run_dir(None, "some.module") as run_dir:
        path = Path(run_dir)
        assert path.is_dir()
    # The throwaway temp dir is removed once the context exits.
    assert not path.exists()


def test_run_dir_with_output_dir_persists_per_module(tmp_path):
    module = "pkg.sub.module"
    with _run_dir(str(tmp_path), module) as run_dir:
        path = Path(run_dir)
        assert path.is_dir()
        assert path == tmp_path / module
    # The persisted dir survives so the exported tests can be inspected afterwards.
    assert path.is_dir()


def test_run_dir_with_output_dir_creates_parents(tmp_path):
    target = tmp_path / "nested" / "out"
    with _run_dir(str(target), "m") as run_dir:
        assert Path(run_dir) == target / "m"
        assert Path(run_dir).is_dir()
