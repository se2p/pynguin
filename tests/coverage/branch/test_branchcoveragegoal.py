#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

from pynguin.coverage.branch.branchcoveragegoal import (
    NonRootBranchCoverageGoal,
    RootBranchCoverageGoal,
)


@pytest.fixture
def root_branch_coverage_goal():
    return RootBranchCoverageGoal(0)


@pytest.fixture
def non_root_branch_coverage_goal():
    return NonRootBranchCoverageGoal(0, True)


def test_root_branch_coverage_goal(root_branch_coverage_goal):
    assert root_branch_coverage_goal.code_object_id == 0


def test_non_root_branch_coverage_goal(non_root_branch_coverage_goal):
    assert non_root_branch_coverage_goal.predicate_id == 0
    assert non_root_branch_coverage_goal.value is True


def test_root_hash(root_branch_coverage_goal):
    assert root_branch_coverage_goal.__hash__() != 0


def test_non_root_hash(non_root_branch_coverage_goal):
    assert non_root_branch_coverage_goal.__hash__() != 0


def test_root_eq_same(root_branch_coverage_goal):
    assert root_branch_coverage_goal.__eq__(root_branch_coverage_goal)


def test_non_root_eq_same(non_root_branch_coverage_goal):
    assert non_root_branch_coverage_goal.__eq__(non_root_branch_coverage_goal)


def test_root_eq_other_type(root_branch_coverage_goal):
    assert not root_branch_coverage_goal.__eq__(MagicMock())


def test_non_root_eq_other_type(non_root_branch_coverage_goal):
    assert not non_root_branch_coverage_goal.__eq__(MagicMock())


def test_root_eq_other(root_branch_coverage_goal):
    other = RootBranchCoverageGoal(0)
    assert root_branch_coverage_goal.__eq__(other)


def test_non_root_eq_other(non_root_branch_coverage_goal):
    other = NonRootBranchCoverageGoal(0, True)
    assert non_root_branch_coverage_goal.__eq__(other)


def test_root_get_distance(root_branch_coverage_goal, mocker):
    mock = mocker.patch(
        "pynguin.coverage.branch.branchcoveragegoal.cfd"
        ".get_root_control_flow_distance",
        return_value=42,
    )
    distance = root_branch_coverage_goal.get_distance(MagicMock(), MagicMock())
    assert distance == 42
    mock.assert_called_once()


def test_non_root_get_distance(non_root_branch_coverage_goal, mocker):
    mock = mocker.patch(
        "pynguin.coverage.branch.branchcoveragegoal.cfd"
        ".get_non_root_control_flow_distance",
        return_value=42,
    )
    distance = non_root_branch_coverage_goal.get_distance(MagicMock(), MagicMock())
    assert distance == 42
    mock.assert_called_once()
