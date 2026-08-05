#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for non-branch goal handling in DynaMOSA."""

from typing import ClassVar

from pynguin.ga.algorithms.dynamosaalgorithm import _GoalsManager  # noqa: PLC2701
from pynguin.utils.orderedset import OrderedSet


def test_non_branch_goals_added_after_branch_completion():
    """Ensure non-branch goals activate only after branch goals are covered."""

    class DummyGoal:
        """Simple dummy goal."""

    class DummyArchive:
        """Minimal archive mock."""

        def __init__(self) -> None:
            """Initialize archive state."""
            self.covered_goals = set()
            self.uncovered_goals = set()

        def update(self, solutions) -> None:
            """Mock update."""
            return

        def add_goals(self, goals) -> None:
            """Track uncovered goals."""
            self.uncovered_goals = set(goals)

    class DummySubject:
        """Minimal subject properties mock."""

        existing_predicates: ClassVar[dict] = {}
        existing_code_objects: ClassVar[dict] = {}

    non_branch_goal = DummyGoal()

    manager = _GoalsManager(
        OrderedSet([non_branch_goal]),
        DummyArchive(),
        DummySubject(),
    )

    # Initially, non-branch goals should NOT be active
    assert non_branch_goal not in manager.current_goals
