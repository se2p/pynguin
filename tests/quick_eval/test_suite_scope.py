# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Tests for quick_eval's target-module coverage scoping.

The quick_eval harness lives in ``utils/_quick_eval`` (outside ``src``); make it
importable the same way the ``utils/quick_eval.py`` entry point does.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UTILS_DIR = Path(__file__).resolve().parents[2] / "utils"
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

from _quick_eval.runner import _module_include_patterns  # noqa: E402, PLC2701


def test_top_level_package_matches_init_and_flat():
    # A bare package target (its __init__.py) must not pull in submodules; the patterns
    # match either the flat module or the package __init__, whichever exists.
    assert _module_include_patterns("cachetools") == "*/cachetools.py,*/cachetools/__init__.py"


def test_dotted_module_scopes_to_that_file():
    assert (
        _module_include_patterns("slugify.slugify")
        == "*/slugify/slugify.py,*/slugify/slugify/__init__.py"
    )


def test_submodule_scopes_to_that_file():
    # cachetools.func is a *separate* target from cachetools; it must scope to func.py.
    assert (
        _module_include_patterns("cachetools.func")
        == "*/cachetools/func.py,*/cachetools/func/__init__.py"
    )
