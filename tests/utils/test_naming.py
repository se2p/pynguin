#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for module-name canonicalization (``pynguin.utils.naming``)."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import pytest

from pynguin.utils import naming
from pynguin.utils.naming import canonical_module_name, dotted_module_path_from_origin

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("pathlib", "pathlib"),
        ("importlib.util", "importlib.util"),
        ("builtins", "builtins"),
        ("array", "array"),
        ("src.pynguin.utils.namingscope", "pynguin.utils.namingscope"),
        ("pynguin.utils.namingscope", "pynguin.utils.namingscope"),
        ("pynguin_this_module_does_not_exist_at_all", "pynguin_this_module_does_not_exist_at_all"),
    ],
)
def test_canonical_module_name(name: str, expected: str):
    assert canonical_module_name(name) == expected


def _make_namespace_package(tmp_path: Path) -> Path:
    """Create ``google/auth/_helpers.py`` with ``google`` a PEP 420 namespace package."""
    auth = tmp_path / "google" / "auth"
    auth.mkdir(parents=True)
    (auth / "__init__.py").write_text("")
    helpers = auth / "_helpers.py"
    helpers.write_text("")
    # Intentionally no ``google/__init__.py`` -> ``google`` is a namespace package.
    return helpers


def test_dotted_from_origin_drops_namespace_prefix(tmp_path: Path) -> None:
    # Documents the raw filesystem derivation the canonical-name guard compensates
    # for: climbing while __init__.py exists stops at the namespace boundary.
    helpers = _make_namespace_package(tmp_path)
    assert dotted_module_path_from_origin(str(helpers)) == "auth._helpers"


def test_canonical_module_name_keeps_namespace_package_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `google.auth._helpers` must not collapse to the unimportable `auth._helpers`.
    helpers = _make_namespace_package(tmp_path)

    def fake_find_spec(name: str):
        if name == "google.auth._helpers":
            return importlib.util.spec_from_file_location(name, str(helpers))
        # The namespace-stripped name does not import.
        return None

    monkeypatch.setattr(naming.importlib.util, "find_spec", fake_find_spec)

    assert canonical_module_name("google.auth._helpers") == "google.auth._helpers"
