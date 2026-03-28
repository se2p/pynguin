#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

from pynguin.utils.orderedset import OrderedSet
from pynguin.ga.algorithms.dynamosaalgorithm import _GoalsManager


class DummyBranchGoal:
    pass


class DummyNonBranchGoal:
    pass


class DummyArchive:
    def __init__(self):
        self.covered_goals = set()
        self.uncovered_goals = set()

    def update(self, solutions):
        pass

    def add_goals(self, goals):
        self.uncovered_goals = set(goals)


class DummySubject:
    existing_predicates = {}
    existing_code_objects = {}


def test_non_branch_goals_added_after_branch_completion():
    branch_goal = DummyBranchGoal()
    non_branch_goal = DummyNonBranchGoal()

    archive = DummyArchive()
    subject = DummySubject()

    manager = _GoalsManager(
        OrderedSet([branch_goal, non_branch_goal]),
        archive,
        subject,
    )

    # Initially → non-branch goal should NOT be active
    assert non_branch_goal not in manager.current_goals

    # Simulate branch goal being covered
    archive.covered_goals.add(branch_goal)
    archive.uncovered_goals.clear()

    manager.update([])

    # Now → non-branch goal SHOULD be active
    assert non_branch_goal in manager.current_goals