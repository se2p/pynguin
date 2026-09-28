#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def keep(pred: Callable[[int], bool], values: Iterable[int]) -> list[int]:
    return [value for value in values if pred(value)]


def first(values: list[int]) -> int:
    return values[0]
