#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a data class to track the control-flow distances."""
from __future__ import annotations

from functools import total_ordering
from typing import Any

from pynguin.ga.fitnessfunctions.fitness_utilities import normalise


@total_ordering
class ControlFlowDistance:
    """Tracks control-flow distances."""

    def __init__(self, approach_level: int = 0, branch_distance: float = 0.0) -> None:
        assert (
            approach_level >= 0 and branch_distance >= 0.0
        ), "Expect approach_level and branch_distance to be non-negative"
        self._approach_level = approach_level
        self._branch_distance = branch_distance

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, ControlFlowDistance):
            return False
        return (self._approach_level, self._branch_distance) == (
            other.approach_level,
            other.branch_distance,
        )

    def __lt__(self, other: ControlFlowDistance) -> bool:
        if not isinstance(other, ControlFlowDistance):
            raise TypeError(  # pylint: disable=raising-format-tuple
                "'<' not supported between instances of "
                "'ControlFlowDistance' and '%s'",
                type(other),
            )
        return (self._approach_level, self._branch_distance) < (
            other.approach_level,
            other.branch_distance,
        )

    @property
    def approach_level(self) -> int:
        """Provides the approach level.

        Returns:
            The approach level
        """
        return self._approach_level

    @approach_level.setter
    def approach_level(self, approach_level: int):
        assert approach_level >= 0, "Expect approach_level to be non-negative"
        self._approach_level = approach_level

    @property
    def branch_distance(self) -> float:
        """Provides the branch distance.

        Returns:
            The branch distance
        """
        return self._branch_distance

    @branch_distance.setter
    def branch_distance(self, branch_distance: float) -> None:
        assert branch_distance >= 0, "Expect branch_distance to be non-negative"
        self._branch_distance = branch_distance

    def increase_approach_level(self) -> None:
        """Increases the approach level by one."""
        self._approach_level += 1

    def get_resulting_branch_fitness(self) -> float:
        """Computes the resulting branch fitness.

        Returns:
            The resulting branch fitness
        """
        return self._approach_level + normalise(self._branch_distance)

    def __str__(self) -> str:
        return (
            f"approach = {self._approach_level}, branch distance ="
            f" {self._branch_distance}"
        )

    def __repr__(self) -> str:
        return (
            f"ControlFlowDistance(approach_level={self._approach_level}, "
            f"branch_distance={self._branch_distance})"
        )
