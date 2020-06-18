# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides an execution trace"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Dict, Set


@dataclass()
class ExecutionTrace:
    """Stores trace information about the execution."""

    executed_code_objects: Set[int] = field(default_factory=set)
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
