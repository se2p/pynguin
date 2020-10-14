#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an entry for the output trace."""
from __future__ import annotations

from abc import abstractmethod
from typing import Set

import pynguin.assertion.assertion as ass


class OutputTraceEntry:
    """An entry in the output trace."""

    @abstractmethod
    def clone(self) -> OutputTraceEntry:
        """Clone this entry."""

    @abstractmethod
    def get_assertions(self) -> Set[ass.Assertion]:
        """Get assertions represented by this entry."""
