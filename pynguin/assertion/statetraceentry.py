#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an entry for the output trace."""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pynguin.assertion.assertion as ass


class StateTraceEntry:
    """An entry in the output trace."""

    @abstractmethod
    def clone(self) -> StateTraceEntry:
        """Clone this entry."""

    @abstractmethod
    def get_assertions(self) -> set[ass.Assertion]:
        """Get assertions represented by this entry."""
