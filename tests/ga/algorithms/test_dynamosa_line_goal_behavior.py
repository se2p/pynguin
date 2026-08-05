#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Integration-like test for DynaMOSA handling of non-branch fitness functions."""

from pynguin.ga.algorithms.dynamosaalgorithm import _GoalsManager
from pynguin.utils.orderedset import OrderedSet


class DummyArchive:
    """Minimal archive."""

    def __init__(self):
        self.covered_goals = set()
        self.uncovered_goals = set()

    def update(self, solutions):
        pass

    def add_goals(self, goals):
        self.uncovered_goals = set(goals)


class DummySubject:
    """Minimal subject properties."""

    existing_predicates = {}
    existing_code_objects = {}


class DummyLineGoal:
    """Represents a non-branch goal."""

    pass


def test_dynamosa_handles_only_non_branch_goals():
    """Ensure DynaMOSA works when only non-branch goals are present."""

    archive = DummyArchive()
    subject = DummySubject()

    line_goal = DummyLineGoal()

    goals = OrderedSet([line_goal])

    manager = _GoalsManager(goals, archive, subject)

    # Should include the non-branch goal
    assert line_goal in manager.current_goals