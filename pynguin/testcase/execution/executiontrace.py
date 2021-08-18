#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an execution trace"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Dict

from ordered_set import OrderedSet


@dataclass()
class ExecutionTrace:
    """Stores trace information about the execution."""

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: Dict[int, int] = field(default_factory=dict)
    true_distances: Dict[int, float] = field(default_factory=dict)
    false_distances: Dict[int, float] = field(default_factory=dict)

    def merge(self, other: ExecutionTrace) -> None:
        """Merge the values from the other trace.

        Args:
            other: Merges the other traces into this trace
        """
        self.executed_code_objects.update(other.executed_code_objects)
        for key, value in other.executed_predicates.items():
            self.executed_predicates[key] = self.executed_predicates.get(key, 0) + value
        self._merge_min(self.true_distances, other.true_distances)
        self._merge_min(self.false_distances, other.false_distances)

    @staticmethod
    def _merge_min(target: Dict[int, float], source: Dict[int, float]) -> None:
        """Merge source into target. Minimum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = min(target.get(key, inf), value)
