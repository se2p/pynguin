#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides utilities related to Fandango and Faker."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

try:
    from fandango.language.parse import parse

    if TYPE_CHECKING:
        from fandango.language.grammar import Grammar
    FANDANGO_FAKER_AVAILABLE = True
except ImportError:
    FANDANGO_FAKER_AVAILABLE = False


def load_fandango_grammars(folder: str) -> list[Grammar]:
    """Loads a list of Fandango grammars from files in the given folder.

    Returns:
        The list of grammars
    """
    grammars: list[Grammar] = []

    if FANDANGO_FAKER_AVAILABLE:
        folder_path = Path(folder)
        if not folder_path.exists():
            return grammars

        for path in folder_path.iterdir():
            if path.is_file() and path.suffix == ".fan":
                with path.open(encoding="utf-8", mode="r") as fan_file:
                    grammar, _constraints = parse(fan_file)
                    grammars.append(grammar)

    return grammars
