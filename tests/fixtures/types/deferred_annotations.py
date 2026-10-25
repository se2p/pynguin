#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sized


def length(obj: Sized) -> int:
    return len(obj)
