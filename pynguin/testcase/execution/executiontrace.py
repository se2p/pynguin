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
from dataclasses import dataclass, field
from typing import Set, Dict


# pylint:disable=too-many-instance-attributes
@dataclass()
class ExecutionTrace:
    """Stores trace information about the execution."""

    # These are linked to the originals, do not modify!
    existing_functions: Set[int]
    existing_predicates: Set[int]
    existing_for_loops: Set[int]

    covered_functions: Set[int] = field(default_factory=set)
    covered_predicates: Dict[int, int] = field(default_factory=dict)
    covered_for_loops: Set[int] = field(default_factory=set)
    true_distances: Dict[int, float] = field(default_factory=dict)
    false_distances: Dict[int, float] = field(default_factory=dict)
